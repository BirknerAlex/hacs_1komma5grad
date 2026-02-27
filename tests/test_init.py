"""Test 1KOMMA5GRAD integration setup and unload."""

from unittest.mock import MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.einskomma5grad.const import DOMAIN
from tests.conftest import _make_response


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


async def test_setup_entry_empty_device_gateways(
    hass: HomeAssistant, mock_config_entry, mock_api, enable_custom_integrations
):
    """Test that the integration loads when deviceGateways is an empty array."""
    mock_api["data"]["systems"]["data"][0]["deviceGateways"] = []

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id].coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.electricity_price_a1b2c3d4_0000_0000_0000_000000000001") is not None
    assert hass.states.get("switch.heartbeat_automatic_mode_a1b2c3d4_0000_0000_0000_000000000001") is not None
    assert hass.states.get("select.ev_charging_mode_tesla") is not None


async def test_setup_entry_ems_settings_error(
    hass: HomeAssistant, mock_config_entry, enable_custom_integrations
):
    """Test that the integration retries setup when get_ems_settings fails."""
    from tests.conftest import load_mock

    mock_data = {
        "systems": load_mock("GET_systems.json"),
        "live_overview": load_mock("GET_systems_id_live-overview.json"),
        "prices": load_mock("GET_systems_id_charts_market-prices.json"),
        "ev_chargers": load_mock("GET_systems_id_devices_evs.json"),
        "ev_modes": load_mock(
            "GET_sites_id_assets_evs_displayed-ev-charging-modes.json"
        ),
    }

    def get_router(url, **kwargs):
        if "/api/v2/systems" in url:
            path = url.split("/api/v2/systems")[1]
            if path and path != "/":
                return _make_response(mock_data["systems"]["data"][0])
            return _make_response(mock_data["systems"])
        if "live-overview" in url:
            return _make_response(mock_data["live_overview"])
        if "market-prices" in url:
            return _make_response(mock_data["prices"])
        if "get-settings" in url:
            # Simulate HTTP 500 error
            return _make_response({"error": "Internal Server Error"}, status=500)
        if "displayed-ev-charging-modes" in url:
            return _make_response(mock_data["ev_modes"])
        if "/devices/evs" in url:
            return _make_response(mock_data["ev_chargers"])
        raise ValueError(f"Unexpected GET URL: {url}")

    def post_router(url, **kwargs):
        if "set-manual-override" in url:
            return _make_response({}, status=201)
        raise ValueError(f"Unexpected POST URL: {url}")

    def patch_router(url, **kwargs):
        if "/devices/evs/" in url:
            return _make_response({})
        raise ValueError(f"Unexpected PATCH URL: {url}")

    with (
        patch(
            "custom_components.einskomma5grad.coordinator.Client"
        ) as mock_client_cls,
        patch(
            "custom_components.einskomma5grad.api.systems.requests.get",
            side_effect=get_router,
        ),
        patch(
            "custom_components.einskomma5grad.api.system.requests.get",
            side_effect=get_router,
        ),
        patch(
            "custom_components.einskomma5grad.api.system.requests.post",
            side_effect=post_router,
        ),
        patch(
            "custom_components.einskomma5grad.api.ev_charger.requests.patch",
            side_effect=patch_router,
        ),
    ):
        client = MagicMock()
        client.get_token.return_value = "mock_token"
        client.HEARTBEAT_API = "https://heartbeat.1komma5grad.com"
        mock_client_cls.return_value = client

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id].coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # Other entities should still work
        assert hass.states.get("sensor.electricity_price_a1b2c3d4_0000_0000_0000_000000000001") is not None
        assert hass.states.get("select.ev_charging_mode_tesla") is not None

        # EMS switch should exist but show unavailable
        ems_state = hass.states.get("switch.heartbeat_automatic_mode_a1b2c3d4_0000_0000_0000_000000000001")
        assert ems_state is not None
        assert ems_state.state == "unavailable"
