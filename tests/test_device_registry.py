"""Tests for device registry integration."""

import json
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import SYSTEM_ID


@pytest.mark.asyncio
async def test_gateway_device_created(
    hass: HomeAssistant, setup_integration
):
    """Test that a Heartbeat gateway device is created."""
    registry = dr.async_get(hass)
    device = registry.async_get_device(
        identifiers={("einskomma5grad", "I032-002-000-000-068-P-X")}
    )
    assert device is not None
    assert device.manufacturer == "1KOMMA5\u00b0"
    assert device.model == "Heartbeat"
    assert device.serial_number == "I032-002-000-000-068-P-X"


@pytest.mark.asyncio
async def test_hybrid_device_created(
    hass: HomeAssistant, setup_integration
):
    """Test that a HYBRID (inverter/battery) device is created."""
    registry = dr.async_get(hass)
    device = registry.async_get_device(
        identifiers={("einskomma5grad", "SN-HY-000001")}
    )
    assert device is not None
    assert device.manufacturer == "Sungrow"
    assert device.model == "SH8.0RT-V112"


@pytest.mark.asyncio
async def test_ev_charger_device_created(
    hass: HomeAssistant, setup_integration
):
    """Test that an EV_CHARGER device is created."""
    registry = dr.async_get(hass)
    device = registry.async_get_device(
        identifiers={("einskomma5grad", "SN-EV-000001")}
    )
    assert device is not None
    assert device.manufacturer == "Mennekes"
    assert device.model == "AMTRON Compact 2.0S 11kW"
    assert device.name == "AMTRON Compact 2.0S 11kW"


@pytest.mark.asyncio
async def test_heat_pump_device_created(
    hass: HomeAssistant, setup_integration
):
    """Test that a HEAT_PUMP device is created."""
    registry = dr.async_get(hass)
    device = registry.async_get_device(
        identifiers={("einskomma5grad", "SN-HP-000001")}
    )
    assert device is not None
    assert device.manufacturer == "Vaillant"
    assert device.model == "VR940"


@pytest.mark.asyncio
async def test_child_devices_linked_via_gateway(
    hass: HomeAssistant, setup_integration
):
    """Test that asset devices are linked to the gateway via via_device."""
    registry = dr.async_get(hass)
    gateway = registry.async_get_device(
        identifiers={("einskomma5grad", "I032-002-000-000-068-P-X")}
    )
    hybrid = registry.async_get_device(
        identifiers={("einskomma5grad", "SN-HY-000001")}
    )
    assert gateway is not None
    assert hybrid is not None
    assert hybrid.via_device_id == gateway.id


@pytest.mark.asyncio
async def test_entities_still_work_without_assets(
    hass: HomeAssistant, mock_config_entry, mock_api, enable_custom_integrations
):
    """Test that entities work fine when status-and-assets returns None."""
    # Patch get_status_and_assets to return None (simulating API failure)
    with patch(
        "custom_components.einskomma5grad.api.system.System.get_status_and_assets",
        return_value=None,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        from custom_components.einskomma5grad.const import DOMAIN
        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id].coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # Entities should still exist
    state = hass.states.get(f"sensor.battery_in_power_{SYSTEM_ID}".replace("-", "_"))
    assert state is not None

    # No asset devices should be created
    registry = dr.async_get(hass)
    hybrid = registry.async_get_device(
        identifiers={("einskomma5grad", "SN-HY-000001")}
    )
    assert hybrid is None


@pytest.mark.asyncio
async def test_entities_still_work_without_gateway(
    hass: HomeAssistant, mock_config_entry, mock_api, enable_custom_integrations
):
    """Test that entities work when system has no deviceGateways."""
    # Modify mock to remove deviceGateways
    original_systems = mock_api["data"]["systems"]
    modified = json.loads(json.dumps(original_systems))
    modified["data"][0]["deviceGateways"] = []

    def get_router_no_gw(url, **kwargs):
        if "status-and-assets" in url:
            from tests.conftest import _make_response
            return _make_response(mock_api["data"]["status_and_assets"])
        if "/api/v2/systems" in url:
            from tests.conftest import _make_response
            path = url.split("/api/v2/systems")[1]
            if path and path != "/":
                return _make_response(modified["data"][0])
            return _make_response(modified)
        # Fall through to existing router for other URLs
        from tests.conftest import _make_response
        if "live-overview" in url:
            return _make_response(mock_api["data"]["live_overview"])
        if "market-prices" in url:
            return _make_response(mock_api["data"]["prices"])
        if "get-settings" in url:
            return _make_response(mock_api["data"]["ems_settings"])
        if "displayed-ev-charging-modes" in url:
            return _make_response(mock_api["data"]["ev_modes"])
        if "/devices/evs" in url:
            return _make_response(mock_api["data"]["ev_chargers"])
        raise ValueError(f"Unexpected GET URL: {url}")

    with patch(
        "custom_components.einskomma5grad.api.systems.requests.get",
        side_effect=get_router_no_gw,
    ), patch(
        "custom_components.einskomma5grad.api.system.requests.get",
        side_effect=get_router_no_gw,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        from custom_components.einskomma5grad.const import DOMAIN
        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id].coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # Entities should still exist
    state = hass.states.get(f"sensor.electricity_price_{SYSTEM_ID}".replace("-", "_"))
    assert state is not None

    # Gateway device should NOT be created
    registry = dr.async_get(hass)
    gateway = registry.async_get_device(
        identifiers={("einskomma5grad", "I032-002-000-000-068-P-X")}
    )
    assert gateway is None
