import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import Coordinator
from .sensor_electricity_price import ElectricityPriceSensor
from .sensor_power_generic import GenericPowerSensor

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sensors."""
    coordinator: Coordinator = hass.data[DOMAIN][config_entry.entry_id].coordinator

    # Enumerate all the sensors in your data value from your DataUpdateCoordinator and add an instance of your sensor class
    # to a list for each one.
    # This maybe different in your specific case, depending on how your data is structured
    sensors = [
        ElectricityPriceSensor(coordinator, system.id())
        for system in coordinator.data.systems
    ]

    for system in coordinator.data.systems:
        sensors.append(
            GenericPowerSensor(
                coordinator=coordinator,
                key="gridConsumption",
                icon="mdi:transmission-tower-export",
                system_id=system.id(),
                name="Grid Consumption",
            )
        )
        sensors.append(
            GenericPowerSensor(
                coordinator=coordinator,
                icon="mdi:transmission-tower",
                key="grid",
                system_id=system.id(),
                name="Grid",
            ),
        )
        sensors.append(
            GenericPowerSensor(
                coordinator=coordinator,
                icon="mdi:home-lightning-bolt-outline",
                key="consumption",
                system_id=system.id(),
                name="Consumption",
            ),
        )
        sensors.append(
            GenericPowerSensor(
                coordinator=coordinator,
                icon="mdi:solar-power",
                key="production",
                system_id=system.id(),
                name="Production",
            ),
        )
        sensors.append(
            GenericPowerSensor(
                coordinator=coordinator,
                icon="mdi:car-electric",
                key="evChargersAggregated",
                system_id=system.id(),
                name="EV Chargers Aggregated",
            ),
        )
        sensors.append(
            GenericPowerSensor(
                coordinator=coordinator,
                icon="mdi:heat-pump",
                key="heatPumpsAggregated",
                system_id=system.id(),
                name="Heat Pumps Aggregated",
            ),
        )
        sensors.append(
            GenericPowerSensor(
                coordinator=coordinator,
                icon="mdi:transmission-tower-import",
                key="gridFeedIn",
                system_id=system.id(),
                name="Grid Feed In",
            ),
        )

    async_add_entities(sensors)
