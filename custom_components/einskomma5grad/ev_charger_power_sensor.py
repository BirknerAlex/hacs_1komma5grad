from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfPower
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DeviceType
from .coordinator import Coordinator
from .device_info import get_device_info


def ev_charger_cards(coordinator: Coordinator, system_id: str) -> list[dict]:
    """Return the per-charger entries of the live overview (summaryCards.evChargers)."""
    live_data = coordinator.get_live_data_by_id(system_id) or {}
    cards = (live_data.get("summaryCards") or {}).get("evChargers")
    return [card for card in cards or [] if card.get("applianceId")]


class EVChargerPowerSensor(CoordinatorEntity[Coordinator], SensorEntity):
    """Power drawn by a single EV charger (wallbox)."""

    def __init__(
        self, coordinator: Coordinator, system_id: str, charger_id: str, name: str
    ) -> None:
        super().__init__(coordinator)

        self._system_id = system_id
        self._charger_id = charger_id
        self._charger_name = name
        self._attr_native_value = self._read_power()

    def _read_power(self) -> float | None:
        for card in ev_charger_cards(self.coordinator, self._system_id):
            if card["applianceId"] == self._charger_id:
                return (card.get("power") or {}).get("value")
        return None

    @property
    def name(self) -> str:
        return f"EV Charger {self._charger_name} Power"

    @property
    def icon(self) -> str:
        return "mdi:ev-station"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_ev_charger_power_{self._system_id}_{self._charger_id}"

    @property
    def native_unit_of_measurement(self) -> str:
        return UnitOfPower.WATT

    @property
    def device_class(self) -> SensorDeviceClass:
        return SensorDeviceClass.POWER

    @property
    def state_class(self) -> SensorStateClass:
        return SensorStateClass.MEASUREMENT

    @property
    def device_info(self) -> DeviceInfo | None:
        return get_device_info(
            self.coordinator, self._system_id, DeviceType.EV_CHARGER, self._charger_id
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = self._read_power()
        self.async_write_ha_state()
