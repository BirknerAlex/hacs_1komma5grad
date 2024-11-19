from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfPower
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Coordinator


class GenericPowerSensor(CoordinatorEntity, SensorEntity):
    """Representation of Generic Power Sensor."""

    def __init__(
        self, coordinator: Coordinator, system_id: str, key: str, name: str, icon: str
    ) -> None:
        """Initialise sensor."""
        super().__init__(coordinator)

        self._system_id = system_id
        self._key = key
        self._name = name
        self._icon = icon
        self._live_data = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} Power {self._system_id}"

    @property
    def icon(self) -> str:
        return self._icon

    @property
    def native_unit_of_measurement(self):
        return UnitOfPower.WATT

    @property
    def unique_id(self) -> str:
        """Return unique id."""

        return f"{DOMAIN}_{self._key}_{self._system_id}"

    @property
    def native_value(self) -> None | float:
        """Return the state of the entity."""
        if self._key not in self._live_data:
            return None

        try:
            # External devices like EV chargers and heat pumps have a "power" key in the data
            if "power" in self._live_data[self._key]:
                # If power is None, you dont have access to the value (e.g. not supported on your heartbeat)
                if (
                    "value" not in self._live_data[self._key]["power"]
                    or self._live_data[self._key]["power"]["value"] is None
                ):
                    return None

                return self._live_data[self._key]["power"]["value"]

            # Other data like energy meters have a "value" key in the data
            return self._live_data[self._key]["value"]
        except KeyError:
            self.coordinator.logger.debug("No data available for %s", self._key)
        except TypeError:
            self.coordinator.logger.debug("No data available for %s", self._key)

        return None

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return SensorDeviceClass.POWER

    @property
    def state_class(self) -> SensorStateClass | str | None:
        """Return the state class of the sensor."""
        return SensorStateClass.MEASUREMENT

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        self._live_data = self.coordinator.get_live_data_by_id(self._system_id)[
            "liveHeroView"
        ]

        self.async_write_ha_state()
