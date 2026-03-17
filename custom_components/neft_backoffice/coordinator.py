"""DataUpdateCoordinator for NEFT Backoffice."""
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, CONF_SELENIUM_URL, CONF_ORGANIZATION_ID
from .scraper import NEFTBackofficeScraper

_LOGGER = logging.getLogger(__name__)


class NEFTDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching NEFT data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        update_interval: timedelta,
    ) -> None:
        """Initialize."""
        self.entry = entry
        self.scraper = None
        self._stored_transactions = {}

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from NEFT Backoffice."""
        try:
            username = self.entry.data[CONF_USERNAME]
            password = self.entry.data[CONF_PASSWORD]
            selenium_url = self.entry.data.get(CONF_SELENIUM_URL)
            organization_id = self.entry.data.get(CONF_ORGANIZATION_ID)
            
            # Use updated values from options if available
            if CONF_SELENIUM_URL in self.entry.options:
                selenium_url = self.entry.options[CONF_SELENIUM_URL]
            if CONF_ORGANIZATION_ID in self.entry.options:
                organization_id = self.entry.options[CONF_ORGANIZATION_ID]

            # Run scraper in executor to avoid blocking
            data = await self.hass.async_add_executor_job(
                self._scrape_data, username, password, selenium_url, organization_id
            )

            return data

        except Exception as err:
            _LOGGER.error("Error fetching NEFT data: %s", err)
            raise UpdateFailed(f"Error communicating with NEFT: {err}") from err

    def _scrape_data(
        self, 
        username: str, 
        password: str, 
        selenium_url: str,
        organization_id: str = None
    ) -> dict[str, Any]:
        """Scrape data from NEFT (runs in executor)."""
        try:
            scraper = NEFTBackofficeScraper(username, password, selenium_url, organization_id)
            scraper.setup_driver()
            scraper.login()
    
            # Scrape transactions
            transactions = scraper.scrape_transactions()
    
            # Scrape tariff settings
            tariff_data = scraper.scrape_tariff_settings()
    
            # Scrape asset status (NEW)
            assets_status = scraper.scrape_all_assets()
    
            scraper.close()
    
            # Process transactions - only keep new ones
            new_transactions = []
            for transaction in transactions:
                trans_id = self._create_transaction_id(transaction)
                
                if trans_id not in self._stored_transactions:
                    self._stored_transactions[trans_id] = transaction
                    new_transactions.append(transaction)
    
            # Limit stored transactions to last 1000
            if len(self._stored_transactions) > 1000:
                sorted_ids = sorted(
                    self._stored_transactions.keys(),
                    key=lambda x: self._stored_transactions[x].get('row_id', '0'),
                    reverse=True
                )
                self._stored_transactions = {
                    k: self._stored_transactions[k]
                    for k in sorted_ids[:1000]
                }
    
            return {
                "transactions": list(self._stored_transactions.values()),
                "new_transactions": new_transactions,
                "tariff_data": tariff_data,
                "assets_status": assets_status,  # NEW
                "total_transactions": len(self._stored_transactions),
            }
    
        except Exception as err:
            _LOGGER.error("Scraping error: %s", err)
            raise

    def _create_transaction_id(self, transaction: dict) -> str:
        """Create a unique ID for a transaction."""
        columns = transaction.get('columns', {})
        
        # Use combination of pass_id, date, kwh, and cost as unique identifier
        pass_id = columns.get('0', {}).get('text', '')
        date = columns.get('3', {}).get('text', '')
        kwh = columns.get('5', {}).get('text', '')
        cost = columns.get('6', {}).get('text', '')
        
        return f"{pass_id}_{date}_{kwh}_{cost}".replace(' ', '_')