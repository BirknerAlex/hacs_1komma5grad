"""Constants for the 1KOMMA5GRAD integration."""

from datetime import timedelta
from enum import StrEnum

DEFAULT_SCAN_INTERVAL = 60

CONF_ERROR_REPORTING = "error_reporting"
DEFAULT_ERROR_REPORTING = False

# Minimum and maximum allowed scan interval (seconds)
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 3600

# Market prices are rate limited (1 request/minute) and change slowly
PRICE_REFRESH_INTERVAL = timedelta(minutes=15)

# Savings, Heartbeat price and Energy Trader figures only move slowly
INSIGHTS_REFRESH_INTERVAL = timedelta(hours=1)

# Window of the savings figure, in days
SAVINGS_WINDOW_DAYS = 30

DOMAIN = "einskomma5grad"

CURRENCY_ICON = "mdi:cash"


class DeviceType(StrEnum):
    """Device types for mapping entities to HA device registry entries."""

    GATEWAY = "gateway"
    HYBRID = "hybrid"
    EV_CHARGER = "ev_charger"
    HEAT_PUMP = "heat_pump"
