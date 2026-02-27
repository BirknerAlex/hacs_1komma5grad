"""Test 1KOMMA5GRAD EV state of charge number entity."""

from homeassistant.core import HomeAssistant


async def test_ev_soc_number_exists(hass: HomeAssistant, setup_integration):
    """Test that the EV SoC number entity is created."""
    state = hass.states.get("number.ev_current_state_of_charge_tesla")
    assert state is not None


async def test_ev_soc_number_unavailable_when_not_smart_charge(
    hass: HomeAssistant, setup_integration
):
    """Test EV SoC is unavailable when not in SMART_CHARGE mode."""
    state = hass.states.get("number.ev_current_state_of_charge_tesla")
    assert state is not None
    # Mock EV has chargingMode: "QUICK_CHARGE" so current_soc returns None
    # which makes the entity unavailable
    assert state.state == "unavailable"
