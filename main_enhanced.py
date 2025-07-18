"""
Enhanced main crawler with API method only
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Optional

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

from config import Config
from crawler_skip_manager import CrawlerSkipManager
from logger import Logger
from api_scraper import ApiScraper, ApiConfig
from results_saver import ResultsSaver


class ApiCrawler:
    """API-based crawler for maximum performance"""

    def __init__(self):
        self.logger = Logger()
        self.config = Config()
        self.results_saver = ResultsSaver()
        self.skip_manager = CrawlerSkipManager(self.logger)

        # Initialize API scraper
        self.api_scraper = None
        self.stats = {
            "total_processed": 0,
            "total_successful": 0,
            "total_failed": 0,
            "last_save_count": 0,
        }

    async def initialize_scraper(self):
        """Initialize the API scraper"""
        self.logger.info("Initializing API scraper...")
        self.api_scraper = ApiScraper(
            ApiConfig(concurrent_requests=15)
        )  # Reduced for Windows
        await self.api_scraper.start_session()
        self.logger.info("API scraper initialized successfully")

    async def cleanup_scraper(self):
        """Clean up the API scraper"""
        if self.api_scraper:
            await self.api_scraper.close_session()
            self.logger.info("API scraper closed")

    async def crawl_batch_api(self, registration_numbers: List[str]) -> List[Dict]:
        """
        Crawl a batch of registration numbers using API (much faster)

        Args:
            registration_numbers: List of registration numbers to process

        Returns:
            List of student data dictionaries
        """
        if not self.api_scraper:
            return []

        # Filter out numbers we should skip
        valid_numbers = [
            num
            for num in registration_numbers
            if not self.skip_manager.should_skip(num)
        ]

        if not valid_numbers:
            return []

        try:
            results = await self.api_scraper.fetch_batch(valid_numbers)

            # Record results
            found_numbers = {result["registration_number"] for result in results}

            for num in valid_numbers:
                if num in found_numbers:
                    self.skip_manager.record_success(num)
                else:
                    self.skip_manager.record_failure(num, "not_found")

            return results

        except Exception as e:
            self.logger.error(f"Batch API crawl failed: {e}")
            return []

    async def crawl_council_fast(self, council_code: str, start_number: int = 1) -> int:
        """
        Crawl a council using optimized batch processing

        Args:
            council_code: Council code (e.g., "01")
            start_number: Starting student number (default: 1)

        Returns:
            Number of students found
        """
        self.logger.info(
            f"🚀 Starting fast crawl for council {council_code} from number {start_number:06d}"
        )

        consecutive_failures = 0
        student_number = start_number
        council_successful = 0
        batch_size = 100  # Process in batches of 100

        while consecutive_failures < 1000:  # Increased limit for batch processing
            # Create batch
            batch = []
            for i in range(batch_size):
                if consecutive_failures >= 1000:
                    break
                reg_num = f"{council_code}{student_number:06d}"
                batch.append(reg_num)
                student_number += 1

            if not batch:
                break

            # Process batch using API
            results = await self.crawl_batch_api(batch)

            if results:
                # Reset consecutive failures if we found any students
                consecutive_failures = 0
                council_successful += len(results)

                # Add results to saver
                for result in results:
                    self.results_saver.add_result(result)
                    self.stats["total_successful"] += 1

                self.logger.info(
                    f"📊 Council {council_code}: Found {len(results)} students in batch (Numbers: {results[0]['registration_number']}-{results[-1]['registration_number']})"
                )
            else:
                # All students in batch failed
                consecutive_failures += len(batch)
                self.stats["total_failed"] += len(batch)

            self.stats["total_processed"] += len(batch)

            # Auto-save check - changed to 10,000 successful students
            if self.stats["total_successful"] - self.stats["last_save_count"] >= 10000:
                self.logger.info(
                    f"💾 Auto-saving results after {self.stats['total_successful']} successful students..."
                )
                self.results_saver.save_all()
                self.stats["last_save_count"] = self.stats["total_successful"]
                self.logger.info("✅ Auto-save completed")

            # Progress update
            if student_number % 2000 == 0:
                self.logger.info(
                    f"📈 Council {council_code}: Processed {student_number:,} students, Found {council_successful}, Consecutive failures: {consecutive_failures}"
                )

        self.logger.info(
            f"🎯 Council {council_code} completed: {council_successful} students found"
        )
        return council_successful

    async def run_full_crawler(self):
        """Run the full crawler with API method, starting from 48034201"""
        try:
            self.logger.info("🚀 Starting API-Based THPT 2025 Crawler")
            self.logger.info("📊 Method: API (High Performance)")
            self.logger.info("🎯 Starting from registration number: 48034201")

            # Initialize scraper
            await self.initialize_scraper()

            # Parse starting number: 48034201 = council 48, student 034201
            start_council = 48
            start_student_number = 34201

            # Process all councils starting from the specified one
            for council_num in range(start_council, 66):  # 48 to 65
                council_code = f"{council_num:02d}"

                # For the first council, start from the specific student number
                if council_num == start_council:
                    await self.crawl_council_fast(council_code, start_student_number)
                else:
                    # For subsequent councils, start from student number 1
                    await self.crawl_council_fast(council_code, 1)

                # Save after each council
                self.logger.info(f"💾 Saving results for council {council_code}...")
                self.results_saver.save_all()
                self.stats["last_save_count"] = self.stats["total_successful"]

                # Continue to next council
                if council_num < 65:
                    self.logger.info(f"➡️ Moving to next council {council_num+1:02d}")

            self.logger.info("🎉 All councils processed successfully!")

        except KeyboardInterrupt:
            self.logger.info("⚠️ Crawler interrupted by user")
            self.logger.info("💾 Saving remaining results...")
            self.results_saver.save_all()
            self.logger.info("✅ Emergency save completed")

        except Exception as e:
            self.logger.error(f"❌ Crawler failed: {e}")
            import traceback

            traceback.print_exc()

        finally:
            # Cleanup
            await self.cleanup_scraper()

            # Final save
            self.logger.info("💾 Performing final save...")
            self.results_saver.save_all()

            # Print final statistics
            self.print_final_stats()

    def print_final_stats(self):
        """Print final crawler statistics"""
        stats = self.stats

        print("\n" + "=" * 60)
        print("🎯 API CRAWLER FINAL STATISTICS")
        print("=" * 60)
        print("📊 Method Used: API (High Performance)")
        print(f"📈 Total Processed: {stats['total_processed']:,}")
        print(f"✅ Total Successful: {stats['total_successful']:,}")
        print(f"❌ Total Failed: {stats['total_failed']:,}")

        if stats["total_processed"] > 0:
            success_rate = (stats["total_successful"] / stats["total_processed"]) * 100
            print(f"📊 Success Rate: {success_rate:.1f}%")

        print("=" * 60)

        # Print scraper-specific stats
        if self.api_scraper:
            print("\n🚀 API SCRAPER STATISTICS:")
            self.api_scraper.print_stats()

        # Print results summary
        self.results_saver.print_summary()


async def main():
    """Main function"""
    print("🎓 API-Based THPT 2025 Crawler")
    print("=" * 40)
    print("🚀 High Performance API Method")
    print("⚡ Concurrent batch processing")
    print("� Up to 20x faster than web scraping")
    print("=" * 40)

    try:
        input("Press Enter to start crawler...")

        crawler = ApiCrawler()
        await crawler.run_full_crawler()

    except KeyboardInterrupt:
        print("\n⚠️ Crawler interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
