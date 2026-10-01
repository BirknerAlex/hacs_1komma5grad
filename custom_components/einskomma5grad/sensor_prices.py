"""Price and savings sensors: spot price, grid costs, day totals and Heartbeat figures."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CURRENCY_ICON, DOMAIN, DeviceType
from .coordinator import Coordinator
from .device_info import get_device_info
from .sensor_electricity_price import current_slot_key

PRICE_UNIT = "EUR/kWh"
MONEY_UNIT = "EUR"


def to_float(value: Any, digits: int = 4) -> float | None:
    """Convert API numbers, which are often strings, to a rounded float."""
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def dig(node: Any, *path: str) -> Any:
    """Follow a path through nested dicts, returning None when it breaks off."""
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


class _GatewaySensor(CoordinatorEntity[Coordinator], SensorEntity):
    """Common parts of the sensors that live on the gateway device."""

    def __init__(self, coordinator: Coordinator, system_id: str, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._system_id = system_id
        self._key = key
        self._name = name

    @property
    def name(self) -> str:
        return f"{self._name} {self._system_id}"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self._key}_{self._system_id}"

    @property
    def icon(self) -> str:
        return CURRENCY_ICON

    @property
    def device_info(self) -> DeviceInfo | None:
        return get_device_info(self.coordinator, self._system_id, DeviceType.GATEWAY)


class SlotPriceSensor(_GatewaySensor):
    """A component of the current 15 minute price slot, e.g. the spot price."""

    _attr_native_unit_of_measurement = PRICE_UNIT

    def __init__(
        self, coordinator: Coordinator, system_id: str, key: str, name: str,
        field: str, net_field: str,
    ) -> None:
        super().__init__(coordinator, system_id, key, name)
        self._field = field
        self._net_field = net_field

    def _slot(self) -> dict | None:
        prices = self.coordinator.get_prices_by_id(self._system_id)
        slot = dig(prices, "timeseries", current_slot_key())
        return slot if isinstance(slot, dict) else None

    @property
    def native_value(self) -> float | None:
        return to_float(dig(self._slot(), self._field))

    @property
    def extra_state_attributes(self) -> dict:
        return {"price_without_vat": to_float(dig(self._slot(), self._net_field))}


class DayTotalSensor(_GatewaySensor):
    """Cost or earnings accumulated over the day, as calculated by the API."""

    _attr_native_unit_of_measurement = MONEY_UNIT
    _attr_device_class = SensorDeviceClass.MONETARY

    # API variant -> attribute name
    _VARIANTS: ClassVar[dict[str, str]] = {
        "withoutVat": "without_vat",
        "withVat": "with_vat",
        "withGridCost": "with_grid_cost",
        "withGridCostAndVat": "with_grid_cost_and_vat",
    }

    def __init__(
        self, coordinator: Coordinator, system_id: str, key: str, name: str,
        total: str, variant: str,
    ) -> None:
        super().__init__(coordinator, system_id, key, name)
        self._total = total
        self._variant = variant

    def _node(self, variant: str) -> Any:
        prices = self.coordinator.get_prices_by_id(self._system_id)
        return dig(prices, "dayTotals", self._total, variant, "amount")

    @property
    def native_value(self) -> float | None:
        return to_float(self._node(self._variant))

    @property
    def extra_state_attributes(self) -> dict:
        return {
            attr: to_float(self._node(variant))
            for variant, attr in self._VARIANTS.items()
            if variant != self._variant
        }


class InsightSensor(_GatewaySensor):
    """A slowly changing figure from the price and savings endpoints."""

    def __init__(
        self, coordinator: Coordinator, system_id: str, key: str, name: str,
        source: str, value: Callable[[Any], Any], unit: str,
        attributes: Callable[[Any], dict] | None = None,
    ) -> None:
        super().__init__(coordinator, system_id, key, name)
        self._source = source
        self._value = value
        self._attributes = attributes
        self._attr_native_unit_of_measurement = unit
        if unit == MONEY_UNIT:
            self._attr_device_class = SensorDeviceClass.MONETARY

    def _data(self) -> Any:
        return self.coordinator.get_insights_by_id(self._system_id).get(self._source)

    @property
    def native_value(self) -> float | None:
        return to_float(self._value(self._data()))

    @property
    def extra_state_attributes(self) -> dict | None:
        if self._attributes is None:
            return None
        return self._attributes(self._data())


_WINDOWS = {"day": "day", "week": "week", "month": "month", "halfYear": "half_year", "year": "year"}


def build_price_sensors(coordinator: Coordinator, system_id: str) -> list[SensorEntity]:
    """Create the price and savings sensors for one system."""
    return [
        SlotPriceSensor(
            coordinator, system_id, "spot_price", "Spot Price",
            field="marketPriceWithVat", net_field="marketPrice",
        ),
        SlotPriceSensor(
            coordinator, system_id, "grid_costs", "Grid Costs",
            field="gridCostsWithVat", net_field="gridCosts",
        ),
        DayTotalSensor(
            coordinator, system_id, "supply_cost_today", "Grid Supply Cost Today",
            total="supplyCostTotal", variant="withGridCostAndVat",
        ),
        DayTotalSensor(
            coordinator, system_id, "feed_in_earnings_today", "Feed-in Earnings Today",
            total="feedInEarningsTotal", variant="withVat",
        ),
        InsightSensor(
            coordinator, system_id, "heartbeat_price", "Heartbeat Price",
            source="heartbeat_prices",
            value=lambda d: dig(d, "day", "heartbeatPrice", "price", "amount"),
            unit=PRICE_UNIT,
            attributes=lambda d: {
                attr: to_float(dig(d, window, "heartbeatPrice", "price", "amount"))
                for window, attr in _WINDOWS.items()
                if window != "day"
            },
        ),
        InsightSensor(
            coordinator, system_id, "comparison_price", "Comparison Price",
            source="comparison_price",
            value=lambda d: dig(d, "comparisonPrice", "price", "amount"),
            unit=PRICE_UNIT,
        ),
        InsightSensor(
            coordinator, system_id, "savings_30_days", "Heartbeat Savings 30 Days",
            source="energy_savings",
            value=lambda d: dig(d, "heartbeatSavings", "value"),
            unit=MONEY_UNIT,
        ),
        InsightSensor(
            coordinator, system_id, "energy_trader_savings", "Energy Trader Savings",
            source="energy_trader",
            value=lambda d: dig(d, "energyTrader", "energyTraderSavings", "amount"),
            unit=MONEY_UNIT,
            attributes=lambda d: {
                "green_energy_savings": to_float(
                    dig(d, "energyTrader", "greenEnergySavings", "amount")
                ),
                "status": dig(d, "energyTrader", "status"),
            },
        ),
        InsightSensor(
            coordinator, system_id, "energy_trader_monthly_savings",
            "Energy Trader Average Monthly Savings",
            source="energy_trader_monthly",
            value=lambda d: dig(d, "averagePastVariableSavings", "value"),
            unit=MONEY_UNIT,
        ),
    ]
