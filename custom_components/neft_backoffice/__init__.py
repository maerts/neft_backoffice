"""The NEFT Backoffice integration."""
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import DOMAIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
from .coordinator import NEFTDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

# Service schemas
SERVICE_REFRESH_DATA = "refresh_data"
SERVICE_CLEAR_TRANSACTIONS = "clear_transactions"

SERVICE_REFRESH_SCHEMA = vol.Schema({})
SERVICE_CLEAR_SCHEMA = vol.Schema({})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NEFT Backoffice from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Get scan interval from options or use default
    scan_interval_minutes = entry.options.get(
        CONF_SCAN_INTERVAL,
        DEFAULT_SCAN_INTERVAL.total_seconds() / 60
    )
    update_interval = timedelta(minutes=scan_interval_minutes)

    _LOGGER.info(
        "Setting up NEFT Backoffice for %s with update interval: %s minutes",
        entry.data.get("username"),
        scan_interval_minutes
    )

    # Create coordinator
    coordinator = NEFTDataUpdateCoordinator(
        hass,
        entry,
        update_interval=update_interval,
    )

    # Fetch initial data
    try:
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.info("Initial data fetch successful")
    except Exception as err:
        _LOGGER.error("Failed to fetch initial data: %s", err)
        # Don't fail setup, let it retry on next update
        pass

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Setup options update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Register services
    async def handle_refresh_data(call: ServiceCall) -> None:
        """Handle the refresh_data service call."""
        _LOGGER.info("Refresh data service called")
        await coordinator.async_request_refresh()

    async def handle_clear_transactions(call: ServiceCall) -> None:
        """Handle the clear_transactions service call."""
        _LOGGER.info("Clear transactions service called")
        coordinator._stored_transactions.clear()
        await coordinator.async_request_refresh()

    # Register services only once
    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH_DATA):
        hass.services.async_register(
            DOMAIN,
            SERVICE_REFRESH_DATA,
            handle_refresh_data,
            schema=SERVICE_REFRESH_SCHEMA,
        )
        _LOGGER.debug("Registered refresh_data service")

    if not hass.services.has_service(DOMAIN, SERVICE_CLEAR_TRANSACTIONS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEAR_TRANSACTIONS,
            handle_clear_transactions,
            schema=SERVICE_CLEAR_SCHEMA,
        )
        _LOGGER.debug("Registered clear_transactions service")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading NEFT Backoffice integration")
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        
        # Clean up coordinator resources
        if hasattr(coordinator, '_stored_transactions'):
            coordinator._stored_transactions.clear()
        
        _LOGGER.info("NEFT Backoffice integration unloaded successfully")

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    _LOGGER.info("Reloading NEFT Backoffice integration")
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)