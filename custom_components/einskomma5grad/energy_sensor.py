import re
from datetime import datetime, UTC
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Coordinator

class EnergySensor(CoordinatorEntity, SensorEntity):
    """Sensor to track the energy consumed or produced by the referenced power sensor."""

    def __init__(self, coordinator: Coordinator, system_id: str, power_sensor: SensorEntity, direction: str, name: str) -> None:
        """Initalize the sensor."""
        super().__init__(coordinator)
        self._system_id = system_id
        self._power_sensor = power_sensor
        self._direction = direction
        self._name = name
        self._last_update = None
        self._energy = 0.0  # Accumulated energy in kWh

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
