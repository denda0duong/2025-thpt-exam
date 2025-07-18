"""
Simple utility for generating registration numbers
"""

from typing import List, Dict, Generator
from config import Config


class RegistrationNumberGenerator:
    def __init__(self):
        self.config = Config()
        self.council_codes = self.config.registration["council_codes"]
        self.student_number_min = self.config.registration["student_number_min"]
        self.student_number_max = self.config.registration["student_number_max"]

    def generate_single(self, council_code: str, student_number: int) -> str:
        """
        Generate a single registration number

        Args:
            council_code: 2-digit council code (01-65)
            student_number: 6-digit student number (000001-999999)

        Returns:
            8-digit registration number
        """
        padded_student_number = f"{student_number:06d}"
        return f"{council_code}{padded_student_number}"

    def generate_for_council(self, council_code: str) -> List[str]:
        """
        Generate all registration numbers for a specific council

        Args:
            council_code: 2-digit council code

        Returns:
            List of registration numbers
        """
        numbers = []
        for i in range(self.student_number_min, self.student_number_max + 1):
            numbers.append(self.generate_single(council_code, i))
        return numbers

    def generate_all(self) -> List[str]:
        """
        Generate all possible registration numbers

        Returns:
            List of all possible registration numbers
        """
        all_numbers = []
        for council_code in self.council_codes:
            all_numbers.extend(self.generate_for_council(council_code))
        return all_numbers

    def generate_batches(
        self, batch_size: int = None
    ) -> Generator[List[str], None, None]:
        """
        Generate registration numbers in batches

        Args:
            batch_size: Size of each batch

        Yields:
            Batches of registration numbers
        """
        if batch_size is None:
            batch_size = self.config.crawler["batch_size"]

        for council_code in self.council_codes:
            batch = []
            for i in range(self.student_number_min, self.student_number_max + 1):
                batch.append(self.generate_single(council_code, i))

                if len(batch) == batch_size:
                    yield batch
                    batch = []

            # Yield remaining numbers in the last batch
            if batch:
                yield batch

    def generate_range(
        self, start_council: str, start_student: int, end_council: str, end_student: int
    ) -> List[str]:
        """
        Generate a specific range of registration numbers

        Args:
            start_council: Starting council code
            start_student: Starting student number
            end_council: Ending council code
            end_student: Ending student number

        Returns:
            List of registration numbers in the range
        """
        numbers = []

        try:
            start_council_index = self.council_codes.index(start_council)
            end_council_index = self.council_codes.index(end_council)
        except ValueError:
            raise ValueError("Invalid council codes")

        for council_index in range(start_council_index, end_council_index + 1):
            council_code = self.council_codes[council_index]
            min_student = (
                start_student
                if council_index == start_council_index
                else self.student_number_min
            )
            max_student = (
                end_student
                if council_index == end_council_index
                else self.student_number_max
            )

            for student_num in range(min_student, max_student + 1):
                numbers.append(self.generate_single(council_code, student_num))

        return numbers

    def is_valid_format(self, registration_number: str) -> bool:
        """
        Validate a registration number format

        Args:
            registration_number: The registration number to validate

        Returns:
            True if valid, False otherwise
        """
        if not registration_number or len(registration_number) != 8:
            return False

        council_code = registration_number[:2]
        student_number = registration_number[2:]

        # Check if council code is valid
        if council_code not in self.council_codes:
            return False

        # Check if student number is valid
        try:
            student_num = int(student_number)
            if (
                student_num < self.student_number_min
                or student_num > self.student_number_max
            ):
                return False
        except ValueError:
            return False

        return True

    def parse(self, registration_number: str) -> Dict[str, any]:
        """
        Parse a registration number into its components

        Args:
            registration_number: The registration number to parse

        Returns:
            Dictionary containing council_code, student_number, and full number
        """
        if not self.is_valid_format(registration_number):
            raise ValueError(
                f"Invalid registration number format: {registration_number}"
            )

        return {
            "council_code": registration_number[:2],
            "student_number": int(registration_number[2:]),
            "full": registration_number,
        }

    def get_total_count(self) -> int:
        """
        Get total count of possible registration numbers

        Returns:
            Total count
        """
        return len(self.council_codes) * (
            self.student_number_max - self.student_number_min + 1
        )

    def get_stats(self) -> Dict[str, any]:
        """
        Get statistics about the registration number generation

        Returns:
            Statistics dictionary
        """
        total_count = self.get_total_count()
        batch_count = (
            total_count + self.config.crawler["batch_size"] - 1
        ) // self.config.crawler["batch_size"]

        return {
            "total_registration_numbers": total_count,
            "council_codes": len(self.council_codes),
            "student_number_range": {
                "min": self.student_number_min,
                "max": self.student_number_max,
                "count": self.student_number_max - self.student_number_min + 1,
            },
            "batch_size": self.config.crawler["batch_size"],
            "total_batches": batch_count,
        }
