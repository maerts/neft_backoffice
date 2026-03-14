"""NEFT Backoffice scraper."""
import logging
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
import time
import re

_LOGGER = logging.getLogger(__name__)


class NEFTBackofficeScraper:
    """NEFT Backoffice scraper class."""

    def __init__(self, username: str, password: str, selenium_url: str, organization_id: str = None):
        """Initialize scraper."""
        self.username = username
        self.password = password
        self.selenium_url = selenium_url
        self.organization_id = organization_id
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
            
            # Extract organization ID if not provided
            if not self.organization_id:
                self._extract_organization_id()

        except Exception as e:
            _LOGGER.error("Login failed: %s", str(e))
            raise

    def _extract_organization_id(self):
        """Extract organization ID from the current page or URL."""
        try:
            wait = WebDriverWait(self.driver, 10)
            
            # Navigate to a page that might contain the org ID
            self.driver.get(f"{self.base_url}/transactions/charging-transactions")
            time.sleep(2)
            
            # Try to extract from local storage
            org_id = self.driver.execute_script(
                "return localStorage.getItem('organizationId') || "
                "sessionStorage.getItem('organizationId');"
            )
            
            if not org_id:
                # Try to find it in the page HTML
                page_source = self.driver.page_source
                match = re.search(r'"organization[Ii]d"\s*:\s*"([a-f0-9]{24})"', page_source)
                if match:
                    org_id = match.group(1)
            
            if not org_id:
                # Try to extract from current URL
                current_url = self.driver.current_url
                match = re.search(r'/organization/([a-f0-9]{24})', current_url)
                if match:
                    org_id = match.group(1)
            
            if org_id:
                self.organization_id = org_id
                _LOGGER.info("Extracted organization ID: %s", org_id)
            else:
                _LOGGER.warning("Could not extract organization ID - API features may be limited")
                
        except Exception as e:
            _LOGGER.warning("Failed to extract organization ID: %s", str(e))

    def scrape_transactions(self, limit: int = 100, offset: int = 0) -> list:
        """Scrape transactions using the API endpoint via Selenium."""
        try:
            wait = WebDriverWait(self.driver, 10)
            _LOGGER.debug("Fetching transactions via API (limit=%d, offset=%d)", limit, offset)
            
            # Build API URL with parameters
            api_url = (
                f"{self.base_url}/api/transaction?"
                f"sort=-startedAt&"
                f"offset={offset}&"
                f"limit={limit}&"
                f"calculate=meterTotal,subtract,meterStop,meterStart&"
                f"postprocess=getVuid&"
                f"populate=user,asset"
            )
            
            # Use Selenium to fetch API data
            script = f"""
                return fetch('{api_url}', {{
                    method: 'GET',
                    credentials: 'include',
                    headers: {{
                        'Accept': 'application/json',
                        'Content-Type': 'application/json'
                    }}
                }})
                .then(response => response.json())
                .then(data => data)
                .catch(error => ({{ error: error.toString() }}));
            """
            
            data = self.driver.execute_script(script)
            
            # Check for errors
            if 'error' in data:
                raise Exception(f"API error: {data['error']}")
            
            transactions = data.get('data', [])
            total = data.get('total', 0)
            
            _LOGGER.info("Fetched %d transactions via API (total available: %d)", len(transactions), total)
            
            # Transform API data to match expected format
            transformed_transactions = []
            for idx, trans in enumerate(transactions):
                transformed = self._transform_api_transaction(trans, offset + idx)
                transformed_transactions.append(transformed)
            
            return transformed_transactions

        except Exception as e:
            _LOGGER.error("API request failed: %s", str(e))
            _LOGGER.info("Falling back to HTML scraping...")
            return self._scrape_transactions_html()

    def _transform_api_transaction(self, api_trans: dict, row_id: int) -> dict:
        """Transform API transaction data to match the expected format."""
        import datetime
        
        wait = WebDriverWait(self.driver, 10)
        
        # Extract relevant fields
        transaction_id = api_trans.get('transactionId', '')
        started_at = api_trans.get('startedAt', '')
        ended_at = api_trans.get('endedAt', '')
        meter_total = api_trans.get('meterTotal', 0)
        
        # Get asset info
        asset = api_trans.get('asset', {})
        asset_serial = asset.get('serial', '') if isinstance(asset, dict) else ''
        
        # Get token info
        token = api_trans.get('token', {})
        ocpi_token = token.get('ocpiToken', {}) if isinstance(token, dict) else {}
        visual_number = ocpi_token.get('visualNumber', '') if isinstance(ocpi_token, dict) else ''
        
        # Get settlement info
        settlement = api_trans.get('settlement', '')
        
        # Calculate kWh (meterTotal is in Wh, convert to kWh)
        kwh = round(meter_total / 1000, 2) if meter_total else 0
        
        # Get tariff info
        tariff = api_trans.get('tariff', {})
        tariff_kwh = tariff.get('kwh', 0) if isinstance(tariff, dict) else 0
        
        # Calculate cost
        cost = round(kwh * tariff_kwh, 2) if kwh and tariff_kwh else 0
        
        # Check for validation errors
        validation = api_trans.get('validation', [])
        has_error = len(validation) > 0 and any('error' in str(v).lower() for v in validation)
        
        # Format dates
        try:
            start_date = datetime.datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            date_str = start_date.strftime('%Y-%m-%d %H:%M')
        except:
            date_str = started_at
        
        # Determine charging type from asset details
        asset_details = asset.get('details', {}) if isinstance(asset, dict) else {}
        power_type = asset_details.get('powerType', 'AC') if isinstance(asset_details, dict) else 'AC'
        charging_type = 'AC' if 'AC' in str(power_type).upper() else 'DC'
        
        # Create columns dict matching the HTML scraping format
        columns = {
            '0': {'text': visual_number or str(transaction_id), 'badge': None, 'has_error': False},
            '1': {'text': asset_serial, 'badge': None, 'has_error': False},
            '2': {'text': settlement.capitalize() if settlement else 'Unknown', 'badge': None, 'has_error': False},
            '3': {'text': date_str, 'badge': None, 'has_error': False},
            '4': {'text': charging_type, 'badge': charging_type, 'has_error': False},
            '5': {'text': f'{kwh} kWh', 'badge': None, 'has_error': False},
            '6': {'text': f'€{cost:.2f}', 'badge': None, 'has_error': has_error},
        }
        
        return {
            'row_id': str(row_id),
            'columns': columns,
            '_raw': api_trans
        }

    def _scrape_transactions_html(self) -> list:
        """Fallback method: Scrape transactions from HTML page."""
        try:
            wait = WebDriverWait(self.driver, 10)
            _LOGGER.debug("Navigating to transactions page...")
            transactions_url = f"{self.base_url}/transactions/charging-transactions"
            self.driver.get(transactions_url)

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

                badge = None
                try:
                    badge_elem = section.find_element(
                        By.CSS_SELECTOR, "span.O66gV6Rd8Wl1xQSGCThg"
                    )
                    badge = badge_elem.text
                except Exception:
                    pass

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

            _LOGGER.info("Scraped %d transactions from HTML", len(transactions))
            return transactions

        except Exception as e:
            _LOGGER.error("Failed to scrape transactions from HTML: %s", str(e))
            raise

    def scrape_tariff_settings(self) -> dict:
        """Scrape tariff settings using API endpoint via Selenium."""
        if not self.organization_id:
            _LOGGER.warning("Organization ID not available, falling back to HTML scraping")
            return self._scrape_tariff_settings_html()
        
        try:
            wait = WebDriverWait(self.driver, 10)
            _LOGGER.debug("Fetching tariff settings via API for org: %s", self.organization_id)
            
            # Build API URL
            api_url = (
                f"{self.base_url}/api/organization/{self.organization_id}?"
                f"postprocess=margin;inheritedResellerTariff;tariff"
            )
            
            # Use Selenium to fetch API data
            script = f"""
                return fetch('{api_url}', {{
                    method: 'GET',
                    credentials: 'include',
                    headers: {{
                        'Accept': 'application/json',
                        'Content-Type': 'application/json'
                    }}
                }})
                .then(response => response.json())
                .then(data => data)
                .catch(error => ({{ error: error.toString() }}));
            """
            
            data = self.driver.execute_script(script)
            
            # Check for errors
            if 'error' in data:
                raise Exception(f"API error: {data['error']}")
            
            # Transform API data to match expected format
            tariff_data = self._transform_api_tariff(data)
            
            _LOGGER.info("Fetched tariff data via API")
            return tariff_data

        except Exception as e:
            _LOGGER.error("API request for tariffs failed: %s", str(e))
            _LOGGER.info("Falling back to HTML scraping for tariffs...")
            return self._scrape_tariff_settings_html()

    def _transform_api_tariff(self, api_data: dict) -> dict:
        """Transform API tariff data to match the expected format."""
        wait = WebDriverWait(self.driver, 10)
        
        resolved_tariff = api_data.get('tariff', {})
        resolved_margin = api_data.get('resolvedMargin', {})
        
        ac_charging = resolved_tariff.get('acCharging', {})
        dc_charging = resolved_tariff.get('dcCharging', {})
        
        ac_margin = resolved_margin.get('acMargin', {})
        dc_margin = resolved_margin.get('dcMargin', {})
        
        currency = resolved_tariff.get('currency', 'EUR')
        country = resolved_tariff.get('country', 'Unknown')
        vat = resolved_tariff.get('vat', 0.21)
        
        tariff_data = {'charging_types': []}
        
        # AC Charging
        ac_tariffs = []
        
        # Per kWh
        ac_kwh_margin = ac_margin.get('kwh', 0.03)
        ac_kwh_base = ac_charging.get('kwh', 0) - ac_kwh_margin
        ac_kwh_total = ac_kwh_base + ac_kwh_margin
        ac_kwh_with_vat = round(ac_kwh_total * (1 + vat), 2)
        
        ac_tariffs.append({
            'label': 'Tariff per kWh (excl. VAT)',
            'base_value': str(ac_kwh_base),
            'additional_fee': f'{ac_kwh_margin:.2f}',
            'total_with_vat': f'{ac_kwh_with_vat:.2f}',
            'country': country,
            'vat_percentage': str(int(vat * 100))
        })
        
        # Per session
        ac_session_base = ac_charging.get('session', 0)
        ac_session_margin = ac_margin.get('session', 0)
        ac_session_total = ac_session_base + ac_session_margin
        ac_session_with_vat = round(ac_session_total * (1 + vat), 2)
        
        ac_tariffs.append({
            'label': 'Tariff per session (excl. VAT)',
            'base_value': str(ac_session_base),
            'additional_fee': f'{ac_session_margin:.2f}',
            'total_with_vat': f'{ac_session_with_vat:.2f}',
            'country': country,
            'vat_percentage': str(int(vat * 100))
        })
        
        # Per hour
        ac_hour_base = ac_charging.get('hour', 0)
        ac_hour_margin = ac_margin.get('hour', 0)
        ac_hour_total = ac_hour_base + ac_hour_margin
        ac_hour_with_vat = round(ac_hour_total * (1 + vat), 2)
        
        ac_tariffs.append({
            'label': 'Tariff per hour (excl. VAT)',
            'base_value': str(ac_hour_base),
            'additional_fee': f'{ac_hour_margin:.2f}',
            'total_with_vat': f'{ac_hour_with_vat:.2f}',
            'country': country,
            'vat_percentage': str(int(vat * 100))
        })
        
        tariff_data['charging_types'].append({
            'type': 'AC Charging',
            'tariffs': ac_tariffs
        })
        
        # DC Charging
        dc_tariffs = []
        
        # Per kWh
        dc_kwh_margin = dc_margin.get('kwh', 0.03)
        dc_kwh_base = dc_charging.get('kwh', 0) - dc_kwh_margin
        dc_kwh_total = dc_kwh_base + dc_kwh_margin
        dc_kwh_with_vat = round(dc_kwh_total * (1 + vat), 2)
        
        dc_tariffs.append({
            'label': 'Tariff per kWh (excl. VAT)',
            'base_value': str(dc_kwh_base),
            'additional_fee': f'{dc_kwh_margin:.2f}',
            'total_with_vat': f'{dc_kwh_with_vat:.2f}',
            'country': country,
            'vat_percentage': str(int(vat * 100))
        })
        
        # Per session
        dc_session_base = dc_charging.get('session', 0)
        dc_session_margin = dc_margin.get('session', 0)
        dc_session_total = dc_session_base + dc_session_margin
        dc_session_with_vat = round(dc_session_total * (1 + vat), 2)
        
        dc_tariffs.append({
            'label': 'Tariff per session (excl. VAT)',
            'base_value': str(dc_session_base),
            'additional_fee': f'{dc_session_margin:.2f}',
            'total_with_vat': f'{dc_session_with_vat:.2f}',
            'country': country,
            'vat_percentage': str(int(vat * 100))
        })
        
        # Per hour
        dc_hour_base = dc_charging.get('hour', 0)
        dc_hour_margin = dc_margin.get('hour', 0)
        dc_hour_total = dc_hour_base + dc_hour_margin
        dc_hour_with_vat = round(dc_hour_total * (1 + vat), 2)
        
        dc_tariffs.append({
            'label': 'Tariff per hour (excl. VAT)',
            'base_value': str(dc_hour_base),
            'additional_fee': f'{dc_hour_margin:.2f}',
            'total_with_vat': f'{dc_hour_with_vat:.2f}',
            'country': country,
            'vat_percentage': str(int(vat * 100))
        })
        
        tariff_data['charging_types'].append({
            'type': 'DC Charging',
            'tariffs': dc_tariffs
        })
        
        return tariff_data

    def _scrape_tariff_settings_html(self) -> dict:
        """Fallback method: Scrape tariff settings from HTML page."""
        try:
            wait = WebDriverWait(self.driver, 10)
            _LOGGER.debug("Navigating to tariff settings...")
            tariff_url = (
                f"{self.base_url}/transactions/charging-transactions/"
                "modal/my-organization/tariff-settings"
            )
            self.driver.get(tariff_url)

            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "form[novalidate]"))
            )
            time.sleep(2)

            tariff_data = {'charging_types': []}

            form = self.driver.find_element(By.CSS_SELECTOR, "form[novalidate]")
            
            charging_containers = form.find_elements(
                By.CSS_SELECTOR, "div[data-clickable='false']"
            )

            for container in charging_containers:
                try:
                    charging_type_elem = container.find_element(
                        By.CSS_SELECTOR, "p > span[data-color='dark-800']"
                    )
                    charging_type = charging_type_elem.text.strip()
                    
                    if not charging_type or "Charging" not in charging_type:
                        continue

                    _LOGGER.debug("Processing charging type: %s", charging_type)
                    charging_data = {'type': charging_type, 'tariffs': []}

                    tariff_fields = container.find_elements(By.CSS_SELECTOR, "div[id]")

                    for field in tariff_fields:
                        field_id = field.get_attribute("id")
                        
                        if not field_id or not field_id.isdigit():
                            continue

                        try:
                            label_spans = field.find_elements(By.TAG_NAME, "span")
                            label = None
                            for span in label_spans:
                                text = span.text.strip()
                                if "Tariff per" in text:
                                    label = text
                                    break
                            
                            if not label:
                                continue

                            input_elem = field.find_element(By.CSS_SELECTOR, "input[type='number']")
                            base_value = input_elem.get_attribute("value")

                            additional_fee = None
                            all_divs = field.find_elements(By.TAG_NAME, "div")
                            for div in all_divs:
                                text = div.text.strip()
                                if text.startswith("+ €"):
                                    additional_fee = text
                                    break

                            billing_spans = field.find_elements(By.TAG_NAME, "span")
                            
                            total_with_vat = None
                            country = "Unknown"
                            vat_pct = "0"
                            
                            for span in billing_spans:
                                text = span.text.strip()
                                
                                if "€" in text and span.get_attribute("data-color") == "dark-400":
                                    total_with_vat = text
                                
                                if "Customers from" in text:
                                    nested_spans = span.find_elements(By.TAG_NAME, "span")
                                    if len(nested_spans) >= 2:
                                        country = nested_spans[0].text.strip()
                                        vat_text = nested_spans[1].text.strip()
                                        vat_pct = vat_text.replace("%", "").strip()

                            tariff = {
                                'label': label,
                                'base_value': base_value or "0",
                                'additional_fee': additional_fee.lstrip("+ €") or "0.00",
                                'total_with_vat': total_with_vat.lstrip("€") or "0.00",
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
            _LOGGER.error("Failed to scrape tariff settings from HTML: %s", str(e))
            raise

    def close(self):
        """Close the browser."""
        if self.driver:
            try:
                self.driver.quit()
                _LOGGER.debug("Browser closed successfully")
            except Exception as e:
                _LOGGER.warning("Error closing browser: %s", str(e))