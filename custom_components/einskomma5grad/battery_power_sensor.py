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

class BatteryPowerInSensor(CoordinatorEntity, SensorEntity):
    """Representation of Battery Power In Sensor."""

    def __init__(self, coordinator: Coordinator, system_id: str) -> None:
        """Initialise sensor."""
        super().__init__(coordinator)
        self._system_id = system_id
        self._summary_cards = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Battery In Power {self._system_id}"

    @property
    def icon(self) -> str:
        return "mdi:battery-arrow-down"

    @property
    def native_unit_of_measurement(self):
        return UnitOfPower.WATT

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        return f"{DOMAIN}_battery_in_power_{self._system_id}"

    @property
    def native_value(self) -> None | float:
        """Return the state of the entity."""
        if "battery" not in self._summary_cards:
            return None

        try:
            if "power" in self._summary_cards["battery"]:
                power = self._summary_cards["battery"]["power"].get("value")
                if power is not None and power < 0:
                    return abs(power)
        except (KeyError, TypeError):
            self.coordinator.logger.debug("No data available for %s", "battery")

        return 0

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
        live_data = self.coordinator.get_live_data_by_id(self._system_id)

        if live_data is None:
            return

        self._summary_cards = live_data[
            "summaryCards"
        ]

        self.async_write_ha_state()


class BatteryPowerOutSensor(CoordinatorEntity, SensorEntity):
    """Representation of Battery Power Out Sensor."""

    def __init__(self, coordinator: Coordinator, system_id: str) -> None:
        """Initialise sensor."""
        super().__init__(coordinator)
        self._system_id = system_id
        self._summary_cards = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Battery Out Power {self._system_id}"

    @property
    def icon(self) -> str:
        return "mdi:battery-arrow-up"

    @property
    def native_unit_of_measurement(self):
        return UnitOfPower.WATT

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        return f"{DOMAIN}_battery_out_power_{self._system_id}"

    @property
    def native_value(self) -> None | float:
        """Return the state of the entity."""
        if "battery" not in self._summary_cards:
            return None

        try:
            if "power" in self._summary_cards["battery"]:
                power = self._summary_cards["battery"]["power"].get("value")
                if power is not None and power > 0:
                    return power
        except (KeyError, TypeError):
            self.coordinator.logger.debug("No data available for %s", "battery")

        return 0

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
        live_data = self.coordinator.get_live_data_by_id(self._system_id)

        if live_data is None:
            return

        self._summary_cards = live_data[
            "summaryCards"
        ]

        self.async_write_ha_state()
