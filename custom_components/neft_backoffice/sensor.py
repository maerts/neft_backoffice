"""Sensor platform for NEFT Backoffice."""
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
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

    entities = [
        NEFTTransactionCountSensor(coordinator, entry),
        NEFTNewTransactionsSensor(coordinator, entry),
        NEFTTotalCostSensor(coordinator, entry),
        NEFTTotalEnergyConsumptionSensor(coordinator, entry),
        NEFTACTariffSensor(coordinator, entry),
        NEFTDCTariffSensor(coordinator, entry),
    ]

    async_add_entities(entities)


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


class NEFTTransactionCountSensor(NEFTBaseSensor):
    """Sensor for total transaction count."""

    def __init__(
        self,
        coordinator: NEFTDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "transaction_count")
        self._attr_name = "Total Transactions"
        self._attr_icon = "mdi:counter"
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self.coordinator.data.get("total_transactions", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        return {
            "last_update": self.coordinator.last_update_success_time,
        }


class NEFTNewTransactionsSensor(NEFTBaseSensor):
    """Sensor for new transactions since last update."""

    def __init__(
        self,
        coordinator: NEFTDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "new_transactions")
        self._attr_name = "New Transactions"
        self._attr_icon = "mdi:new-box"

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return len(self.coordinator.data.get("new_transactions", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        new_transactions = self.coordinator.data.get("new_transactions", [])

        # Format new transactions for attributes
        transactions_list = []
        for trans in new_transactions[:10]:  # Limit to 10 most recent
            columns = trans.get('columns', {})
            transactions_list.append({
                ATTR_TRANSACTION_ID: trans.get('row_id'),
                ATTR_PASS_ID: columns.get('0', {}).get('text', ''),
                ATTR_CHARGING_STATION: columns.get('1', {}).get('text', ''),
                ATTR_SETTLEMENT_TYPE: columns.get('2', {}).get('text', ''),
                ATTR_DATE: columns.get('3', {}).get('text', ''),
                ATTR_TYPE: columns.get('4', {}).get('badge') or columns.get('4', {}).get('text', ''),
                ATTR_KWH: columns.get('5', {}).get('text', ''),
                ATTR_COST: columns.get('6', {}).get('text', ''),
                ATTR_HAS_ERROR: columns.get('6', {}).get('has_error', False),
            })

        return {
            "transactions": transactions_list,
            "total_new": len(new_transactions),
        }


class NEFTTotalCostSensor(NEFTBaseSensor):
    """Sensor for total cost of all transactions."""

    def __init__(
        self,
        coordinator: NEFTDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "total_cost")
        self._attr_name = "Total Cost"
        self._attr_icon = "mdi:currency-eur"
        self._attr_native_unit_of_measurement = "EUR"
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        transactions = self.coordinator.data.get("transactions", [])
        total_cost = 0.0

        for trans in transactions:
            columns = trans.get('columns', {})
            cost_str = columns.get('6', {}).get('text', '€0.00')

            # Parse cost (remove €, convert to float)
            try:
                cost_value = float(cost_str.replace('€', '').replace(',', '.').strip())
                total_cost += cost_value
            except (ValueError, AttributeError):
                continue

        return round(total_cost, 2)


class NEFTTotalEnergyConsumptionSensor(NEFTBaseSensor):
    """Sensor for total energy consumption."""

    def __init__(
        self,
        coordinator: NEFTDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "total_energy")
        self._attr_name = "Total Energy Consumption"
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        transactions = self.coordinator.data.get("transactions", [])
        total_kwh = 0.0

        for trans in transactions:
            columns = trans.get('columns', {})
            kwh_str = columns.get('5', {}).get('text', '0 kWh')

            # Parse kWh (remove 'kWh', convert to float)
            try:
                kwh_value = float(kwh_str.replace('kWh', '').replace(',', '.').strip())
                total_kwh += kwh_value
            except (ValueError, AttributeError):
                continue

        return round(total_kwh, 2)


class NEFTACTariffSensor(NEFTBaseSensor):
    """Sensor for AC charging tariffs."""

    def __init__(
        self,
        coordinator: NEFTDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "ac_tariff")
        self._attr_name = "AC Charging Tariff"
        self._attr_icon = "mdi:ev-station"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        tariff_data = self.coordinator.data.get("tariff_data", {})
        charging_types = tariff_data.get("charging_types", [])

        for charging_type in charging_types:
            if charging_type.get('type') == 'AC Charging':
                tariffs = charging_type.get('tariffs', [])
                if tariffs:
                    # Return the per kWh tariff as the main state
                    for tariff in tariffs:
                        if 'kWh' in tariff.get('label', ''):
                            return tariff.get('total_with_vat', 'Unknown')

        return "Unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        tariff_data = self.coordinator.data.get("tariff_data", {})
        charging_types = tariff_data.get("charging_types", [])

        attributes = {}

        for charging_type in charging_types:
            if charging_type.get('type') == 'AC Charging':
                tariffs = charging_type.get('tariffs', [])

                for tariff in tariffs:
                    label = tariff.get('label', '')

                    if 'kWh' in label:
                        attributes[ATTR_AC_TARIFF_PER_KWH] = {
                            'base_value': tariff.get('base_value'),
                            'additional_fee': tariff.get('additional_fee'),
                            'total_with_vat': tariff.get('total_with_vat'),
                            'country': tariff.get('country'),
                            'vat_percentage': tariff.get('vat_percentage'),
                        }
                    elif 'session' in label.lower():
                        attributes[ATTR_AC_TARIFF_PER_SESSION] = {
                            'base_value': tariff.get('base_value'),
                            'additional_fee': tariff.get('additional_fee'),
                            'total_with_vat': tariff.get('total_with_vat'),
                        }
                    elif 'hour' in label.lower():
                        attributes[ATTR_AC_TARIFF_PER_HOUR] = {
                            'base_value': tariff.get('base_value'),
                            'additional_fee': tariff.get('additional_fee'),
                            'total_with_vat': tariff.get('total_with_vat'),
                        }

        return attributes


class NEFTDCTariffSensor(NEFTBaseSensor):
    """Sensor for DC charging tariffs."""

    def __init__(
        self,
        coordinator: NEFTDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "dc_tariff")
        self._attr_name = "DC Charging Tariff"
        self._attr_icon = "mdi:ev-plug-ccs2"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        tariff_data = self.coordinator.data.get("tariff_data", {})
        charging_types = tariff_data.get("charging_types", [])

        for charging_type in charging_types:
            if charging_type.get('type') == 'DC Charging':
                tariffs = charging_type.get('tariffs', [])
                if tariffs:
                    # Return the per kWh tariff as the main state
                    for tariff in tariffs:
                        if 'kWh' in tariff.get('label', ''):
                            return tariff.get('total_with_vat', 'Unknown')

        return "Unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        tariff_data = self.coordinator.data.get("tariff_data", {})
        charging_types = tariff_data.get("charging_types", [])

        attributes = {}

        for charging_type in charging_types:
            if charging_type.get('type') == 'DC Charging':
                tariffs = charging_type.get('tariffs', [])

                for tariff in tariffs:
                    label = tariff.get('label', '')

                    if 'kWh' in label:
                        attributes[ATTR_DC_TARIFF_PER_KWH] = {
                            'base_value': tariff.get('base_value'),
                            'additional_fee': tariff.get('additional_fee'),
                            'total_with_vat': tariff.get('total_with_vat'),
                            'country': tariff.get('country'),
                            'vat_percentage': tariff.get('vat_percentage'),
                        }
                    elif 'session' in label.lower():
                        attributes[ATTR_DC_TARIFF_PER_SESSION] = {
                            'base_value': tariff.get('base_value'),
                            'additional_fee': tariff.get('additional_fee'),
                            'total_with_vat': tariff.get('total_with_vat'),
                        }
                    elif 'hour' in label.lower():
                        attributes[ATTR_DC_TARIFF_PER_HOUR] = {
                            'base_value': tariff.get('base_value'),
                            'additional_fee': tariff.get('additional_fee'),
                            'total_with_vat': tariff.get('total_with_vat'),
                        }

        return attributes
