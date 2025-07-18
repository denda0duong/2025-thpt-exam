import asyncio
import json
import time
import logging
from playwright.async_api import async_playwright
from typing import Dict, Optional, List


class WebScraper:
    """Main web scraper class for extracting student exam results"""

    def __init__(self, base_url: str = "https://tuoitre.vn/diem-thi.htm"):
        self.base_url = base_url
        self.playwright = None
        self.browser = None
        self.page = None
        self.context = None

    async def start_browser(self, headless: bool = True):
        """Start the browser and create a new page with optimizations"""
        self.playwright = await async_playwright().start()

        # Launch browser with performance optimizations
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=[
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
        )

        # Create context with optimizations
        self.context = await self.browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        )

        # Create page with resource blocking for speed
        self.page = await self.context.new_page()

        # Block unnecessary resources to speed up loading
        await self.page.route(
            "**/*.{png,jpg,jpeg,gif,svg,webp,ico}", lambda route: route.abort()
        )
        await self.page.route("**/*.{woff,woff2,ttf,otf}", lambda route: route.abort())
        await self.page.route(
            "**/*.{mp4,webm,ogg,mp3,wav,flac,aac}", lambda route: route.abort()
        )
        await self.page.route("**/ads/**", lambda route: route.abort())
        await self.page.route("**/analytics/**", lambda route: route.abort())
        await self.page.route("**/tracking/**", lambda route: route.abort())

    async def close_browser(self):
        """Close the browser and all resources properly"""
        try:
            if self.page:
                await self.page.close()
                self.page = None

            if self.context:
                await self.context.close()
                self.context = None

            if self.browser:
                await self.browser.close()
                self.browser = None

            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
        except Exception as e:
            logging.warning(f"Error closing browser resources: {e}")

    async def navigate_to_page(self) -> bool:
        """Navigate to the target page with fallback strategies"""
        max_retries = 2  # Reduced from 3
        retry_delay = 1  # Reduced from 2 seconds

        for attempt in range(max_retries):
            try:
                # Try different wait strategies based on attempt
                if attempt == 0:
                    # First attempt: use domcontentloaded (faster than networkidle)
                    await self.page.goto(
                        self.base_url, wait_until="domcontentloaded", timeout=15000
                    )
                else:
                    # Second attempt: use load (most reliable)
                    await self.page.goto(
                        self.base_url, wait_until="load", timeout=20000
                    )

                # Very small wait for page to stabilize
                await self.page.wait_for_timeout(500)

                # Verify page loaded by checking for a known element
                try:
                    await self.page.wait_for_selector(
                        'input[name="inputSBD"]', timeout=3000  # Reduced from 5000
                    )
                    logging.debug(  # Changed from info to debug
                        f"Successfully navigated to page on attempt {attempt + 1}"
                    )
                    return True
                except Exception:
                    logging.warning(
                        f"Page loaded but form not found on attempt {attempt + 1}"
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        continue
                    return False

            except Exception as e:
                logging.warning(f"Navigation attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    logging.debug(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                else:
                    logging.error(f"All {max_retries} navigation attempts failed")
                    return False

        return False

    async def fill_form_and_submit(self, registration_number: str) -> bool:
        """Fill the form with registration number and submit - optimized"""
        try:
            # Reduced timeout from 10000ms to 5000ms
            await self.page.wait_for_selector('input[name="inputSBD"]', timeout=5000)

            # Clear and fill the input field
            await self.page.fill('input[name="inputSBD"]', registration_number)

            # Wait for the button to be clickable with reduced timeout
            await self.page.wait_for_selector("button.button-search", timeout=5000)

            # Click the search button
            await self.page.click("button.button-search")

            # Reduced wait time from 3000ms to 1500ms
            await self.page.wait_for_timeout(1500)

            return True

        except Exception as e:
            logging.error(
                f"Failed to fill form and submit for {registration_number}: {e}"
            )
            return False

    async def extract_student_data(self, registration_number: str) -> Optional[Dict]:
        """Extract student data from the page after form submission - optimized"""
        try:
            # Reduced wait time from 3000ms to 1000ms
            await self.page.wait_for_timeout(1000)

            # Check if the student information section exists with reduced timeout
            try:
                user_info_element = await self.page.wait_for_selector(
                    ".user-infor", timeout=2000  # Reduced from 5000ms
                )
                if not user_info_element:
                    logging.debug(
                        f"No user info section found for {registration_number}"
                    )
                    return None
            except Exception:
                logging.debug(f"User info section not found for {registration_number}")
                return None

            # Initialize student data
            student_data = {
                "registration_number": registration_number,
                "timestamp": time.time(),
            }

            # Extract registration number from the page to verify
            try:
                sbd_element = await self.page.query_selector(".user-sbd .sbd")
                if sbd_element:
                    page_sbd = await sbd_element.text_content()
                    if page_sbd and page_sbd.strip() == registration_number:
                        student_data["verified_registration_number"] = page_sbd.strip()
                    else:
                        logging.warning(
                            f"Registration number mismatch: expected {registration_number}, got {page_sbd}"
                        )
            except Exception as e:
                logging.warning(f"Could not verify registration number: {e}")

            # Extract scores from the table
            try:
                scores = {}
                score_rows = await self.page.query_selector_all(
                    ".list-majors-table tbody tr"
                )

                for row in score_rows:
                    cells = await row.query_selector_all("td")
                    if len(cells) >= 2:
                        subject_cell = cells[0]
                        score_cell = cells[1]

                        subject = await subject_cell.text_content()
                        score = await score_cell.text_content()

                        if subject and score:
                            subject_clean = subject.strip()
                            score_clean = score.strip()

                            # Normalize subject names
                            subject_mapping = {
                                "Toán": "Math",
                                "Văn": "Vietnamese",
                                "Hóa học": "Chemistry",
                                "Sinh học": "Biology",
                                "Vật lý": "Physics",
                                "Lịch sử": "History",
                                "Địa lý": "Geography",
                                "Ngoại ngữ": "Foreign Language",
                                "Giáo dục công dân": "Civic Education",
                                "Tin học": "Computer Science",
                                "Kinh tế pháp luật": "Economic and Legal Education",
                                "Công nghệ công nghiệp": "Industrial Technology",
                                "Công nghệ nông nghiệp": "Agricultural Technology",
                                "Tổng điểm": "Total Score",
                            }

                            english_subject = subject_mapping.get(
                                subject_clean, subject_clean
                            )
                            scores[english_subject] = score_clean

                if scores:
                    student_data["scores"] = scores
                    student_data["total_subjects"] = len(
                        [s for s in scores.keys() if s != "Total Score"]
                    )

            except Exception as e:
                logging.error(f"Error extracting scores for {registration_number}: {e}")

            # Try to extract additional student information if available
            try:
                # Look for any additional student details
                info_elements = await self.page.query_selector_all(
                    ".user-infor-box .user-flex"
                )
                for element in info_elements:
                    text = await element.text_content()
                    if text:
                        # You can add more specific extraction logic here
                        pass
            except Exception as e:
                logging.debug(
                    f"No additional info found for {registration_number}: {e}"
                )

            # If we found meaningful data (scores), return it
            if "scores" in student_data and student_data["scores"]:
                logging.info(
                    f"Found {len(student_data['scores'])} scores for {registration_number}"
                )
                return student_data
            else:
                logging.info(f"No scores found for {registration_number}")
                return None

        except Exception as e:
            logging.error(f"Failed to extract data for {registration_number}: {e}")
            return None

    async def scrape_registration_number(
        self, registration_number: str
    ) -> Optional[Dict]:
        """Scrape data for a single registration number"""
        try:
            # Navigate to the page
            if not await self.navigate_to_page():
                return None

            # Fill form and submit
            if not await self.fill_form_and_submit(registration_number):
                return None

            # Extract data
            return await self.extract_student_data(registration_number)

        except Exception as e:
            logging.error(f"Failed to scrape {registration_number}: {e}")
            return None

    async def scrape_multiple_numbers(
        self, registration_numbers: List[str]
    ) -> List[Dict]:
        """Scrape data for multiple registration numbers"""
        results = []

        for reg_num in registration_numbers:
            result = await self.scrape_registration_number(reg_num)
            if result:
                results.append(result)

            # Add delay between requests to avoid being blocked
            await asyncio.sleep(1)

        return results

    async def debug_page_content(self, registration_number: str) -> str:
        """Debug function to see page content after form submission"""
        try:
            await self.navigate_to_page()
            await self.fill_form_and_submit(registration_number)

            # Wait for page to load
            await self.page.wait_for_timeout(3000)

            # Get page content
            content = await self.page.content()

            # Save to file for debugging
            with open(
                f"debug_page_{registration_number}.html", "w", encoding="utf-8"
            ) as f:
                f.write(content)

            return content

        except Exception as e:
            logging.error(f"Debug failed for {registration_number}: {e}")
            return ""


async def main():
    """Main function for testing the scraper"""
    logging.basicConfig(level=logging.INFO)

    scraper = WebScraper()

    try:
        await scraper.start_browser(headless=False)  # Set to True for production

        # Test with a sample registration number
        test_number = "01000001"
        logging.info(f"Testing with registration number: {test_number}")

        # Debug the page content first
        content = await scraper.debug_page_content(test_number)
        logging.info(f"Page content length: {len(content)}")

        # Try to scrape actual data
        result = await scraper.scrape_registration_number(test_number)

        if result:
            logging.info(
                f"Successfully scraped data: {json.dumps(result, indent=2, ensure_ascii=False)}"
            )
        else:
            logging.info("No data found")

    except Exception as e:
        logging.error(f"Main function failed: {e}")

    finally:
        # Ensure proper cleanup
        await scraper.close_browser()
        # Give a moment for cleanup to complete
        await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(main())
