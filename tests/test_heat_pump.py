"""Tests for heat pump power and energy handling."""

from unittest.mock import MagicMock

import pytest

from custom_components.einskomma5grad.heat_pump_power_sensor import (
    HeatPumpPowerSensor,
    heat_pump_cards,
)
from custom_components.einskomma5grad.sensor_power_generic import GenericPowerSensor


def _sensor(node) -> GenericPowerSensor:
    sensor = GenericPowerSensor(
        MagicMock(), system_id="x", key="heatPumpsAggregated", name="HP", icon="mdi:x"
    )
    sensor._live_data = {"heatPumpsAggregated": node}
    return sensor


@pytest.mark.parametrize(
    ("node", "expected"),
    [
        # Heat pump not controlled by the EMS: only powerExternal is filled.
        ({"power": {"value": 0}, "powerExternal": {"value": 9}}, 9),
        ({"power": {"value": 1200}, "powerExternal": None}, 1200),
        ({"power": {"value": 1200}}, 1200),
        ({"power": {"value": None}, "powerExternal": {"value": 9}}, 9),
        ({"power": {"value": None}, "powerExternal": None}, None),
        ({"power": None, "powerExternal": None}, None),
    ],
)
def test_aggregated_power_includes_external(node, expected):
    assert _sensor(node).native_value == expected


def test_value_node_without_power_key_still_works():
    sensor = _sensor({"value": 42})
    assert sensor.native_value == 42


def _coordinator(cards):
    coordinator = MagicMock()
    coordinator.get_live_data_by_id.return_value = {"summaryCards": {"heatPumps": cards}}
    return coordinator


def test_heat_pump_cards_skip_entries_without_id():
    coordinator = _coordinator(
        [{"applianceId": "a", "power": {"value": 9}}, {"power": {"value": 1}}]
    )
    assert [c["applianceId"] for c in heat_pump_cards(coordinator, "x")] == ["a"]


def test_per_heat_pump_sensor_reads_its_own_card():
    coordinator = _coordinator(
        [
            {"applianceId": "a", "power": {"value": 9}},
            {"applianceId": "b", "power": {"value": 1500}},
        ]
    )
    assert HeatPumpPowerSensor(coordinator, "x", "b", "2").native_value == 1500
    assert HeatPumpPowerSensor(coordinator, "x", "missing", "3").native_value is None
