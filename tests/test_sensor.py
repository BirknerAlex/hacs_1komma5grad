"""Test 1KOMMA5GRAD sensor entities."""

from homeassistant.core import HomeAssistant

from tests.conftest import SYSTEM_SLUG


async def test_electricity_price_sensor_exists(hass: HomeAssistant, setup_integration):
    """Test that the electricity price sensor is created."""
    state = hass.states.get(f"sensor.electricity_price_{SYSTEM_SLUG}")
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
