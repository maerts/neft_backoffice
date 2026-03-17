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

    # Add asset sensors dynamically (NEW)
    if coordinator.data and "assets_status" in coordinator.data:
        for asset in coordinator.data["assets_status"]:
            asset_id = asset.get("asset_id")
            if asset_id:
                sensors.append(NEFTAssetStatusSensor(coordinator, entry, asset_id))
                sensors.append(NEFTAssetConnectorSensor(coordinator, entry, asset_id))

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
                # Remove "kWh" suffix and clean up
                kwh_clean = kwh_text.replace("kWh", "").replace(",", ".").strip()
                kwh_value = float(kwh_clean)
                # Only add positive values
                if kwh_value > 0:
                    total_kwh += kwh_value
                else:
                    _LOGGER.debug("Skipping negative kWh value: %s", kwh_text)
            except (ValueError, AttributeError) as e:
                _LOGGER.debug("Failed to parse kWh '%s': %s", kwh_text, e)
                continue
        
        # Ensure we never return negative
        result = max(0.0, round(total_kwh, 2))
        return result


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
        else:
            return "Unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = {
            "last_update_success": self.coordinator.last_update_success,
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
        
class NEFTAssetStatusSensor(NEFTBaseSensor):
    """Sensor for charging station status."""

    def __init__(
        self, 
        coordinator: NEFTDataUpdateCoordinator, 
        entry: ConfigEntry,
        asset_id: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, f"asset_{asset_id}_status")
        self._asset_id = asset_id
        self._attr_icon = "mdi:ev-station"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        asset_data = self._get_asset_data()
        if asset_data:
            alias = asset_data.get("alias", "")
            serial = asset_data.get("serial", "")
            return f"{alias or serial} Status"
        return f"Asset {self._asset_id} Status"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        asset_data = self._get_asset_data()
        if asset_data:
            return asset_data.get("connection_status", "Unknown")
        return "Unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        asset_data = self._get_asset_data()
        if not asset_data:
            return {}
        
        details = asset_data.get("details", {})
        
        return {
            "serial": asset_data.get("serial"),
            "alias": asset_data.get("alias"),
            "management_status": asset_data.get("management_status"),
            "last_contact": asset_data.get("last_contact"),
            "firmware": asset_data.get("firmware"),
            "model": asset_data.get("model"),
            "vendor": asset_data.get("vendor"),
            "protocol_version": asset_data.get("protocol_version"),
            "max_amps": details.get("max_amps"),
            "voltage": details.get("voltage"),
            "phase_count": details.get("phase_count"),
            "power_type": details.get("power_type"),
            "connector_type": details.get("connector_type"),
            "communication_type": details.get("communication_type"),
        }

    def _get_asset_data(self) -> dict | None:
        """Get asset data from coordinator."""
        if not self.coordinator.data:
            return None
        
        assets = self.coordinator.data.get("assets_status", [])
        for asset in assets:
            if asset.get("asset_id") == self._asset_id:
                return asset
        
        return None


class NEFTAssetConnectorSensor(NEFTBaseSensor):
    """Sensor for charging station connector status."""

    def __init__(
        self, 
        coordinator: NEFTDataUpdateCoordinator, 
        entry: ConfigEntry,
        asset_id: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, f"asset_{asset_id}_connectors")
        self._asset_id = asset_id
        self._attr_icon = "mdi:ev-plug-type2"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        asset_data = self._get_asset_data()
        if asset_data:
            alias = asset_data.get("alias", "")
            serial = asset_data.get("serial", "")
            return f"{alias or serial} Connectors"
        return f"Asset {self._asset_id} Connectors"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        asset_data = self._get_asset_data()
        if not asset_data:
            return "Unknown"
        
        connectors = asset_data.get("connectors", {})
        if not connectors:
            return "No connectors"
        
        # Return status of first connector or summary
        statuses = list(connectors.values())
        if len(statuses) == 1:
            return statuses[0]
        
        # Multiple connectors - return summary
        charging_count = sum(1 for s in statuses if s == "Charging")
        if charging_count > 0:
            return f"Charging ({charging_count}/{len(statuses)})"
        
        available_count = sum(1 for s in statuses if s == "Available")
        if available_count == len(statuses):
            return "Available"
        
        return "Mixed"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        asset_data = self._get_asset_data()
        if not asset_data:
            return {}
        
        connectors = asset_data.get("connectors", {})
        
        attrs = {
            "connector_count": len(connectors),
        }
        
        # Add individual connector statuses
        for connector_id, status in connectors.items():
            attrs[f"connector_{connector_id}"] = status
        
        return attrs

    def _get_asset_data(self) -> dict | None:
        """Get asset data from coordinator."""
        if not self.coordinator.data:
            return None
        
        assets = self.coordinator.data.get("assets_status", [])
        for asset in assets:
            if asset.get("asset_id") == self._asset_id:
                return asset
        
        return None