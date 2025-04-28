import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .energy_sensor import EnergySensor
from .const import DOMAIN
from .coordinator import Coordinator
from .sensor_electricity_price import ElectricityPriceSensor
from .sensor_power_generic import GenericPowerSensor
from .battery_power_sensor import BatteryPowerInSensor, BatteryPowerOutSensor
from .battery_soc_sensor import BatteryStateOfChargeSensor

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
        # Grid feed out power sensor
        grid_feed_out_power_sensor = GenericPowerSensor(
            coordinator=coordinator,
            key="gridConsumption",
            icon="mdi:transmission-tower-export",
            system_id=system.id(),
            name="Grid Feed Out",
        )
        sensors.append(grid_feed_out_power_sensor)
        sensors.append(
            EnergySensor(
                coordinator=coordinator,
                system_id=system.id(),
                power_sensor=grid_feed_out_power_sensor,
                name="Grid Feed",
                direction="out"
            )
        )

        # Grid feed in power sensor
        grid_feed_in_power_sensor = GenericPowerSensor(
            coordinator=coordinator,
            icon="mdi:transmission-tower-import",
            key="gridFeedIn",
            system_id=system.id(),
            name="Grid Feed In",
        )
        sensors.append(grid_feed_in_power_sensor)
        sensors.append(
            EnergySensor(
                coordinator=coordinator,
                system_id=system.id(),
                power_sensor=grid_feed_in_power_sensor,
                name="Grid Feed",
                direction="in"
            )
        )

        # Grid power total sensor
        grid_feed_total_sensor = GenericPowerSensor(
            coordinator=coordinator,
            icon="mdi:transmission-tower",
            key="grid",
            system_id=system.id(),
            name="Grid Feed",
        )
        sensors.append(grid_feed_total_sensor)

        # Consumption total power sensor
        consumption_total_power_sensor = GenericPowerSensor(
            coordinator=coordinator,
            icon="mdi:home-lightning-bolt-outline",
            key="consumption",
            system_id=system.id(),
            name="Consumption",
        )
        sensors.append(consumption_total_power_sensor)

        # Solar power production sensor
        solar_power_production_sensor = GenericPowerSensor(
            coordinator=coordinator,
            icon="mdi:solar-power",
            key="production",
            system_id=system.id(),
            name="Solar Production",
        )
        sensors.append(solar_power_production_sensor)
        sensors.append(
            EnergySensor(
                coordinator=coordinator,
                system_id=system.id(),
                power_sensor=solar_power_production_sensor,
                name="Solar",
                direction="production"
            )
        )

        # Electric vehicle chargers and heat pumps aggregated power sensor
        ev_chargers_power_sensor = GenericPowerSensor(
            coordinator=coordinator,
            icon="mdi:car-electric",
            key="evChargersAggregated",
            system_id=system.id(),
            name="EV Chargers Aggregated",
        )
        sensors.append(ev_chargers_power_sensor)
        sensors.append(
            EnergySensor(
                coordinator=coordinator,
                system_id=system.id(),
                power_sensor=ev_chargers_power_sensor,
                name="EV Chargers",
                direction="consumption"
            )
        )

        # Heat pumps aggregated power sensor
        heat_pumps_power_sensor = GenericPowerSensor(
            coordinator=coordinator,
            icon="mdi:heat-pump",
            key="heatPumpsAggregated",
            system_id=system.id(),
            name="Heat Pumps Aggregated",
        )
        sensors.append(heat_pumps_power_sensor)
        sensors.append(
            EnergySensor(
                coordinator=coordinator,
                system_id=system.id(),
                power_sensor=heat_pumps_power_sensor,
                name="Heat Pumps",
                direction="consumption"
            )
        )

        # Battery SOC sensor
        battery_soc_sensor = BatteryStateOfChargeSensor(
            coordinator=coordinator,
            system_id=system.id(),
        )
        sensors.append(battery_soc_sensor)

        # Battery Power In sensor
        battery_power_in_sensor = BatteryPowerInSensor(coordinator, system.id())
        sensors.append(battery_power_in_sensor)
        sensors.append(
            EnergySensor(
                coordinator=coordinator,
                system_id=system.id(),
                power_sensor=battery_power_in_sensor,
                name="Battery",
                direction="in",
            )
        )

        # Battery Power Out sensor
        battery_power_out_sensor = BatteryPowerOutSensor(coordinator, system.id())
        sensors.append(battery_power_out_sensor)
        sensors.append(
            EnergySensor(
                coordinator=coordinator,
                system_id=system.id(),
                power_sensor=battery_power_out_sensor,
                name="Battery",
                direction="out"
            )
        )

    async_add_entities(sensors)
