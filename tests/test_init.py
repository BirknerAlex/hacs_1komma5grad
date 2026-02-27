"""Test 1KOMMA5GRAD integration setup and unload."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.einskomma5grad.const import DOMAIN


async def test_setup_entry(hass: HomeAssistant, setup_integration):
    """Test that the integration sets up correctly."""
    entry = setup_integration
    assert entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]


async def test_unload_entry(hass: HomeAssistant, setup_integration):
    """Test that the integration unloads correctly."""
    entry = setup_integration
    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.entry_id not in hass.data[DOMAIN]
