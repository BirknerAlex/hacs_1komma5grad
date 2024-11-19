from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import Coordinator
from .const import DOMAIN


class EmsSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of the Heartbeat Auto Mode Switch."""

    def __init__(self, coordinator: Coordinator, system_id: str) -> None:
        """Initialise sensor."""
        super().__init__(coordinator)

        self._system_id = system_id
        self._enabled = None

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:heart"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Heartbeat Automatic Mode {self._system_id}"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the entity."""
        return self._enabled

    @property
    def unique_id(self) -> str:
        """Return unique id."""

        return f"{DOMAIN}_ems_auto_mode_{self._system_id}"

    @property
    def device_class(self) -> SwitchDeviceClass | None:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return SwitchDeviceClass.SWITCH

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.hass.async_add_executor_job(
            self.coordinator.set_ems_auto_mode,
            self._system_id,
            False,
        )

        self._enabled = False

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.hass.async_add_executor_job(
            self.coordinator.set_ems_auto_mode,
            self._system_id,
            True,
        )

        self._enabled = True

    @callback
    def _handle_coordinator_update(self) -> None:
        self._enabled = not self.coordinator.data.ems_settings[self._system_id][
            "overrideAutoSettings"
        ]

        self.async_write_ha_state()
