"""Test 1KOMMA5GRAD EMS switch entity."""

from homeassistant.core import HomeAssistant

from tests.conftest import SYSTEM_SLUG


async def test_ems_switch_exists(hass: HomeAssistant, setup_integration):
    """Test that the EMS auto mode switch is created."""
    state = hass.states.get(
        f"switch.heartbeat_automatic_mode_{SYSTEM_SLUG}"
    )
    assert state is not None


async def test_ems_switch_state(hass: HomeAssistant, setup_integration):
    """Test EMS switch reflects overrideAutoSettings from mock data."""
    state = hass.states.get(
        f"switch.heartbeat_automatic_mode_{SYSTEM_SLUG}"
    )
    assert state is not None
    # Mock has overrideAutoSettings: false, so auto mode is ON
    assert state.state == "on"
