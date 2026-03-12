"""Sensor platform for NEFT Backoffice."""
import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ATTR_TRANSACTION_ID,
    ATTR_PASS_ID,
    ATTR_CHARGING_STATION,
    ATTR_SETTLEMENT_TYPE,
    ATTR_DATE,
    ATTR_TYPE,
    ATTR_KWH,
    ATTR_COST,
    ATTR_HAS_ERROR,
    ATTR_AC_TARIFF_PER_KWH,
    ATTR_AC_TARIFF_PER_SESSION,
    ATTR_AC_TARIFF_PER_HOUR,
    ATTR_DC_TARIFF_PER_KWH,
    ATTR_DC_TARIFF_PER_SESSION,
    ATTR_DC_TARIFF_PER_HOUR,
)
from .coordinator import NEFTDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NEFT Backoffice sensors."""
    coordinator: NEFTDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        NEFTTotalTransactionsSensor(coordinator, entry),
        NEFTNewTransactionsSensor(coordinator, entry),
        NEFTTotalCostSensor(coordinator, entry),
        NEFTTotalEnergySensor(coordinator, entry),
        NEFTACTariffSensor(coordinator, entry),
        NEFTDCTariffSensor(coordinator, entry),
        NEFTLastUpdateSensor(coordinator, entry),
        NEFTCoordinatorStatusSensor(coordinator, entry),
    ]

    async_add_entities(sensors)


class NEFTBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for NEFT sensors."""

    def __init__(
        self,
        coordinator: NEFTDataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"
        self._attr_has_entity_name = True

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": f"NEFT Backoffice ({self._entry.data.get('username')})",
            "manufacturer": "NEFT",
            "model": "Backoffice",
            "sw_version": "1.0",
        }


class NEFTTotalTransactionsSensor(NEFTBaseSensor):
    """Sensor for total number of transactions."""

    def __init__(self, coordinator: NEFTDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "total_transactions")
        self._attr_name = "Total Transactions"
        self._attr_icon = "mdi:counter"
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get("total_transactions", 0)
        return 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}
        
        return {
            "last_update": self.coordinator.data.get("last_update"),
            "consecutive_errors": self.coordinator.consecutive_errors,
        }


class NEFTNewTransactionsSensor(NEFTBaseSensor):
    """Sensor for new transactions since last update."""

    def __init__(self, coordinator: NEFTDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "new_transactions")
        self._attr_name = "New Transactions"
        self._attr_icon = "mdi:new-box"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return len(self.coordinator.data.get("new_transactions", []))
        return 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}
        
        new_transactions = self.coordinator.data.get("new_transactions", [])
        
        # Return details of new transactions
        transactions_list = []
        for trans in new_transactions[:10]:  # Limit to 10 most recent
            columns = trans.get("columns", {})
            transactions_list.append({
                "pass_id": columns.get("0", {}).get("text", ""),
                "date": columns.get("3", {}).get("text", ""),
                "kwh": columns.get("5", {}).get("text", ""),
                "cost": columns.get("6", {}).get("text", ""),
            })
        
        return {
            "transactions": transactions_list,
            "total_new": len(new_transactions),
        }


class NEFTTotalCostSensor(NEFTBaseSensor):
    """Sensor for total cost of all transactions."""

    def __init__(self, coordinator: NEFTDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "total_cost")
        self._attr_name = "Total Cost"
        self._attr_icon = "mdi:currency-eur"
        self._attr_native_unit_of_measurement = CURRENCY_EURO
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return 0.0
        
        transactions = self.coordinator.data.get("transactions", [])
        total_cost = 0.0
        
        for trans in transactions:
            columns = trans.get("columns", {})
            cost_text = columns.get("6", {}).get("text", "0")
            
            # Parse cost (remove currency symbols and convert to float)
            try:
                cost_clean = cost_text.replace("€", "").replace(",", ".").strip()
                total_cost += float(cost_clean)
            except (ValueError, AttributeError):
                continue
        
        return round(total_cost, 2)


class NEFTTotalEnergySensor(NEFTBaseSensor):
    """Sensor for total energy consumed."""

    def __init__(self, coordinator: NEFTDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "total_energy")
        self._attr_name = "Total Energy"
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return 0.0
        
        transactions = self.coordinator.data.get("transactions", [])
        total_kwh = 0.0
        
        for trans in transactions:
            columns = trans.get("columns", {})
            kwh_text = columns.get("5", {}).get("text", "0")
            
            # Parse kWh
            try:
                kwh_clean = kwh_text.replace("kWh", "").replace(",", ".").strip()
                total_kwh += float(kwh_clean)
            except (ValueError, AttributeError):
                continue
        
        return round(total_kwh, 2)


