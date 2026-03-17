
"""Config flow for NEFT Backoffice integration."""
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_SCAN_INTERVAL,
    CONF_SELENIUM_URL,
    CONF_ORGANIZATION_ID,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SELENIUM_URL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_SELENIUM_URL, default=DEFAULT_SELENIUM_URL): str,
        vol.Required(CONF_ORGANIZATION_ID): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    from .scraper import NEFTBackofficeScraper

    def _test_connection():
        """Test connection in executor."""
        scraper = NEFTBackofficeScraper(
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            data[CONF_SELENIUM_URL],
            data[CONF_ORGANIZATION_ID]
        )
        try:
            scraper.setup_driver()
            scraper.login()

            return True
        except Exception as err:
            _LOGGER.error("Connection test failed: %s", err)
            raise
        finally:
            scraper.close()

    try:
        await hass.async_add_executor_job(_test_connection)
    except Exception as err:
        raise ValueError("Cannot connect") from err

    return {"title": f"NEFT Backoffice ({data[CONF_USERNAME]})"}


class NEFTConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NEFT Backoffice."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except ValueError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return NEFTOptionsFlowHandler(config_entry)


class NEFTOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for NEFT Backoffice."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self._config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL.total_seconds() / 60
                        ),
                    ): vol.All(
                        cv.positive_int,
                        vol.Range(
                            min=MIN_SCAN_INTERVAL.total_seconds() / 60,
                            msg=f"Minimum scan interval is {MIN_SCAN_INTERVAL.total_seconds() / 60} minutes",
                        ),
                    ),
                    vol.Optional(
                        CONF_SELENIUM_URL,
                        default=self._config_entry.data.get(
                            CONF_SELENIUM_URL, DEFAULT_SELENIUM_URL
                        ),
                    ): str,
                }
            ),
        )