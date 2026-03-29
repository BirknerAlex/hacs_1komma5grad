"""Test 1KOMMA5GRAD sensor entities."""

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant

from custom_components.einskomma5grad.const import DOMAIN
from tests.conftest import SYSTEM_SLUG

PRICE_ENTITY = f"sensor.electricity_price_{SYSTEM_SLUG}"

# Frozen time for price forecast tests: 2026-03-29 08:30 UTC (= 09:30 CET)
# The API returns timeseries keys in CET (UTC+1), so the current slot key is 09:30Z
FROZEN_NOW = datetime(2026, 3, 29, 8, 30, 0, tzinfo=ZoneInfo("UTC"))


async def test_electricity_price_sensor_exists(hass: HomeAssistant, setup_integration):
    """Test that the electricity price sensor is created."""
    state = hass.states.get(PRICE_ENTITY)
    assert state is not None


async def test_grid_feed_out_sensor_exists(hass: HomeAssistant, setup_integration):
    """Test that the grid feed out power sensor is created."""
    state = hass.states.get(f"sensor.grid_feed_out_power_{SYSTEM_SLUG}")
    assert state is not None


async def test_grid_feed_in_sensor_exists(hass: HomeAssistant, setup_integration):
    """Test that the grid feed in power sensor is created."""
    state = hass.states.get(f"sensor.grid_feed_in_power_{SYSTEM_SLUG}")
    assert state is not None


async def test_consumption_sensor_exists(hass: HomeAssistant, setup_integration):
    """Test that the consumption power sensor is created."""
    state = hass.states.get(f"sensor.consumption_power_{SYSTEM_SLUG}")
    assert state is not None


async def test_solar_production_sensor_exists(hass: HomeAssistant, setup_integration):
    """Test that the solar production power sensor is created."""
    state = hass.states.get(f"sensor.solar_production_power_{SYSTEM_SLUG}")
    assert state is not None


async def test_battery_soc_sensor_exists(hass: HomeAssistant, setup_integration):
    """Test that the battery state of charge sensor is created."""
    state = hass.states.get(f"sensor.battery_state_of_charge_{SYSTEM_SLUG}")
    assert state is not None


async def test_battery_soc_sensor_value(hass: HomeAssistant, setup_integration):
    """Test that the battery SoC sensor has the correct value from mock data."""
    state = hass.states.get(f"sensor.battery_state_of_charge_{SYSTEM_SLUG}")
    assert state is not None
    # Mock has stateOfCharge: 0.03, which is 3%
    assert float(state.state) == 3.0


async def test_battery_power_in_sensor_exists(hass: HomeAssistant, setup_integration):
    """Test that the battery power in sensor is created."""
    state = hass.states.get(f"sensor.battery_in_power_{SYSTEM_SLUG}")
    assert state is not None


async def test_battery_power_in_sensor_value(hass: HomeAssistant, setup_integration):
    """Test battery power in sensor shows charging power (negative = charging)."""
    state = hass.states.get(f"sensor.battery_in_power_{SYSTEM_SLUG}")
    assert state is not None
    # Mock has battery power: -908.7 (negative = charging in), so abs = 908.7
    assert float(state.state) == 908.7


async def test_battery_power_out_sensor_value(hass: HomeAssistant, setup_integration):
    """Test battery power out sensor shows 0 when battery is charging."""
    state = hass.states.get(f"sensor.battery_out_power_{SYSTEM_SLUG}")
    assert state is not None
    # Mock has battery power: -908.7 (negative = charging), so out = 0
    assert float(state.state) == 0


async def test_ev_chargers_aggregated_sensor_exists(
    hass: HomeAssistant, setup_integration
):
    """Test that the EV chargers aggregated power sensor is created."""
    state = hass.states.get(f"sensor.ev_chargers_aggregated_power_{SYSTEM_SLUG}")
    assert state is not None


async def test_heat_pumps_aggregated_sensor_exists(
    hass: HomeAssistant, setup_integration
):
    """Test that the heat pumps aggregated power sensor is created."""
    state = hass.states.get(f"sensor.heat_pumps_aggregated_power_{SYSTEM_SLUG}")
    assert state is not None


# --- Electricity price forecast attribute tests ---
# Mock timeseries keys are CET (UTC+1) despite "Z" suffix.
# Frozen at 08:30 UTC = 09:30 CET → current CET slot = 09:30Z
# Forecast starts at 09:45 CET (= 08:45 UTC) and outputs real UTC datetimes.


