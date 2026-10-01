"""Tests for the price and savings sensors."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from custom_components.einskomma5grad.sensor_prices import (
    DayTotalSensor,
    InsightSensor,
    dig,
    to_float,
)
from tests.conftest import SYSTEM_SLUG
from tests.test_sensor import _setup_with_frozen_time


def test_to_float_handles_api_strings_and_junk():
    assert to_float("0.22286804500025448") == 0.2229
    assert to_float(26.81, 2) == 26.81
    assert to_float(None) is None
    assert to_float("n/a") is None


def test_dig_stops_on_missing_or_non_dict_nodes():
    assert dig({"a": {"b": 1}}, "a", "b") == 1
    assert dig({"a": None}, "a", "b") is None
    assert dig(None, "a") is None


def _coordinator(prices=None, insights=None):
    coordinator = MagicMock()
    coordinator.get_prices_by_id.return_value = prices
    coordinator.get_insights_by_id.return_value = insights or {}
    return coordinator


def test_day_total_sensor_lists_the_other_variants_as_attributes():
    prices = {
        "dayTotals": {
            "supplyCostTotal": {
                "withoutVat": {"amount": "1.0"},
                "withVat": {"amount": "1.19"},
                "withGridCost": {"amount": "2.0"},
                "withGridCostAndVat": {"amount": "2.38"},
            }
        }
    }
    sensor = DayTotalSensor(
        _coordinator(prices), "x", "k", "n", "supplyCostTotal", "withGridCostAndVat"
    )

    assert sensor.native_value == 2.38
    assert sensor.extra_state_attributes == {
        "without_vat": 1.0,
        "with_vat": 1.19,
        "with_grid_cost": 2.0,
    }


def test_day_total_sensor_tolerates_null_variants():
    prices = {"dayTotals": {"feedInEarningsTotal": {"withVat": {"amount": "0.01"}, "withGridCost": None}}}
    sensor = DayTotalSensor(_coordinator(prices), "x", "k", "n", "feedInEarningsTotal", "withVat")

    assert sensor.native_value == 0.01
    assert sensor.extra_state_attributes["with_grid_cost"] is None


def test_insight_sensor_is_none_without_data():
    sensor = InsightSensor(
        _coordinator(), "x", "k", "n", "energy_trader",
        value=lambda d: dig(d, "energyTrader", "energyTraderSavings", "amount"),
        unit="EUR",
    )
    assert sensor.native_value is None


async def test_insight_sensors_from_api_data(hass: HomeAssistant, setup_integration):
    expected = {
        "heartbeat_price": 0.2229,
        "comparison_price": 0.4,
        "heartbeat_savings_30_days": 189.32,
        "energy_trader_savings": 48.75,
        "energy_trader_average_monthly_savings": 26.81,
    }
    for name, value in expected.items():
        state = hass.states.get(f"sensor.{name}_{SYSTEM_SLUG}")
        assert state is not None, name
        assert float(state.state) == value, name

    trader = hass.states.get(f"sensor.energy_trader_savings_{SYSTEM_SLUG}")
    assert trader is not None
    assert trader.attributes["status"] == "ACTIVE"
    assert trader.attributes["green_energy_savings"] == 12.5

    price = hass.states.get(f"sensor.heartbeat_price_{SYSTEM_SLUG}")
    assert price is not None
    assert price.attributes["year"] == 0.2612
    assert "day" not in price.attributes


async def test_day_total_sensors_from_price_data(hass: HomeAssistant, setup_integration):
    supply = hass.states.get(f"sensor.grid_supply_cost_today_{SYSTEM_SLUG}")
    assert supply is not None
    assert float(supply.state) > 0
    assert supply.attributes["unit_of_measurement"] == "EUR"

    assert hass.states.get(f"sensor.feed_in_earnings_today_{SYSTEM_SLUG}") is not None


async def test_slot_price_sensors_read_current_slot(
    hass: HomeAssistant, mock_config_entry, mock_api, enable_custom_integrations
):
    await _setup_with_frozen_time(hass, mock_config_entry, mock_api)

    # Slot 09:30Z: marketPriceWithVat 0.0510629 / marketPrice 0.04291
    spot = hass.states.get(f"sensor.spot_price_{SYSTEM_SLUG}")
    assert spot is not None
    assert float(spot.state) == 0.0511
    assert spot.attributes["price_without_vat"] == 0.0429

    # gridCostsWithVat 0.1520344 / gridCosts 0.12776
    grid = hass.states.get(f"sensor.grid_costs_{SYSTEM_SLUG}")
    assert grid is not None
    assert float(grid.state) == 0.152
    assert grid.attributes["price_without_vat"] == 0.1278
