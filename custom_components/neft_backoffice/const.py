"""Constants for the NEFT Backoffice integration."""
from datetime import timedelta

DOMAIN = "neft_backoffice"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = timedelta(hours=1)
MIN_SCAN_INTERVAL = timedelta(minutes=30)

# Attributes
ATTR_TRANSACTION_ID = "transaction_id"
ATTR_PASS_ID = "pass_id"
ATTR_CHARGING_STATION = "charging_station"
ATTR_SETTLEMENT_TYPE = "settlement_type"
ATTR_DATE = "date"
ATTR_TYPE = "type"
ATTR_KWH = "kwh"
ATTR_COST = "cost"
ATTR_HAS_ERROR = "has_error"

# Tariff attributes
ATTR_AC_TARIFF_PER_KWH = "ac_tariff_per_kwh"
ATTR_AC_TARIFF_PER_SESSION = "ac_tariff_per_session"
ATTR_AC_TARIFF_PER_HOUR = "ac_tariff_per_hour"
ATTR_DC_TARIFF_PER_KWH = "dc_tariff_per_kwh"
ATTR_DC_TARIFF_PER_SESSION = "dc_tariff_per_session"
ATTR_DC_TARIFF_PER_HOUR = "dc_tariff_per_hour"
