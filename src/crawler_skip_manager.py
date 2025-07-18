"""
Smart skipping manager for the crawler to optimize performance
"""

import json
import os
from typing import Dict, List, Set
from logger import Logger


class CrawlerSkipManager:
    def __init__(self, logger: Logger):
        self.logger = logger

        # File paths for persistence
        self.skip_ranges_file = "data/skip_ranges.json"
        self.council_limits_file = "data/council_limits.json"
        self.invalid_patterns_file = "data/invalid_patterns.json"

        # Load skip data
        self.skip_ranges: Dict[str, List[Dict]] = self._load_skip_ranges()
        self.council_limits: Dict[str, int] = self._load_council_limits()
        self.invalid_patterns: Set[str] = self._load_invalid_patterns()

        # Runtime tracking
        self.consecutive_failures: Dict[str, int] = {}
        self.last_valid_number: Dict[str, int] = {}
        self.failure_threshold = 100  # Configurable threshold

    def _load_skip_ranges(self) -> Dict[str, List[Dict]]:
        """Load skip ranges from file"""
        if os.path.exists(self.skip_ranges_file):
            try:
                with open(self.skip_ranges_file, "r") as f:
                    data = json.load(f)
                    if self.logger:
                        if self.logger:
                            self.logger.info(
                                f"Loaded skip ranges for {len(data)} councils"
                            )
                    return data
            except Exception as e:
                if self.logger:
                    if self.logger:
                        self.logger.warning(f"Failed to load skip ranges: {e}")
        return {}

    def _load_council_limits(self) -> Dict[str, int]:
        """Load known council limits from file"""
        if os.path.exists(self.council_limits_file):
            try:
                with open(self.council_limits_file, "r") as f:
                    data = json.load(f)
                    if self.logger:
                        if self.logger:
                            self.logger.info(f"Loaded limits for {len(data)} councils")
                    return data
            except Exception as e:
                if self.logger:
                    if self.logger:
                        self.logger.warning(f"Failed to load council limits: {e}")
        return {}

    def _load_invalid_patterns(self) -> Set[str]:
        """Load invalid patterns from file"""
        if os.path.exists(self.invalid_patterns_file):
            try:
                with open(self.invalid_patterns_file, "r") as f:
                    data = set(json.load(f))
                    if self.logger:
                        self.logger.info(f"Loaded {len(data)} invalid patterns")
                    return data
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Failed to load invalid patterns: {e}")
        return set()

    def _save_skip_ranges(self):
        """Save skip ranges to file"""
        os.makedirs("data", exist_ok=True)
        with open(self.skip_ranges_file, "w") as f:
            json.dump(self.skip_ranges, f, indent=2)

    def _save_council_limits(self):
        """Save council limits to file"""
        os.makedirs("data", exist_ok=True)
        with open(self.council_limits_file, "w") as f:
            json.dump(self.council_limits, f, indent=2)

    def _save_invalid_patterns(self):
        """Save invalid patterns to file"""
        os.makedirs("data", exist_ok=True)
        with open(self.invalid_patterns_file, "w") as f:
            json.dump(list(self.invalid_patterns), f, indent=2)

    def should_skip(self, registration_number: str) -> bool:
        """
        Check if a registration number should be skipped

        Args:
            registration_number: 8-digit registration number

        Returns:
            True if should skip, False otherwise
        """
        council_code = registration_number[:2]
        student_number = int(registration_number[2:])

        # Check against council limits
        if council_code in self.council_limits:
            if student_number > self.council_limits[council_code]:
                return True

        # Check against skip ranges
        if council_code in self.skip_ranges:
            for skip_range in self.skip_ranges[council_code]:
                if skip_range["start"] <= student_number <= skip_range["end"]:
                    return True

        # Check against invalid patterns
        if registration_number in self.invalid_patterns:
            return True

        return False

    def record_failure(self, registration_number: str, error_type: str = "not_found"):
        """
        Record a failed attempt

        Args:
            registration_number: Registration number that failed
            error_type: Type of error (e.g., "not_found", "invalid_format", "timeout")
        """
        council_code = registration_number[:2]
        student_number = int(registration_number[2:])

        # Track consecutive failures
        key = f"{council_code}_{student_number}"
        self.consecutive_failures[key] = self.consecutive_failures.get(key, 0) + 1

        # Add to invalid patterns
        self.invalid_patterns.add(registration_number)

        # If too many consecutive failures, create a skip range
        if self.consecutive_failures[key] >= self.failure_threshold:
            self.add_skip_range(
                council_code,
                student_number,
                student_number + 1000,
                "consecutive_failures",
            )
            if self.logger:
                self.logger.warning(
                    f"Added skip range for {council_code} starting at {student_number} due to consecutive failures"
                )

    def record_success(self, registration_number: str):
        """
        Record a successful attempt

        Args:
            registration_number: Registration number that succeeded
        """
        council_code = registration_number[:2]
        student_number = int(registration_number[2:])

        # Update last valid number
        self.last_valid_number[council_code] = max(
            self.last_valid_number.get(council_code, 0), student_number
        )

        # Reset consecutive failures for this area
        key = f"{council_code}_{student_number}"
        self.consecutive_failures[key] = 0

    def add_skip_range(
        self,
        council_code: str,
        start_student: int,
        end_student: int,
        reason: str = "not_found",
    ):
        """
        Add a range of student numbers to skip for a specific council

        Args:
            council_code: Council code (e.g., "01")
            start_student: Starting student number to skip
            end_student: Ending student number to skip
            reason: Reason for skipping
        """
        if council_code not in self.skip_ranges:
            self.skip_ranges[council_code] = []

        self.skip_ranges[council_code].append(
            {
                "start": start_student,
                "end": end_student,
                "reason": reason,
                "added_at": str(os.path.getctime(__file__)),
            }
        )

        self._save_skip_ranges()

    def set_council_limit(self, council_code: str, max_student_number: int):
        """
        Set the maximum valid student number for a council

        Args:
            council_code: Council code (e.g., "01")
            max_student_number: Maximum valid student number found
        """
        current_limit = self.council_limits.get(council_code, float("inf"))
        if max_student_number < current_limit:
            self.council_limits[council_code] = max_student_number
            self._save_council_limits()
            if self.logger:
                self.logger.info(
                    f"Updated council {council_code} limit to {max_student_number}"
                )

    def get_skip_stats(self) -> Dict:
        """
        Get statistics about skipping

        Returns:
            Dictionary with skip statistics
        """
        total_skip_ranges = sum(len(ranges) for ranges in self.skip_ranges.values())
        return {
            "councils_with_limits": len(self.council_limits),
            "total_skip_ranges": total_skip_ranges,
            "invalid_patterns": len(self.invalid_patterns),
            "consecutive_failures_tracked": len(self.consecutive_failures),
            "last_valid_numbers": len(self.last_valid_number),
        }

    def save_all(self):
        """Save all skip data to files"""
        self._save_skip_ranges()
        self._save_council_limits()
        self._save_invalid_patterns()
        if self.logger:
            self.logger.info("Saved all skip data to files")
