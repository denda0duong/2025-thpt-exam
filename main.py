"""
Main entry point for the THPT 2025 Exam Results Crawler
"""

import asyncio
import sys
import logging
from pathlib import Path
from typing import List, Dict, Optional

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

from config import Config
from registration_number_generator import RegistrationNumberGenerator
from crawler_skip_manager import CrawlerSkipManager
from logger import Logger
from web_scraper import WebScraper
from results_saver import ResultsSaver


# Global web scraper pool
web_scraper_pool = []
pool_size = 1  # Reduced from 3 to 1 for stability


async def initialize_web_scraper_pool():
    """Initialize multiple web scrapers for parallel processing"""
    global web_scraper_pool
    web_scraper_pool = []

    for i in range(pool_size):
        max_retries = 2  # Reduced retries
        for attempt in range(max_retries):
            try:
                logging.info(
                    f"Initializing scraper {i+1}/{pool_size}, attempt {attempt+1}"
                )
                scraper = WebScraper()

                # Add timeout to browser startup
                try:
                    await asyncio.wait_for(
                        scraper.start_browser(headless=True), timeout=30
                    )
                    web_scraper_pool.append(scraper)
                    logging.info(f"Successfully initialized scraper {i+1}/{pool_size}")
                    break
                except asyncio.TimeoutError:
                    logging.warning(
                        f"Timeout initializing scraper {i+1}, attempt {attempt+1}"
                    )
                    try:
                        await scraper.close_browser()
                    except Exception:
                        pass
                    if attempt < max_retries - 1:
                        await asyncio.sleep(3)
                    continue

            except Exception as e:
                logging.warning(
                    f"Failed to initialize scraper {i+1} on attempt {attempt+1}: {e}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(3)  # Wait before retry
                else:
                    logging.error(
                        f"Failed to initialize scraper {i+1} after {max_retries} attempts"
                    )
                    # Continue with fewer scrapers if some fail
                    break

    if not web_scraper_pool:
        raise Exception("Failed to initialize any scrapers")

    logging.info(
        f"Successfully initialized {len(web_scraper_pool)} scrapers out of {pool_size} attempted"
    )


async def cleanup_web_scraper_pool():
    """Cleanup all web scrapers in the pool"""
    global web_scraper_pool
    for i, scraper in enumerate(web_scraper_pool):
        try:
            await scraper.close_browser()
            logging.info(f"Closed scraper {i+1}/{len(web_scraper_pool)}")
        except Exception as e:
            logging.warning(f"Error closing scraper {i+1}: {e}")
    web_scraper_pool = []


async def get_available_scraper():
    """Get an available scraper from the pool (round-robin for simplicity)"""
    global web_scraper_pool
    if not web_scraper_pool:
        await initialize_web_scraper_pool()

    # Simple round-robin selection
    import random

    return random.choice(web_scraper_pool)


async def crawl_registration_number(
    registration_number: str, skip_manager: CrawlerSkipManager, logger: Logger
) -> Optional[Dict]:
    """
    Crawl a single registration number using Playwright with scraper pool

    Args:
        registration_number: The registration number to crawl
        skip_manager: Skip manager instance
        logger: Logger instance

    Returns:
        Dictionary with student data if successful, None if failed
    """
    # Check if we should skip this number
    if skip_manager.should_skip(registration_number):
        logger.debug(f"Skipping {registration_number} (marked for skip)")
        return False

    max_retries = 2
    for attempt in range(max_retries):
        try:
            # Get an available scraper from the pool
            scraper = await get_available_scraper()

            # Use web scraper to get actual data
            result = await scraper.scrape_registration_number(registration_number)

            if result:
                skip_manager.record_success(registration_number)
                # Extract student info for logging
                scores = result.get("scores", {})
                total_score = scores.get("Total Score", "N/A")
                subject_count = len([s for s in scores.keys() if s != "Total Score"])
                logger.info(
                    f"Successfully crawled {registration_number}: {subject_count} subjects, Total: {total_score}"
                )
                return result  # Return the actual result data
            else:
                skip_manager.record_failure(registration_number, "not_found")
                logger.debug(f"No data found for {registration_number}")
                return None

        except Exception as e:
            logger.warning(
                f"Attempt {attempt + 1} failed for {registration_number}: {e}"
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(1)  # Wait before retry
                continue
            else:
                skip_manager.record_failure(registration_number, "error")
                logger.error(
                    f"Error crawling {registration_number} after {max_retries} attempts: {e}"
                )
                return None


async def process_batch(
    batch: List[str],
    skip_manager: CrawlerSkipManager,
    logger: Logger,
    results_saver: ResultsSaver,
) -> Dict:
    """
    Process a batch of registration numbers

    Args:
        batch: List of registration numbers to process
        skip_manager: Skip manager instance
        logger: Logger instance
        results_saver: Results saver instance

    Returns:
        Dictionary with batch results
    """
    results = {
        "total": len(batch),
        "successful": 0,
        "failed": 0,
        "skipped": 0,
        "found_data": [],
    }

    for registration_number in batch:
        if skip_manager.should_skip(registration_number):
            results["skipped"] += 1
            continue

        result = await crawl_registration_number(
            registration_number, skip_manager, logger
        )
        if result:
            results["successful"] += 1
            results["found_data"].append(registration_number)
            results_saver.add_result(result)
        else:
            results["failed"] += 1

    return results


async def main():
    """Main crawler function"""
    logger = Logger()
    config = Config()

    try:
        logger.info("Starting THPT 2025 Exam Results Crawler...")

        # Initialize web scraper pool
        logger.info("Initializing web scraper pool...")
        await initialize_web_scraper_pool()

        # Initialize components
        generator = RegistrationNumberGenerator()
        skip_manager = CrawlerSkipManager(logger)
        results_saver = ResultsSaver()
        stats = generator.get_stats()

        logger.log_crawler_start(
            stats["total_registration_numbers"], stats["batch_size"]
        )

        # Print crawler statistics
        skip_stats = skip_manager.get_skip_stats()
        logger.info(
            "Crawler Configuration:",
            {
                "total_registration_numbers": stats["total_registration_numbers"],
                "council_codes": stats["council_codes"],
                "batch_size": stats["batch_size"],
                "total_batches": stats["total_batches"],
                "concurrency": config.crawler["concurrency"],
                "target_url": config.target["url"],
                "skip_stats": skip_stats,
                "results_output": results_saver.get_session_info()["session_dir"],
            },
        )

        # Process councils with simple consecutive failure detection
        total_processed = 0
        total_successful = 0
        total_failed = 0
        total_skipped = 0
        last_save_count = 0  # Track when we last saved results

        logger.info("Starting simple crawl with consecutive failure detection...")
        logger.info("Processing all councils (01-65) with 10 consecutive failure limit")
        logger.info("Auto-saving results every 100 successful students")

        try:
            # Process all councils
            for council_num in range(1, 66):  # 01 to 65
                council_code = f"{council_num:02d}"
                logger.info(f"Starting council {council_code}")

                consecutive_failures = 0
                student_number = 1
                council_successful = 0

                # Process this council until 10 consecutive failures
                while consecutive_failures < 10:
                    registration_number = f"{council_code}{student_number:06d}"

                    result = await crawl_registration_number(
                        registration_number, skip_manager, logger
                    )

                    if result:
                        council_successful += 1
                        consecutive_failures = (
                            0  # Reset consecutive failures on success
                        )
                        results_saver.add_result(result)
                        total_successful += 1

                        # Auto-save results every 100 successful students
                        if total_successful - last_save_count >= 100:
                            logger.info(
                                f"Auto-saving results after {total_successful} successful students..."
                            )
                            results_saver.save_all()
                            last_save_count = total_successful
                            logger.info("Auto-save completed")

                    else:
                        consecutive_failures += 1
                        total_failed += 1

                    total_processed += 1
                    student_number += 1

                    # Progress update every 1000 students
                    if student_number % 1000 == 0:
                        logger.info(
                            f"Council {council_code}: Processed {student_number:,} students, Found {council_successful}, Consecutive failures: {consecutive_failures}"
                        )

                # Council completed after 10 consecutive failures
                logger.info(
                    f"Council {council_code} completed: {council_successful} students found after {student_number-1} attempts, stopped after 10 consecutive failures"
                )

                # Save results after each council (and update last save count)
                logger.info(
                    f"Saving results after completing council {council_code}..."
                )
                results_saver.save_all()
                last_save_count = total_successful
                logger.info("Council results saved")

                # Continue to next council (this happens automatically in the for loop)
                if council_num < 65:
                    logger.info(f"Moving to next council {council_num+1:02d}")

            logger.info("All councils (01-65) processed successfully!")

        except KeyboardInterrupt:
            logger.info("Crawler interrupted by user")
            # Save any remaining results
            logger.info("Saving remaining results...")
            results_saver.save_all()
            logger.info("Emergency save completed")
        finally:
            # Always cleanup web scraper pool
            logger.info("Cleaning up web scraper pool...")
            await cleanup_web_scraper_pool()

        # Final save to ensure all data is persisted
        logger.info("Performing final save...")
        results_saver.save_all()
        logger.info("Final save completed")

        # Final statistics
        logger.info(
            "Simple crawler completed",
            {
                "total_processed": total_processed,
                "total_successful": total_successful,
                "total_failed": total_failed,
                "total_skipped": total_skipped,
                "overall_success_rate": f"{(total_successful / max(1, total_processed - total_skipped)) * 100:.1f}%",
                "councils_processed": 65,
            },
        )

        # Save final skip data
        skip_manager.save_all()

        # Display final skip statistics
        final_skip_stats = skip_manager.get_skip_stats()
        logger.info("Final skip statistics:", final_skip_stats)

        # Print results summary
        results_saver.print_summary()

        logger.info("Simple crawler completed successfully!")

    except Exception as error:
        logger.log_error(error)
        # Ensure cleanup on error
        await cleanup_web_scraper_pool()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
