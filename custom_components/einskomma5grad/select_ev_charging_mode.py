import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api.ev_charger import ChargingMode
from .const import DOMAIN
from .coordinator import Coordinator

_LOGGER = logging.getLogger(__name__)


class EVChargingModeSelect(CoordinatorEntity, SelectEntity):
    """Representation of an EV Charging Mode Select entity."""

    def __init__(self, coordinator: Coordinator, system_id: str, ev_id=str) -> None:
        """Initialize the select entity."""

        super().__init__(coordinator)

        self._system_id = system_id
        self._ev_id = ev_id
        self._attr_options = [
            str(ChargingMode.QUICK_CHARGE.value),
            str(ChargingMode.SMART_CHARGE.value),
            str(ChargingMode.SOLAR_CHARGE.value),
        ]

        self._attr_current_option = None

    @property
    def icon(self):
        return "mdi:ev-station"

    @property
    def options(self) -> list[str]:
        return self._attr_options

    @property
    def current_option(self) -> str | None:
        """Return the selected option."""
        return self._attr_current_option

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        return f"{DOMAIN}_ev_charging_mode_{self._system_id}_{self._ev_id}"

    @property
    def name(self) -> str:
        """Return the name of the select entity."""
        return f"EV Charging Mode {self._ev_id}"

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option not in self._attr_options:
            _LOGGER.error("Invalid option selected: %s", option)
            return

        # Call the API to change the mode
        await self.hass.async_add_executor_job(
            self.coordinator.set_charging_mode,
            self._system_id,
            self._ev_id,
            option,
        )

        # Update the current option
        self._attr_current_option = option
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        live_overview = self.coordinator.get_live_data_by_id(self._system_id)[
            "summaryCards"
        ]

        # iterate over all EVs and find the one with the matching ID
        for ev in live_overview["evs"]:
            if ev["id"] == self._ev_id:
                self._attr_current_option = ev["chargingMode"]

        self.async_write_ha_state()