class NEFTACTariffSensor(NEFTBaseSensor):
    """Sensor for AC charging tariff."""

    def __init__(self, coordinator: NEFTDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "ac_tariff")
        self._attr_name = "AC Charging Tariff"
        self._attr_icon = "mdi:ev-station"
        self._attr_native_unit_of_measurement = f"{CURRENCY_EURO}/kWh"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return "Unknown"
        
        tariff_data = self.coordinator.data.get("tariff_data", {})
        charging_types = tariff_data.get("charging_types", [])
        
        for charging_type in charging_types:
            if "AC" in charging_type.get("type", "").upper():
                tariffs = charging_type.get("tariffs", [])
                if tariffs:
                    # Return first tariff's total with VAT
                    return tariffs[0].get("total_with_vat", "Unknown")
        
        return "Unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}
        
        tariff_data = self.coordinator.data.get("tariff_data", {})
        charging_types = tariff_data.get("charging_types", [])
        
        for charging_type in charging_types:
            if "AC" in charging_type.get("type", "").upper():
                tariffs = charging_type.get("tariffs", [])
                
                attrs = {}
                for tariff in tariffs:
                    label = tariff.get("label", "").lower().replace(" ", "_")
                    attrs[f"{label}_base"] = tariff.get("base_value", "0")
                    attrs[f"{label}_fee"] = tariff.get("additional_fee", "0")
                    attrs[f"{label}_total"] = tariff.get("total_with_vat", "0")
                    attrs[f"{label}_country"] = tariff.get("country", "Unknown")
                    attrs[f"{label}_vat"] = tariff.get("vat_percentage", "0")
                
                return attrs
        
        return {}


class NEFTDCTariffSensor(NEFTBaseSensor):
    """Sensor for DC charging tariff."""

    def __init__(self, coordinator: NEFTDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "dc_tariff")
        self._attr_name = "DC Charging Tariff"
        self._attr_icon = "mdi:ev-plug-type2"
        self._attr_native_unit_of_measurement = f"{CURRENCY_EURO}/kWh"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return "Unknown"
        
        tariff_data = self.coordinator.data.get("tariff_data", {})
        charging_types = tariff_data.get("charging_types", [])
        
        for charging_type in charging_types:
            if "DC" in charging_type.get("type", "").upper():
                tariffs = charging_type.get("tariffs", [])
                if tariffs:
                    # Return first tariff's total with VAT
                    return tariffs[0].get("total_with_vat", "Unknown")
        
        return "Unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}
        
        tariff_data = self.coordinator.data.get("tariff_data", {})
        charging_types = tariff_data.get("charging_types", [])
        
        for charging_type in charging_types:
            if "DC" in charging_type.get("type", "").upper():
                tariffs = charging_type.get("tariffs", [])
                
                attrs = {}
                for tariff in tariffs:
                    label = tariff.get("label", "").lower().replace(" ", "_")
                    attrs[f"{label}_base"] = tariff.get("base_value", "0")
                    attrs[f"{label}_fee"] = tariff.get("additional_fee", "0")
                    attrs[f"{label}_total"] = tariff.get("total_with_vat", "0")
                    attrs[f"{label}_country"] = tariff.get("country", "Unknown")
                    attrs[f"{label}_vat"] = tariff.get("vat_percentage", "0")
                
                return attrs
        
        return {}


class NEFTLastUpdateSensor(NEFTBaseSensor):
    """Sensor for last successful update time."""

    def __init__(self, coordinator: NEFTDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "last_update")
        self._attr_name = "Last Update"
        self._attr_icon = "mdi:clock-outline"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get("last_update")
        return None


class NEFTCoordinatorStatusSensor(NEFTBaseSensor):
    """Diagnostic sensor for coordinator status."""

    def __init__(self, coordinator: NEFTDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "coordinator_status")
        self._attr_name = "Coordinator Status"
        self._attr_icon = "mdi:information-outline"
        self._attr_entity_category = "diagnostic"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if self.coordinator.last_update_success:
            return "OK"
        elif self.coordinator.consecutive_errors > 0:
            return f"Error ({self.coordinator.consecutive_errors} consecutive)"
        else:
            return "Unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = {
            "last_update_success": self.coordinator.last_update_success,
            "consecutive_errors": self.coordinator.consecutive_errors,
            "update_interval": str(self.coordinator.update_interval),
        }
        
        if self.coordinator.last_exception:
            attrs["last_error"] = self.coordinator.last_exception
        
        # Add WebDriver info if using Selenium
        if self._entry.data.get(CONF_REMOTE_WEBDRIVER):
            attrs["webdriver_type"] = "remote"
            attrs["webdriver_url"] = self._entry.data.get(CONF_WEBDRIVER_URL, "Unknown")
        else:
            attrs["webdriver_type"] = "local"
        
        return attrs

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True  # Always available to show status