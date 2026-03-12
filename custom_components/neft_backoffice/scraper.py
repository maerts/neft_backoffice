
"""NEFT Backoffice scraper."""
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
import time

_LOGGER = logging.getLogger(__name__)


class NEFTBackofficeScraper:
    """NEFT Backoffice scraper class."""

    def __init__(self, username: str, password: str, selenium_url: str):
        """Initialize scraper."""
        self.username = username
        self.password = password
        self.selenium_url = selenium_url
        self.driver = None
        self.base_url = "https://backoffice.neft.be"

    def setup_driver(self):
        """Initialize the Remote Chrome WebDriver."""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        # Additional options for stability
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        try:
            _LOGGER.debug("Connecting to remote Selenium at %s", self.selenium_url)
            self.driver = webdriver.Remote(
                command_executor=self.selenium_url,
                options=options
            )
            _LOGGER.info("Successfully connected to remote Selenium")
        except WebDriverException as e:
            _LOGGER.error("Failed to connect to remote Selenium: %s", str(e))
            raise ConnectionError(f"Cannot connect to Selenium at {self.selenium_url}") from e

    def login(self):
        """Login to the NEFT backoffice."""
        try:
            _LOGGER.debug("Navigating to login page...")
            self.driver.get(self.base_url)

            wait = WebDriverWait(self.driver, 10)

            username_field = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']"))
            )

            password_field = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")

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
        """Scrape transactions using structure-based selectors."""
        try:
            _LOGGER.debug("Navigating to transactions page...")
            transactions_url = f"{self.base_url}/transactions/charging-transactions"
            self.driver.get(transactions_url)
            
            wait = WebDriverWait(self.driver, 20)
            
            # Wait for main content to load
            time.sleep(3)
            
            _LOGGER.info("Looking for transaction table by structure...")
            
            # Find the main article element containing the transaction table
            # Structure: article containing multiple section elements with data-row and data-column
            articles = self.driver.find_elements(By.TAG_NAME, "article")
            
            main_article = None
            for article in articles:
                # Check if this article contains sections with data-row and data-column attributes
                sections = article.find_elements(By.CSS_SELECTOR, "section[data-row][data-column]")
                if len(sections) > 10:  # Transaction table should have many sections
                    main_article = article
                    _LOGGER.info(f"Found transaction table with {len(sections)} sections")
                    break
            
            if not main_article:
                _LOGGER.warning("Transaction table not found by structure")
                return []
            
            # Find all sections with data-row and data-column attributes
            all_sections = main_article.find_elements(By.CSS_SELECTOR, "section[data-row][data-column]")
            _LOGGER.info(f"Found {len(all_sections)} section elements")
            
            # Group sections by row
            rows_dict = {}
            header_columns = {}
            
            for section in all_sections:
                row_id = section.get_attribute("data-row")
                column_id = section.get_attribute("data-column")
                
                # Handle header row (row_id = "-1")
                if row_id == "-1":
                    # Extract header text from span
                    try:
                        header_span = section.find_element(By.TAG_NAME, "span")
                        header_text = header_span.text.strip()
                        header_columns[column_id] = header_text
                        _LOGGER.debug(f"Header column {column_id}: {header_text}")
                    except Exception:
                        pass
                    continue
                
                # Skip if row_id is not a valid positive number
                try:
                    if int(row_id) < 0:
                        continue
                except (ValueError, TypeError):
                    continue
                
                # Initialize row if not exists
                if row_id not in rows_dict:
                    rows_dict[row_id] = {}
                
                # Extract text from span within section
                text = ""
                try:
                    # Look for span elements (main content)
                    spans = section.find_elements(By.TAG_NAME, "span")
                    for span in spans:
                        span_text = span.text.strip()
                        if span_text:
                            # Take the longest text (to get full content, not just badges)
                            if len(span_text) > len(text):
                                text = span_text
                except Exception:
                    text = section.text.strip()
                
                # Check for badge/type indicator (colored span)
                badge = None
                badge_color = None
                try:
                    # Look for nested span elements that might be badges
                    # Badges typically have background-color style
                    badge_containers = section.find_elements(By.XPATH, ".//span[@style]")
                    for container in badge_containers:
                        style = container.get_attribute("style")
                        if "background-color" in style:
                            # This is likely a badge container
                            badge_spans = container.find_elements(By.TAG_NAME, "span")
                            for badge_span in badge_spans:
                                badge_text = badge_span.text.strip()
                                if badge_text and badge_text != text:
                                    badge = badge_text
                                    # Extract color from style
                                    if "error" in style:
                                        badge_color = "error"
                                    elif "info" in style:
                                        badge_color = "info"
                                    elif "success" in style:
                                        badge_color = "success"
                                    elif "warning" in style:
                                        badge_color = "warning"
                                    break
                except Exception:
                    pass
                
                # Check for error/warning icon (SVG with AlertTriangleIcon)
                has_error = False
                try:
                    svgs = section.find_elements(By.TAG_NAME, "svg")
                    for svg in svgs:
                        test_id = svg.get_attribute("data-testid")
                        if test_id and "alert" in test_id.lower():
                            has_error = True
                            break
                except Exception:
                    pass
                
                # Check if row is expandable (has button)
                is_expandable = False
                try:
                    buttons = section.find_elements(By.TAG_NAME, "button")
                    if buttons:
                        is_expandable = True
                except Exception:
                    pass
                
                # Store column data
                rows_dict[row_id][column_id] = {
                    'text': text,
                    'badge': badge,
                    'badge_color': badge_color,
                    'has_error': has_error,
                    'is_expandable': is_expandable
                }
            
            # Convert to list of transactions with meaningful field names
            transactions = []
            for row_id in sorted(rows_dict.keys(), key=lambda x: int(x)):
                row_data = rows_dict[row_id]
                
                # Map columns to meaningful names based on typical structure
                # Column 0: Pass ID / Name
                # Column 1: Charging Station
                # Column 2: Settlement Type
                # Column 3: Date
                # Column 4: Type (Roaming/Unauthorized/etc)
                # Column 5: kWh
                # Column 6: Cost
                # Column 7: Error indicator
                
                transaction = {
                    'row_id': row_id,
                    'columns': row_data,
                    # Add parsed fields for easier access
                    'pass_id': row_data.get('0', {}).get('text', ''),
                    'charging_station': row_data.get('1', {}).get('text', ''),
                    'settlement_type': row_data.get('2', {}).get('text', ''),
                    'date': row_data.get('3', {}).get('text', ''),
                    'type': row_data.get('4', {}).get('badge', row_data.get('4', {}).get('text', '')),
                    'type_color': row_data.get('4', {}).get('badge_color', ''),
                    'kwh': row_data.get('5', {}).get('text', ''),
                    'cost': row_data.get('6', {}).get('text', ''),
                    'has_error': row_data.get('7', {}).get('has_error', False) or row_data.get('6', {}).get('has_error', False),
                }
                
                transactions.append(transaction)
            
            _LOGGER.info(f"Scraped {len(transactions)} transactions")
            
            # Log sample transaction for debugging
            if transactions:
                _LOGGER.debug(f"Sample transaction: {transactions[0]}")
            
            return transactions
            
        except Exception as e:
            _LOGGER.error(f"Failed to scrape transactions: {str(e)}", exc_info=True)
            raise

    def scrape_tariff_settings(self) -> dict:
        """Scrape tariff settings using structure-based approach."""
        try:
            _LOGGER.debug("Navigating to tariff settings...")
            tariff_url = (
                f"{self.base_url}/transactions/charging-transactions/"
                "modal/my-organization/tariff-settings"
            )
            self.driver.get(tariff_url)

            wait = WebDriverWait(self.driver, 10)
            # Wait for form to be present
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "form[novalidate]"))
            )
            time.sleep(2)

            tariff_data = {'charging_types': []}

            # Find all charging type containers by looking for <p> tags with charging type text
            # These are siblings of the tariff field containers
            form = self.driver.find_element(By.CSS_SELECTOR, "form[novalidate]")
            
            # Find all divs that have data-clickable="false" attribute
            # These are the main containers for each charging type
            charging_containers = form.find_elements(
                By.CSS_SELECTOR, "div[data-clickable='false']"
            )

            for container in charging_containers:
                try:
                    # Find the charging type name - look for <p> tag with nested span
                    charging_type_elem = container.find_element(
                        By.CSS_SELECTOR, "p > span[data-color='dark-800']"
                    )
                    charging_type = charging_type_elem.text.strip()
                    
                    # Skip if no charging type found or if it's not AC/DC Charging
                    if not charging_type or "Charging" not in charging_type:
                        continue

                    _LOGGER.debug("Processing charging type: %s", charging_type)
                    charging_data = {'type': charging_type, 'tariffs': []}

                    # Find all tariff field containers - divs with numeric IDs
                    tariff_fields = container.find_elements(By.CSS_SELECTOR, "div[id]")

                    for field in tariff_fields:
                        field_id = field.get_attribute("id")
                        
                        # Only process numeric IDs
                        if not field_id or not field_id.isdigit():
                            continue

                        try:
                            # Get the label (e.g., "Tariff per kWh (excl. VAT)")
                            # Look for span that contains the label text
                            label_spans = field.find_elements(By.TAG_NAME, "span")
                            label = None
                            for span in label_spans:
                                text = span.text.strip()
                                if "Tariff per" in text:
                                    label = text
                                    break
                            
                            if not label:
                                _LOGGER.debug("No label found for field %s", field_id)
                                continue

                            # Get the base value from input field
                            input_elem = field.find_element(By.CSS_SELECTOR, "input[type='number']")
                            base_value = input_elem.get_attribute("value")

                            # Get the additional fee - look for div containing "+ €"
                            additional_fee = None
                            all_divs = field.find_elements(By.TAG_NAME, "div")
                            for div in all_divs:
                                text = div.text.strip()
                                if text.startswith("+ €"):
                                    additional_fee = text.lstrip("+ €")
                                    break

                            # Get total with VAT and billing info
                            # Look for span elements within the billing info section
                            billing_spans = field.find_elements(By.TAG_NAME, "span")
                            
                            total_with_vat = None
                            country = "Unknown"
                            vat_pct = "0"
                            
                            for i, span in enumerate(billing_spans):
                                text = span.text.strip()
                                
                                # Look for the total with VAT (contains € and is highlighted)
                                if "€" in text and span.get_attribute("data-color") == "dark-400":
                                    total_with_vat = text.lstrip("€")
                                
                                # Look for "Customers from" to find country
                                if "Customers from" in text:
                                    # Next spans should contain country and VAT
                                    nested_spans = span.find_elements(By.TAG_NAME, "span")
                                    if len(nested_spans) >= 2:
                                        country = nested_spans[0].text.strip()
                                        vat_text = nested_spans[1].text.strip()
                                        # Extract percentage from text like "21"
                                        vat_pct = vat_text.replace("%", "").strip()

                            tariff = {
                                'label': label,
                                'base_value': base_value or "0",
                                'additional_fee': additional_fee or "0.00",
                                'total_with_vat': total_with_vat or "0.00",
                                'country': country,
                                'vat_percentage': vat_pct
                            }

                            charging_data['tariffs'].append(tariff)
                            _LOGGER.debug("Parsed tariff: %s = %s", label, total_with_vat)

                        except Exception as e:
                            _LOGGER.debug("Failed to parse tariff field %s: %s", field_id, str(e))
                            continue

                    if charging_data['tariffs']:
                        tariff_data['charging_types'].append(charging_data)

                except Exception as e:
                    _LOGGER.debug("Failed to parse charging container: %s", str(e))
                    continue

            _LOGGER.info("Scraped tariff data for %d charging types", len(tariff_data['charging_types']))
            return tariff_data

        except Exception as e:
            _LOGGER.error("Failed to scrape tariff settings: %s", str(e))
            raise

    def close(self):
        """Close the browser."""
        if self.driver:
            try:
                self.driver.quit()
                _LOGGER.debug("Browser closed successfully")
            except Exception as e:
                _LOGGER.warning("Error closing browser: %s", str(e))