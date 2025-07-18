"""
Configuration for THPT 2025 Exam Results Crawler
"""

from pathlib import Path


class Config:
    def __init__(self):
        self.target = {
            "url": "https://tuoitre.vn/diem-thi.htm",
            "search_form_selector": 'form[action*="diem-thi"]',
            "input_selector": 'input[name="sobd"]',
            "submit_button_selector": 'button[type="submit"], input[type="submit"]',
            "results_selector": ".result-container, .diem-thi-result",
            "no_results_message": "Không tìm thấy",
        }

        # Registration number configuration
        self.registration = {
            "council_codes": [f"{i:02d}" for i in range(1, 66)],  # 01 to 65
            "student_number_min": 1,
            "student_number_max": 999999,
            "total_length": 8,  # 2 digits council code + 6 digits student number
        }

        # Crawler configuration
        self.crawler = {
            "concurrency": 10,  # Increased from 5 to 10 concurrent requests
            "delay_between_requests": 200,  # Reduced from 400ms to 200ms
            "retry_attempts": 2,  # Reduced from 3 to 2 attempts
            "retry_delay": 1000,  # Reduced from 2000ms to 1000ms
            "timeout": 15000,  # Reduced from 30000ms to 15000ms
            # Batch processing
            "batch_size": 1000,  # Number of registration numbers per batch
            "save_interval": 100,  # Save results every N successful requests
            # Speed optimizations
            "parallel_councils": 3,  # Process multiple councils simultaneously
            "prefetch_pages": True,  # Keep browser pages ready
            "skip_unnecessary_waits": True,  # Skip non-essential waits
        }

        # Browser configuration
        self.browser = {
            "headless": True,
            "viewport": {"width": 1366, "height": 768},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            # Speed optimizations
            "disable_images": True,  # Don't load images
            "disable_javascript": False,  # Keep JS but optimize
            "disable_css": False,  # Keep CSS for proper parsing
            "disable_fonts": True,  # Don't load fonts
            "disable_plugins": True,  # Disable plugins
            "disable_extensions": True,  # Disable extensions
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-web-security",
                "--disable-features=TranslateUI",
                "--disable-ipc-flooding-protection",
                "--aggressive-cache-discard",
                "--memory-pressure-off",
                "--max_old_space_size=4096",
            ],
        }

        # Output configuration
        self.output = {
            "data_dir": "./data",
            "logs_dir": "./logs",
            "formats": ["json", "csv"],  # Available: json, csv, xlsx
            # File naming patterns
            "data_file_pattern": "thpt-2025-results-{timestamp}.json",
            "csv_file_pattern": "thpt-2025-results-{timestamp}.csv",
            "log_file_pattern": "crawler-{date}.log",
            # Progress tracking
            "progress_file": "progress.json",
            "resume_file": "resume.json",
        }

        # Logging configuration
        self.logging = {
            "level": "INFO",  # DEBUG, INFO, WARNING, ERROR, CRITICAL
            "log_to_console": True,
            "log_to_file": True,
            "max_log_files": 10,
            "max_log_size": 10 * 1024 * 1024,  # 10MB in bytes
        }

        # Data validation
        self.validation = {
            "required_fields": ["registration_number", "student_name"],
            "score_subjects": [
                "toan",
                "ngu_van",
                "ngoai_ngu",
                "vat_ly",
                "hoa_hoc",
                "sinh_hoc",
                "lich_su",
                "dia_ly",
                "gdcd",
            ],
        }

        # Ensure directories exist
        self._ensure_directories()

    def _ensure_directories(self):
        """Create necessary directories if they don't exist"""
        Path(self.output["data_dir"]).mkdir(exist_ok=True)
        Path(self.output["logs_dir"]).mkdir(exist_ok=True)
