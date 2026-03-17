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

        except Exception as e:
            _LOGGER.error("Login failed: %s", str(e))
            raise

def scrape_transactions(self, limit: int = 100, offset: int = 0, fetch_all: bool = True) -> list:
    """Scrape transactions using the API endpoint via Selenium with pagination support."""
    try:
        wait = WebDriverWait(self.driver, 10)
        
        # First, get total count by querying with high offset
        _LOGGER.debug("Fetching transaction count...")
        count_url = (
            f"{self.base_url}/api/transaction?"
            f"limit=20&"
            f"offset=999999&"
            f"sort=-endedAt"
        )
        
        count_script = f"""
            return fetch('{count_url}', {{
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
        
        count_data = self.driver.execute_script(count_script)
        
        if 'error' in count_data:
            raise Exception(f"API error getting count: {count_data['error']}")
        
        total_transactions = count_data.get('total', 0)
        total_pages = count_data.get('pages', 0)
        
        _LOGGER.info("Found %d total transactions across %d pages", total_transactions, total_pages)
        
        if not fetch_all:
            # Fetch only one page
            return self._fetch_transaction_page(limit, offset)
        
        # Fetch all pages
        all_transactions = []
        current_offset = 0
        page_limit = 100  # Fetch 100 transactions per page for efficiency
        
        while current_offset < total_transactions:
            _LOGGER.debug("Fetching page at offset %d", current_offset)
            page_transactions = self._fetch_transaction_page(page_limit, current_offset)
            
            if not page_transactions:
                break
            
            all_transactions.extend(page_transactions)
            current_offset += page_limit
            
            # Safety check to avoid infinite loops
            if len(all_transactions) >= total_transactions:
                break
        
        _LOGGER.info("Successfully fetched %d transactions", len(all_transactions))
        return all_transactions

    except Exception as e:
        _LOGGER.error("Transaction scraping failed: %s", str(e))
        raise

def _fetch_transaction_page(self, limit: int, offset: int) -> list:
    """Fetch a single page of transactions."""
    try:
        api_url = (
            f"{self.base_url}/api/transaction?"
            f"sort=-endedAt&"
            f"offset={offset}&"
            f"limit={limit}&"
            f"calculate=meterTotal,subtract,meterStop,meterStart&"
            f"postprocess=getVuid&"
            f"populate=user,asset"
        )
        
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
        
        if 'error' in data:
            raise Exception(f"API error: {data['error']}")
        
        transactions = data.get('data', [])
        
        # Transform API data to match expected format
        transformed_transactions = []
        for idx, trans in enumerate(transactions):
            transformed = self._transform_api_transaction(trans, offset + idx)
            transformed_transactions.append(transformed)
        
        return transformed_transactions

    except Exception as e:
        _LOGGER.error("Failed to fetch transaction page: %s", str(e))
        raise

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

    def scrape_tariff_settings(self) -> dict:
        """Scrape tariff settings using API endpoint via Selenium."""
        if not self.organization_id:
            _LOGGER.error("Organization ID not available, please configure it correctly in the settings page.")
            raise
        
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
            raise

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

    def scrape_asset_status(self, asset_id: str) -> dict:
        """Scrape asset status using API endpoint via Selenium."""
        try:
            wait = WebDriverWait(self.driver, 10)
            _LOGGER.debug("Fetching asset status for asset: %s", asset_id)
            
            # Build API URL
            api_url = f"{self.base_url}/api/v2/asset/active/{asset_id}"
            
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
            
            _LOGGER.info("Fetched asset status for %s", asset_id)
            return self._transform_asset_status(data)

        except Exception as e:
            _LOGGER.error("Failed to fetch asset status: %s", str(e))
            raise

    def _transform_asset_status(self, api_data: dict) -> dict:
        """Transform API asset data to a structured format."""
        details = api_data.get('details', {})
        connectors = details.get('connectors', {})
        
        # Extract connector statuses
        connector_statuses = {}
        for connector_id, connector_data in connectors.items():
            connector_statuses[connector_id] = connector_data.get('status', 'Unknown')
        
        return {
            'asset_id': api_data.get('_id'),
            'serial': api_data.get('serial'),
            'alias': api_data.get('alias'),
            'connection_status': api_data.get('connectionStatus', 'Unknown'),
            'management_status': api_data.get('managementStatus', 'Unknown'),
            'last_contact': api_data.get('lastContact'),
            'firmware': api_data.get('firmware'),
            'model': api_data.get('model'),
            'vendor': api_data.get('vendor'),
            'protocol_version': api_data.get('protocolVersion'),
            'details': {
                'max_amps': details.get('maxAmps'),
                'max_amps_per_socket': details.get('maxAmpsPerSocket'),
                'phase_count': details.get('phaseCount'),
                'voltage': details.get('voltage'),
                'connector_type': details.get('connectorType'),
                'communication_type': details.get('communicationType'),
                'power_type': details.get('powerType'),
            },
            'connectors': connector_statuses,
            'tariff': api_data.get('tariff', {}),
        }

    def scrape_all_assets(self) -> list:
        """Scrape all active assets from transactions."""
        try:
            _LOGGER.debug("Extracting asset IDs from transactions")
            
            # Get transactions to extract asset IDs
            transactions = self.scrape_transactions(limit=100)
            
            # Extract unique asset IDs
            asset_ids = set()
            for trans in transactions:
                if '_raw' in trans:
                    asset = trans['_raw'].get('asset', {})
                    if isinstance(asset, dict):
                        asset_id = asset.get('_id')
                        if asset_id:
                            asset_ids.add(asset_id)
            
            _LOGGER.info("Found %d unique assets", len(asset_ids))
            
            # Fetch status for each asset
            assets_status = []
            for asset_id in asset_ids:
                try:
                    status = self.scrape_asset_status(asset_id)
                    assets_status.append(status)
                except Exception as e:
                    _LOGGER.warning("Failed to fetch status for asset %s: %s", asset_id, str(e))
                    continue
            
            return assets_status

        except Exception as e:
            _LOGGER.error("Failed to scrape assets: %s", str(e))
            return []

            
    def close(self):
        """Close the browser."""
        if self.driver:
            try:
                self.driver.quit()
                _LOGGER.debug("Browser closed successfully")
            except Exception as e:
                _LOGGER.warning("Error closing browser: %s", str(e))