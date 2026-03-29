"""Constants for the 1KOMMA5GRAD integration."""

from enum import StrEnum

DEFAULT_SCAN_INTERVAL = 60

# Minimum and maximum allowed scan interval (seconds)
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 3600

DOMAIN = "einskomma5grad"

CURRENCY_ICON = "mdi:cash"


class DeviceType(StrEnum):
    """Device types for mapping entities to HA device registry entries."""

    GATEWAY = "gateway"
    HYBRID = "hybrid"
    EV_CHARGER = "ev_charger"
    HEAT_PUMP = "heat_pump"