async def _setup_with_frozen_time(hass, mock_config_entry, mock_api):
    """Set up integration with time frozen at 2026-03-29T08:30 UTC."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.einskomma5grad.sensor_electricity_price.dt_util.now",
        return_value=FROZEN_NOW,
    ), patch(
        "custom_components.einskomma5grad.coordinator.dt_util.now",
        return_value=FROZEN_NOW,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id].coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    return hass.states.get(PRICE_ENTITY)


async def test_price_sensor_has_current_value(
    hass: HomeAssistant, mock_config_entry, mock_api, enable_custom_integrations
):
    """Test that the price sensor shows the current 15-min slot's price."""
    state = await _setup_with_frozen_time(hass, mock_config_entry, mock_api)
    assert state is not None
    # 09:30 CET entry (key "09:30Z"): marketPriceWithGridCostAndVat → rounded to 0.2031
    assert float(state.state) == 0.2031


async def test_price_forecast_is_list(
    hass: HomeAssistant, mock_config_entry, mock_api, enable_custom_integrations
):
    """Test that forecast attribute is a non-empty list."""
    state = await _setup_with_frozen_time(hass, mock_config_entry, mock_api)
    assert state is not None
    forecast = state.attributes.get("forecast")
    assert isinstance(forecast, list)
    assert len(forecast) > 0


async def test_price_forecast_entries_have_correct_keys(
    hass: HomeAssistant, mock_config_entry, mock_api, enable_custom_integrations
):
    """Test that each forecast entry has datetime and price keys."""
    state = await _setup_with_frozen_time(hass, mock_config_entry, mock_api)
    forecast = state.attributes["forecast"]
    for entry in forecast:
        assert "datetime" in entry
        assert "price" in entry
        assert isinstance(entry["price"], float)


async def test_price_forecast_count(
    hass: HomeAssistant, mock_config_entry, mock_api, enable_custom_integrations
):
    """Test forecast_hours_available matches expected count."""
    state = await _setup_with_frozen_time(hass, mock_config_entry, mock_api)
    # 145 future 15-min slots (09:45 CET through 21:45 CET next day, output as real UTC)
    assert state.attributes["forecast_hours_available"] == 145
    assert len(state.attributes["forecast"]) == 145


async def test_price_forecast_excludes_past_and_current(
    hass: HomeAssistant, mock_config_entry, mock_api, enable_custom_integrations
):
    """Test that forecast only contains future slots, not current or past."""
    state = await _setup_with_frozen_time(hass, mock_config_entry, mock_api)
    forecast = state.attributes["forecast"]
    # First forecast: 09:45 CET = 08:45 UTC (next slot after frozen 09:30 CET)
    assert forecast[0]["datetime"] == "2026-03-29T08:45:00+00:00"
    # Last entry: 21:45 CET next day = 20:45 UTC
    assert forecast[-1]["datetime"] == "2026-03-30T20:45:00+00:00"


async def test_price_forecast_sorted_chronologically(
    hass: HomeAssistant, mock_config_entry, mock_api, enable_custom_integrations
):
    """Test that forecast entries are sorted by datetime."""
    state = await _setup_with_frozen_time(hass, mock_config_entry, mock_api)
    forecast = state.attributes["forecast"]
    datetimes = [entry["datetime"] for entry in forecast]
    assert datetimes == sorted(datetimes)


async def test_price_summary_attributes(
    hass: HomeAssistant, mock_config_entry, mock_api, enable_custom_integrations
):
    """Test that price summary attributes exist and are floats."""
    state = await _setup_with_frozen_time(hass, mock_config_entry, mock_api)
    attrs = state.attributes
    assert "price_today_min" in attrs
    assert "price_today_max" in attrs
    assert "price_today_avg" in attrs
    assert isinstance(attrs["price_today_min"], float)
    assert isinstance(attrs["price_today_max"], float)
    assert isinstance(attrs["price_today_avg"], float)
    # From mock: energyMarketWithGridCostsAndVat summary
    assert attrs["price_today_min"] == 0.1487
    assert attrs["price_today_max"] == 0.3139
    assert attrs["price_today_avg"] == 0.2277


async def test_price_cheapest_upcoming_hour(
    hass: HomeAssistant, mock_config_entry, mock_api, enable_custom_integrations
):
    """Test cheapest upcoming hour attributes (average of 4 × 15-min slots)."""
    state = await _setup_with_frozen_time(hass, mock_config_entry, mock_api)
    attrs = state.attributes
    assert "cheapest_upcoming_hour" in attrs
    assert "cheapest_upcoming_price" in attrs
    # 13:00 CET = 12:00 UTC hour has the lowest average price across 4 slots
    assert attrs["cheapest_upcoming_hour"] == "2026-03-29T12:00:00+00:00"
    assert attrs["cheapest_upcoming_price"] == 0.1496


async def test_price_unit_from_metadata(
    hass: HomeAssistant, mock_config_entry, mock_api, enable_custom_integrations
):
    """Test that the unit is derived from timeseriesMetadata."""
    state = await _setup_with_frozen_time(hass, mock_config_entry, mock_api)
    # Mock metadata has currency=EUR, perUnit=kWh
    assert state.attributes.get("unit_of_measurement") == "EUR/kWh"
