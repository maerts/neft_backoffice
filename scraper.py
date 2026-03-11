"""NEFT Backoffice scraper."""
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time

_LOGGER = logging.getLogger(__name__)


class NEFTBackofficeScraper:
    """NEFT Backoffice scraper class."""

    def __init__(self, username: str, password: str):
        """Initialize scraper."""
        self.username = username
        self.password = password
        self.driver = None
        self.base_url = "https://backoffice.neft.be"

    def setup_driver(self):
        """Initialize the Chrome WebDriver."""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')

        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )

    def login(self):
        """Login to the NEFT backoffice."""
        try:
            _LOGGER.debug("Navigating to login page...")
            self.driver.get(self.base_url)

            wait = WebDriverWait(self.driver, 10)

            username_field = wait.until(
                EC.presence_of_element_located((By.ID, "username"))
            )

            password_field = self.driver.find_element(By.ID, "password")

            username_field.clear()
            username_field.send_keys(self.username)

            password_field.clear()
            password_field.send_keys(self.password)

            login_button = self.driver.find_element(
                By.CSS_SELECTOR, "button[type='submit']"
            )
            login_button.click()

            wait.until(EC.url_changes(self.base_url))
            _LOGGER.info("Login successful!")

            time.sleep(2)

        except Exception as e:
            _LOGGER.error("Login failed: %s", str(e))
            raise

    def scrape_transactions(self) -> list:
        """Scrape transactions from the page."""
        try:
            _LOGGER.debug("Navigating to transactions page...")
            transactions_url = f"{self.base_url}/transactions/charging-transactions"
            self.driver.get(transactions_url)

            wait = WebDriverWait(self.driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "article")))
            time.sleep(2)

            main_article = self.driver.find_element(
                By.CSS_SELECTOR,
                "article.kVYSy1trxThKXaovbq62"
            )

            all_sections = main_article.find_elements(
                By.CSS_SELECTOR,
                "section[data-row][data-column]"
            )

            rows_dict = {}
            for section in all_sections:
                row_id = section.get_attribute("data-row")

                try:
                    if int(row_id) < 0:
                        continue
                except (ValueError, TypeError):
                    continue

                if row_id not in rows_dict:
                    rows_dict[row_id] = {}

                column_id = section.get_attribute("data-column")
                text = section.text.strip()

                # Check for badge
                badge = None
                try:
                    badge_elem = section.find_element(
                        By.CSS_SELECTOR, "span.O66gV6Rd8Wl1xQSGCThg"
                    )
                    badge = badge_elem.text
                except Exception:
                    pass

                # Check for error icon
                has_error = len(
                    section.find_elements(
                        By.CSS_SELECTOR, "svg[data-testid='AlertTriangleIcon']"
                    )
                ) > 0

                rows_dict[row_id][column_id] = {
                    'text': text,
                    'badge': badge,
                    'has_error': has_error
                }

            transactions = []
            for row_id in sorted(rows_dict.keys(), key=lambda x: int(x)):
                transactions.append({
                    'row_id': row_id,
                    'columns': rows_dict[row_id]
                })

            _LOGGER.info("Scraped %d transactions", len(transactions))
            return transactions

        except Exception as e:
            _LOGGER.error("Failed to scrape transactions: %s", str(e))
            raise

    def scrape_tariff_settings(self) -> dict:
        """Scrape tariff settings."""
        try:
            _LOGGER.debug("Navigating to tariff settings...")
            tariff_url = (
                f"{self.base_url}/transactions/charging-transactions/"
                "modal/my-organization/tariff-settings"
            )
            self.driver.get(tariff_url)

            wait = WebDriverWait(self.driver, 10)
            wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "form.qXUbW2RtuEkQMju3svUD")
                )
            )
            time.sleep(2)

            tariff_data = {'charging_types': []}

            charging_containers = self.driver.find_elements(
                By.CSS_SELECTOR,
                "div.llg4uFLgEpc4Sgu7Hg7O.A5njQE8sqxhW7XuV0N0u"
            )

            for container in charging_containers:
                try:
                    charging_type = container.find_element(
                        By.CSS_SELECTOR,
                        "p span[data-color='dark-800']"
                    ).text

                    charging_data = {'type': charging_type, 'tariffs': []}

                    fields = container.find_elements(By.CSS_SELECTOR, "div[id]")

                    for field in fields:
                        if not field.get_attribute("id").isdigit():
                            continue

                        try:
                            label = field.find_element(
                                By.CSS_SELECTOR, "span.VxbcHVn7aSWvryBvYJmS"
                            ).text
                            base_value = field.find_element(
                                By.CSS_SELECTOR, "input[type='number']"
                            ).get_attribute("value")
                            additional_fee = field.find_element(
                                By.CSS_SELECTOR, "div.FVHgg7qUZNhoSYdkE37H"
                            ).text
                            total_with_vat = field.find_element(
                                By.CSS_SELECTOR, "span[data-color='dark-400']"
                            ).text

                            # Get country and VAT info
                            billing_info = field.find_element(
                                By.CSS_SELECTOR, "span.VQGhWGopIJ1ralbppjFT"
                            )
                            billing_spans = billing_info.find_elements(By.TAG_NAME, "span")

                            country = billing_spans[0].text if len(billing_spans) > 0 else "Unknown"
                            vat_pct = billing_spans[1].text if len(billing_spans) > 1 else "0"

                            tariff = {
                                'label': label,
                                'base_value': base_value,
                                'additional_fee': additional_fee,
                                'total_with_vat': total_with_vat,
                                'country': country,
                                'vat_percentage': vat_pct
                            }

                            charging_data['tariffs'].append(tariff)

                        except Exception:
                            continue

                    tariff_data['charging_types'].append(charging_data)

                except Exception:
                    continue

            _LOGGER.info("Scraped tariff data for %d charging types", len(tariff_data['charging_types']))
            return tariff_data

        except Exception as e:
            _LOGGER.error("Failed to scrape tariff settings: %s", str(e))
            raise

    def close(self):
        """Close the browser."""
        if self.driver:
            self.driver.quit()
            _LOGGER.debug("Browser closed")
