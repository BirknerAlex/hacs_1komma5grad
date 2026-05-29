import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .energy_sensor import EnergySensor, DailyEnergySensor
from .const import DOMAIN, DeviceType
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

    def append_energy_sensors(
        power_sensor, name, direction, device_type, system_id, metric_path
    ):
        """Append the cumulative (integrated) and daily (measured) energy sensors.

        The cumulative sensor integrates instantaneous power; the daily sensor
        (disabled by default) reads the measured daily total from the API so it
        matches the dashboard and resets at midnight.
        """
        sensors.append(
            EnergySensor(
                coordinator=coordinator,
                system_id=system_id,
                power_sensor=power_sensor,
                name=name,
                direction=direction,
                device_type=device_type,
            )
        )
        sensors.append(
            DailyEnergySensor(
                coordinator=coordinator,
                system_id=system_id,
                name=name,
                direction=direction,
                metric_path=metric_path,
                device_type=device_type,
            )
        )

    for system in coordinator.data.systems:
        # Grid feed out power sensor
        grid_feed_out_power_sensor = GenericPowerSensor(
            coordinator=coordinator,
            key="gridConsumption",
            icon="mdi:transmission-tower-export",
            system_id=system.id(),
            name="Grid Feed Out",
            device_type=DeviceType.GATEWAY,
        )
        sensors.append(grid_feed_out_power_sensor)
        append_energy_sensors(
            power_sensor=grid_feed_out_power_sensor,
            name="Grid Feed",
            direction="out",
            device_type=DeviceType.GATEWAY,
            system_id=system.id(),
            metric_path=("grid", "supply"),
        )

        # Grid feed in power sensor
        grid_feed_in_power_sensor = GenericPowerSensor(
            coordinator=coordinator,
            icon="mdi:transmission-tower-import",
            key="gridFeedIn",
            system_id=system.id(),
            name="Grid Feed In",
            device_type=DeviceType.GATEWAY,
        )
        sensors.append(grid_feed_in_power_sensor)
        append_energy_sensors(
            power_sensor=grid_feed_in_power_sensor,
            name="Grid Feed",
            direction="in",
            device_type=DeviceType.GATEWAY,
            system_id=system.id(),
            metric_path=("grid", "feedIn"),
        )

        # Grid power total sensor
        grid_feed_total_sensor = GenericPowerSensor(
            coordinator=coordinator,
            icon="mdi:transmission-tower",
            key="grid",
            system_id=system.id(),
            name="Grid Feed",
            device_type=DeviceType.GATEWAY,
        )
        sensors.append(grid_feed_total_sensor)

        # Consumption total power sensor
        consumption_total_power_sensor = GenericPowerSensor(
            coordinator=coordinator,
            icon="mdi:home-lightning-bolt-outline",
            key="consumption",
            system_id=system.id(),
            name="Consumption",
            device_type=DeviceType.GATEWAY,
        )
        sensors.append(consumption_total_power_sensor)

        # Solar power production sensor
        solar_power_production_sensor = GenericPowerSensor(
            coordinator=coordinator,
            icon="mdi:solar-power",
            key="production",
            system_id=system.id(),
            name="Solar Production",
            device_type=DeviceType.GATEWAY,
        )
        sensors.append(solar_power_production_sensor)
        append_energy_sensors(
            power_sensor=solar_power_production_sensor,
            name="Solar",
            direction="production",
            device_type=DeviceType.GATEWAY,
            system_id=system.id(),
            metric_path=("energyProduced",),
        )

        # Electric vehicle chargers and heat pumps aggregated power sensor
        ev_chargers_power_sensor = GenericPowerSensor(
            coordinator=coordinator,
            icon="mdi:car-electric",
            key="evChargersAggregated",
            system_id=system.id(),
            name="EV Chargers Aggregated",
            device_type=DeviceType.EV_CHARGER,
        )
        sensors.append(ev_chargers_power_sensor)
        append_energy_sensors(
            power_sensor=ev_chargers_power_sensor,
            name="EV Chargers",
            direction="consumption",
            device_type=DeviceType.EV_CHARGER,
            system_id=system.id(),
            metric_path=("consumption", "consumers", "ev"),
        )

        # Heat pumps aggregated power sensor
        heat_pumps_power_sensor = GenericPowerSensor(
            coordinator=coordinator,
            icon="mdi:heat-pump",
            key="heatPumpsAggregated",
            system_id=system.id(),
            name="Heat Pumps Aggregated",
            device_type=DeviceType.HEAT_PUMP,
        )
        sensors.append(heat_pumps_power_sensor)
        append_energy_sensors(
            power_sensor=heat_pumps_power_sensor,
            name="Heat Pumps",
            direction="consumption",
            device_type=DeviceType.HEAT_PUMP,
            system_id=system.id(),
            metric_path=("consumption", "consumers", "heatPump"),
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
        append_energy_sensors(
            power_sensor=battery_power_in_sensor,
            name="Battery",
            direction="in",
            device_type=DeviceType.HYBRID,
            system_id=system.id(),
            metric_path=("battery", "charge"),
        )

        # Battery Power Out sensor
        battery_power_out_sensor = BatteryPowerOutSensor(coordinator, system.id())
        sensors.append(battery_power_out_sensor)
        append_energy_sensors(
            power_sensor=battery_power_out_sensor,
            name="Battery",
            direction="out",
            device_type=DeviceType.HYBRID,
            system_id=system.id(),
            metric_path=("battery", "discharge"),
        )

    async_add_entities(sensors)
