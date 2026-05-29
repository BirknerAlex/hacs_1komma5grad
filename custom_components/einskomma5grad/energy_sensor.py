import logging
import re
from datetime import datetime, UTC
from homeassistant.components.sensor import RestoreSensor, SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, DeviceType
from .coordinator import Coordinator
from .device_info import get_device_info

_LOGGER = logging.getLogger(__name__)

class EnergySensor(CoordinatorEntity, RestoreSensor):
    """Sensor to track the energy consumed or produced by the referenced power sensor."""

    def __init__(self, coordinator: Coordinator, system_id: str, power_sensor: SensorEntity, direction: str, name: str, device_type: DeviceType | None = None) -> None:
        """Initalize the sensor."""
        super().__init__(coordinator)
        self._system_id = system_id
        self._power_sensor = power_sensor
        self._direction = direction
        self._name = name
        self._device_type = device_type
        self._last_update = None
        self._energy = 0.0  # Accumulated energy in kWh

    async def async_added_to_hass(self) -> None:
        """Restore the accumulated energy after a restart."""
        await super().async_added_to_hass()

        last_data = await self.async_get_last_sensor_data()
        if last_data is not None and last_data.native_value is not None:
            self._energy = float(last_data.native_value)
            _LOGGER.debug(
                "Restored accumulated energy for %s: %s kWh",
                self.unique_id,
                self._energy,
            )
        else:
            _LOGGER.debug(
                "No previous energy state to restore for %s, starting at 0 kWh",
                self.unique_id,
            )

        # Intentionally leave self._last_update as None so the first update after
        # a restart only re-establishes the timestamp and does not count energy
        # for the time Home Assistant was offline.

    @property
    def name(self):
        """Returns the name of the energy sensor."""
        return f"{self._name} Energy {self._direction.capitalize()} {self._system_id}"

    @property
    def icon(self) -> str:
        return "mdi:lightning-bolt"

    @property
    def native_unit_of_measurement(self):
        return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self.key_from_name()}_energy_{self._direction}_{self._system_id}"

    @property
    def native_value(self) -> float:
        """Returns the current value of the sensor."""
        return self._energy

    @property
    def device_class(self):
        """Returns the sensor device class."""
        return SensorDeviceClass.ENERGY

    @property
    def state_class(self) -> SensorStateClass | str | None:
        """Returns the state class of the sensor."""
        return SensorStateClass.TOTAL_INCREASING

    @property
    def device_info(self) -> DeviceInfo | None:
        return get_device_info(self.coordinator, self._system_id, self._device_type)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Updates the sensor state when the coordinator updates."""
        current_time = datetime.now(UTC)
        power = self._power_sensor.native_value  # power in watt

        if power is not None and self._last_update is not None:
            time_diff = (current_time - self._last_update).total_seconds() / 3600.0  # Zeitdifferenz in Stunden
            self._energy += (power * time_diff) / 1000.0  # energy in kWh

        self._last_update = current_time
        self.async_write_ha_state()

    def key_from_name(self) -> str:
        return re.sub(r'\s+', '_', self._name.strip().lower())


class DailyEnergySensor(EnergySensor):
    """Energy sensor that resets to zero at local midnight (daily total).

    Disabled by default; intended for users who want a value that matches the
    1KOMMA5GRAD dashboard's daily figures.
    """

    _attr_entity_registry_enabled_default = False

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the daily energy sensor."""
        super().__init__(*args, **kwargs)
        self._current_day = None  # local date the accumulated energy belongs to

    async def async_added_to_hass(self) -> None:
        """Restore the accumulated energy, discarding it if it is from a past day."""
        await super().async_added_to_hass()

        today = dt_util.now().date()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            last_day = dt_util.as_local(last_state.last_updated).date()
            if last_day != today:
                self._energy = 0.0
                _LOGGER.debug(
                    "Discarded stale daily energy for %s (last update %s), reset to 0 kWh",
                    self.unique_id,
                    last_day,
                )
        self._current_day = today

    @property
    def name(self):
        """Returns the name of the daily energy sensor."""
        return f"{self._name} Energy {self._direction.capitalize()} Today {self._system_id}"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self.key_from_name()}_energy_{self._direction}_today_{self._system_id}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Reset at local midnight, then accumulate as usual."""
        today = dt_util.now().date()
        if self._current_day is not None and today != self._current_day:
            self._energy = 0.0
            # Drop the timestamp so the cross-midnight interval is not counted
            # into the new day; accumulation restarts from this update.
            self._last_update = None
            _LOGGER.debug("Daily energy reset for %s at %s", self.unique_id, today)
        self._current_day = today

        super()._handle_coordinator_update()
