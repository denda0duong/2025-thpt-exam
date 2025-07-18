"""
API-based scraper for THPT 2025 exam results
Uses the tuoitre.vn API endpoint for much faster data extraction
Optimized for Windows with better connection handling
"""

import asyncio
import aiohttp
import json
import time
import logging
import warnings
import sys
from typing import Dict, Optional, List
from dataclasses import dataclass

# Suppress Windows-specific asyncio warnings
warnings.filterwarnings(
    "ignore", category=RuntimeWarning, message=".*was never awaited.*"
)

# Set Windows-specific asyncio event loop policy for better connection handling
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        # Fallback for older Python versions
        pass


@dataclass
class ApiConfig:
    """Configuration for API scraper - optimized for Windows"""

    base_url: str = "https://s6.tuoitre.vn/api/diem-thi-thpt.htm"
    year: int = 2025
    timeout: int = 15  # Increased timeout for Windows
    max_retries: int = 3
    retry_delay: float = 2.0  # Increased delay between retries
    concurrent_requests: int = 15  # Reduced for Windows stability


class ApiScraper:
    """High-performance API-based scraper for THPT exam results"""

    def __init__(self, config: ApiConfig = None):
        self.config = config or ApiConfig()
        self.session = None
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "api_errors": 0,
            "network_errors": 0,
            "start_time": None,
            "end_time": None,
        }

        # Vietnamese subject mapping (same as web scraper)
        self.subject_mapping = {
            # JSON format subjects from API
            "TONGDIEM": "Total Score",
            "TOAN": "Math",
            "VAN": "Vietnamese",
            "NGOAI_NGU": "Foreign Language",
            "SU": "History",
            "DIA": "Geography",
            "GDKT_PL": "GDKT_PL",
            "LI": "Physics",
            "HOA": "Chemistry",
            "SINH": "Biology",
            "TIN_HOC": "Computer Science",
            "GIAO_DUC_CONG_DAN": "Civic Education",
            "CN_CONG_NGHIEP": "Industrial Technology",
            "CN_NONG_NGHIEP": "Agricultural Technology",
        }

    async def start_session(self):
        """Initialize the aiohttp session with optimized settings for Windows"""
        connector = aiohttp.TCPConnector(
            limit=50,  # Reduced connection pool limit for Windows
            limit_per_host=20,  # Reduced connections per host
            ttl_dns_cache=300,  # DNS cache TTL
            use_dns_cache=True,
            enable_cleanup_closed=True,
            force_close=True,  # Force close connections after use (no keepalive)
        )

        timeout = aiohttp.ClientTimeout(
            total=self.config.timeout,
            connect=5,  # Connection timeout
            sock_read=self.config.timeout,
            sock_connect=5,
        )

        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "close",  # Changed from keep-alive to close
                "Upgrade-Insecure-Requests": "1",
            },
        )

        self.stats["start_time"] = time.time()
        logging.info("API scraper session started with Windows-optimized settings")

    async def close_session(self):
        """Close the aiohttp session with proper cleanup"""
        if self.session:
            try:
                await self.session.close()
                # Give time for connections to close properly
                await asyncio.sleep(0.1)
                self.stats["end_time"] = time.time()
                logging.info("API scraper session closed")
            except Exception as e:
                logging.warning(f"Error closing session: {e}")
                self.stats["end_time"] = time.time()

    async def fetch_student_data(self, registration_number: str) -> Optional[Dict]:
        """
        Fetch student data from API endpoint

        Args:
            registration_number: Student registration number (e.g., "01000010")

        Returns:
            Dictionary with student data if successful, None if not found
        """
        url = (
            f"{self.config.base_url}?sbd={registration_number}&year={self.config.year}"
        )

        for attempt in range(self.config.max_retries):
            try:
                self.stats["total_requests"] += 1

                async with self.session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()

                        # Check if student exists
                        if (
                            data.get("success")
                            and data.get("total", 0) > 0
                            and data.get("data")
                        ):
                            student_raw = data["data"][0]
                            processed_data = self.process_api_response(
                                student_raw, registration_number
                            )

                            if processed_data:
                                self.stats["successful_requests"] += 1
                                return processed_data

                        # Student not found (valid API response but no data)
                        self.stats["successful_requests"] += 1
                        return None
                    else:
                        logging.warning(
                            f"API returned status {response.status} for {registration_number}"
                        )
                        self.stats["api_errors"] += 1

            except aiohttp.ClientError as e:
                logging.warning(
                    f"Network error for {registration_number} (attempt {attempt + 1}): {e}"
                )
                self.stats["network_errors"] += 1

            except ConnectionResetError as e:
                logging.warning(
                    f"Connection reset for {registration_number} (attempt {attempt + 1}): {e}"
                )
                self.stats["network_errors"] += 1

            except OSError as e:
                if "WinError 10054" in str(e):
                    logging.warning(
                        f"Windows connection forcibly closed for {registration_number} (attempt {attempt + 1})"
                    )
                else:
                    logging.warning(
                        f"OS error for {registration_number} (attempt {attempt + 1}): {e}"
                    )
                self.stats["network_errors"] += 1

            except json.JSONDecodeError as e:
                logging.warning(f"JSON decode error for {registration_number}: {e}")
                self.stats["api_errors"] += 1

            except Exception as e:
                logging.error(f"Unexpected error for {registration_number}: {e}")
                self.stats["failed_requests"] += 1

            # Wait before retry
            if attempt < self.config.max_retries - 1:
                await asyncio.sleep(self.config.retry_delay)

        self.stats["failed_requests"] += 1
        return None

    def process_api_response(
        self, student_raw: Dict, registration_number: str
    ) -> Optional[Dict]:
        """
        Process the raw API response into our standard format
        Extracts only meaningful data columns to keep CSV file size manageable

        Args:
            student_raw: Raw student data from API
            registration_number: Registration number for verification

        Returns:
            Processed student data dictionary with only essential fields
        """
        try:
            # Verify registration number matches
            if student_raw.get("SBD") != registration_number:
                logging.warning(
                    f"Registration number mismatch: expected {registration_number}, got {student_raw.get('SBD')}"
                )
                return None

            # Define the exact fields we want to extract for CSV
            meaningful_fields = [
                "Id",
                "TinhId",
                "MA_MON_NGOAI_NGU",
                "SBD",
                "TONGDIEM",
                "TOAN",
                "VAN",
                "NGOAI_NGU",
                "SU",
                "DIA",
                "GDKT_PL",
                "LI",
                "HOA",
                "SINH",
                "TIN_HOC",
                "GIAO_DUC_CONG_DAN",
                "CN_CONG_NGHIEP",
                "CN_NONG_NGHIEP",
            ]

            # Extract only the meaningful fields
            extracted_data = {}
            valid_scores_count = 0

            for field in meaningful_fields:
                if field in student_raw:
                    value = student_raw[field]

                    # Handle different field types
                    if field in ["Id", "TinhId", "MA_MON_NGOAI_NGU", "SBD"]:
                        # String/ID fields
                        extracted_data[field] = str(value) if value is not None else ""
                    else:
                        # Score fields (TONGDIEM, TOAN, VAN, etc.)
                        if isinstance(value, (int, float)):
                            if value >= 0:  # Valid score (filter out -1 values)
                                extracted_data[field] = float(value)
                                if field != "TONGDIEM":  # Don't count total score
                                    valid_scores_count += 1
                            else:
                                extracted_data[field] = None
                        else:
                            extracted_data[field] = None
                else:
                    extracted_data[field] = None

            # Only return data if we have valid scores or total score
            if valid_scores_count > 0 or (
                extracted_data.get("TONGDIEM") and extracted_data.get("TONGDIEM") > 0
            ):
                return {
                    "registration_number": registration_number,
                    "timestamp": time.time(),
                    "total_subjects": valid_scores_count,
                    "source": "api",
                    **extracted_data,  # Include all meaningful fields
                }

            return None

        except Exception as e:
            logging.error(
                f"Error processing API response for {registration_number}: {e}"
            )
            return None

    async def fetch_batch(self, registration_numbers: List[str]) -> List[Dict]:
        """
        Fetch a batch of students concurrently with Windows-optimized error handling

        Args:
            registration_numbers: List of registration numbers to fetch

        Returns:
            List of student data dictionaries
        """
        try:
            tasks = [
                self.fetch_student_data(reg_num) for reg_num in registration_numbers
            ]

            # Use semaphore to limit concurrent requests
            semaphore = asyncio.Semaphore(self.config.concurrent_requests)

            async def fetch_with_semaphore(task):
                async with semaphore:
                    try:
                        return await task
                    except (ConnectionResetError, OSError) as e:
                        if "WinError 10054" in str(e):
                            logging.warning(
                                "Windows connection reset handled gracefully"
                            )
                            return None
                        raise

            results = await asyncio.gather(
                *[fetch_with_semaphore(task) for task in tasks], return_exceptions=True
            )

            # Filter out None results and exceptions
            valid_results = []
            for result in results:
                if isinstance(result, Exception):
                    logging.warning(f"Exception in batch processing: {result}")
                    continue
                if result is not None:
                    valid_results.append(result)

            return valid_results

        except Exception as e:
            logging.error(f"Batch processing failed: {e}")
            return []

    def get_stats(self) -> Dict:
        """Get scraper statistics"""
        stats = self.stats.copy()
        if stats["start_time"] and stats["end_time"]:
            stats["duration"] = stats["end_time"] - stats["start_time"]
            stats["requests_per_second"] = stats["total_requests"] / stats["duration"]
        return stats

    def print_stats(self):
        """Print formatted statistics"""
        stats = self.get_stats()

        print("\n" + "=" * 50)
        print("API SCRAPER STATISTICS")
        print("=" * 50)
        print(f"Total Requests: {stats['total_requests']:,}")
        print(f"Successful: {stats['successful_requests']:,}")
        print(f"Failed: {stats['failed_requests']:,}")
        print(f"API Errors: {stats['api_errors']:,}")
        print(f"Network Errors: {stats['network_errors']:,}")

        if "duration" in stats:
            print(f"Duration: {stats['duration']:.1f} seconds")
            print(f"Requests/Second: {stats['requests_per_second']:.1f}")

        if stats["total_requests"] > 0:
            success_rate = (
                stats["successful_requests"] / stats["total_requests"]
            ) * 100
            print(f"Success Rate: {success_rate:.1f}%")

        print("=" * 50)


# Test function
async def test_api_scraper():
    """Test the API scraper with a few sample registration numbers"""
    logging.basicConfig(level=logging.INFO)

    scraper = ApiScraper()

    try:
        await scraper.start_session()

        # Test with known good numbers
        test_numbers = [
            "01000001",
            "01000002",
            "01000010",
            "01000999",
        ]  # Last one likely invalid

        print("Testing API scraper with sample numbers...")
        for reg_num in test_numbers:
            result = await scraper.fetch_student_data(reg_num)
            if result:
                print(
                    f"✅ {reg_num}: {result['total_subjects']} subjects, Total: {result.get('TONGDIEM', 'N/A')}"
                )
            else:
                print(f"❌ {reg_num}: No data found")

        # Test batch processing
        print("\nTesting batch processing...")
        batch_results = await scraper.fetch_batch(test_numbers)
        print(f"Batch processed: {len(batch_results)} students found")

        scraper.print_stats()

    except Exception as e:
        logging.error(f"Test failed: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await scraper.close_session()


if __name__ == "__main__":
    asyncio.run(test_api_scraper())
