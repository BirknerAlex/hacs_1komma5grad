import logging

from homeassistant.components.number import NumberEntity
from homeassistant.const import PERCENTAGE
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Coordinator

_LOGGER = logging.getLogger(__name__)


class EVCurrentStateOfCharge(CoordinatorEntity, NumberEntity):
    """Number entity representing the EV State of Charge (0-100%)."""

    def __init__(self, coordinator: Coordinator, system_id: str, ev_id: str) -> None:
        """Initialize the number entity."""

        super().__init__(coordinator)

        self._system_id = system_id
        self._ev_id = ev_id
        self._ev_name = ev_id

        # NumberEntity attributes
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_native_min_value = 0.0
        self._attr_native_max_value = 100.0
        self._attr_native_step = 1.0
        self._attr_native_value: float | None = None

    @property
    def icon(self):
        # show a generic battery icon; Home Assistant may override with device class in the future
        soc = self._attr_native_value
        if soc is None:
            # unavailable / no SOC available
            return "mdi:battery-off"
        try:
            soc_int = int(float(soc))
        except (TypeError, ValueError):
            return "mdi:battery"

        # choose an icon bucket like battery-20, -40, -60, -80, -90, -full
        if soc_int >= 95:
            return "mdi:battery"
        if soc_int >= 80:
            return "mdi:battery-80"
        if soc_int >= 60:
            return "mdi:battery-60"
        if soc_int >= 40:
            return "mdi:battery-40"
        if soc_int >= 20:
            return "mdi:battery-20"
        return "mdi:battery-alert"

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        return f"{DOMAIN}_ev_current_soc_{self._system_id}_{self._ev_id}"

    @property
    def name(self) -> str:
        """Return the name of the EV SoC entity."""
        return f"EV Current State of Charge {self._ev_name}"

    @property
    def native_value(self) -> float | None:
        return self._attr_native_value

    async def async_set_native_value(self, value: float) -> None:
        """Set the target SOC via the coordinator (implement setter in coordinator)."""
        # Call coordinator setter (implement `set_target_soc` in your coordinator)
        await self.hass.async_add_executor_job(
            self.coordinator.set_ev_current_soc, self._system_id, self._ev_id, value
        )

        # Update local value and write state
        self._attr_native_value = float(value)
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True when entity has a valid SOC (SMART_CHARGE), otherwise False so HA shows unavailable."""
        return self._attr_native_value is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        ev_data = self.coordinator.get_ev_data(self._ev_id)
        if ev_data is not None:
            self._attr_native_value = ev_data.current_soc
            self._ev_name = ev_data.ev_name

        self.async_write_ha_state()