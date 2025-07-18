"""
Logging utility for the THPT 2025 crawler
"""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from config import Config


class Logger:
    def __init__(self):
        self.config = Config()
        self.setup_logger()

    def setup_logger(self):
        """Set up the logging configuration"""
        # Ensure logs directory exists
        Path(self.config.output["logs_dir"]).mkdir(exist_ok=True)

        # Create log filename with current date
        log_filename = self.config.output["log_file_pattern"].format(
            date=datetime.now().strftime("%Y-%m-%d")
        )
        log_filepath = Path(self.config.output["logs_dir"]) / log_filename

        # Configure logging
        self.logger = logging.getLogger("thpt_crawler")
        self.logger.setLevel(getattr(logging, self.config.logging["level"]))

        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s]: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        # Add console handler if enabled
        if self.config.logging["log_to_console"]:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        # Add file handler if enabled
        if self.config.logging["log_to_file"]:
            file_handler = logging.FileHandler(log_filepath, encoding="utf-8")
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def _log_with_meta(self, level: str, message: str, meta: Dict[str, Any] = None):
        """Log a message with optional metadata"""
        if meta:
            full_message = f"{message} {json.dumps(meta, ensure_ascii=False)}"
        else:
            full_message = message

        getattr(self.logger, level.lower())(full_message)

    def debug(self, message: str, meta: Dict[str, Any] = None):
        """Log debug message"""
        self._log_with_meta("DEBUG", message, meta)

    def info(self, message: str, meta: Dict[str, Any] = None):
        """Log info message"""
        self._log_with_meta("INFO", message, meta)

    def warning(self, message: str, meta: Dict[str, Any] = None):
        """Log warning message"""
        self._log_with_meta("WARNING", message, meta)

    def error(self, message: str, meta: Dict[str, Any] = None):
        """Log error message"""
        self._log_with_meta("ERROR", message, meta)

    def critical(self, message: str, meta: Dict[str, Any] = None):
        """Log critical message"""
        self._log_with_meta("CRITICAL", message, meta)

    # Specialized logging methods for crawler events
    def log_crawler_start(self, total_numbers: int, batch_size: int):
        """Log crawler start event"""
        self.info(
            "Crawler started",
            {
                "total_numbers": total_numbers,
                "batch_size": batch_size,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def log_crawler_end(self, stats: Dict[str, Any]):
        """Log crawler end event"""
        self.info(
            "Crawler completed", {**stats, "timestamp": datetime.now().isoformat()}
        )

    def log_batch_start(self, batch_index: int, batch_size: int):
        """Log batch start event"""
        self.info(
            "Batch processing started",
            {
                "batch_index": batch_index,
                "batch_size": batch_size,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def log_batch_end(self, batch_index: int, success_count: int, error_count: int):
        """Log batch end event"""
        self.info(
            "Batch processing completed",
            {
                "batch_index": batch_index,
                "success_count": success_count,
                "error_count": error_count,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def log_successful_lookup(
        self, registration_number: str, student_data: Dict[str, Any]
    ):
        """Log successful lookup event"""
        self.debug(
            "Successful lookup",
            {
                "registration_number": registration_number,
                "student_name": student_data.get("student_name", "N/A"),
                "timestamp": datetime.now().isoformat(),
            },
        )

    def log_failed_lookup(self, registration_number: str, error: Exception):
        """Log failed lookup event"""
        self.warning(
            "Failed lookup",
            {
                "registration_number": registration_number,
                "error": str(error),
                "timestamp": datetime.now().isoformat(),
            },
        )

    def log_not_found(self, registration_number: str):
        """Log not found event"""
        self.debug(
            "Registration number not found",
            {
                "registration_number": registration_number,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def log_retry(self, registration_number: str, attempt: int, max_attempts: int):
        """Log retry event"""
        self.warning(
            "Retrying lookup",
            {
                "registration_number": registration_number,
                "attempt": attempt,
                "max_attempts": max_attempts,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def log_rate_limit_delay(self, delay: float):
        """Log rate limit delay event"""
        self.info(
            "Rate limit delay",
            {"delay": delay, "timestamp": datetime.now().isoformat()},
        )

    def log_progress(self, processed: int, total: int, percentage: float):
        """Log progress event"""
        self.info(
            "Progress update",
            {
                "processed": processed,
                "total": total,
                "percentage": f"{percentage:.2f}%",
                "timestamp": datetime.now().isoformat(),
            },
        )

    def log_error(self, error: Exception, context: Dict[str, Any] = None):
        """Log error with context"""
        self.error(
            "Error occurred",
            {
                "error": str(error),
                "error_type": type(error).__name__,
                "context": context or {},
                "timestamp": datetime.now().isoformat(),
            },
        )

    def log_save_data(self, filename: str, record_count: int):
        """Log data save event"""
        self.info(
            "Data saved",
            {
                "filename": filename,
                "record_count": record_count,
                "timestamp": datetime.now().isoformat(),
            },
        )
