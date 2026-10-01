"""Tests for device registry integration."""

import json
import re
from typing import cast
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

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
        if "/api/v1/systems/" in url and url.endswith("/details"):
            from tests.conftest import _make_response
            return _make_response(modified["data"][0])
        if re.search(r"/api/v4/systems/[^/]+$", url):
            from tests.conftest import _make_response
            return _make_response(modified["data"][0])
        from tests.conftest import insight_response
        if (insight := insight_response(url)) is not None:
            return insight
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
        if "energy-historical" in url:
            return _make_response(mock_api["data"]["energy_today"])
        if "live-overview" in url:
            return _make_response(mock_api["data"]["live_overview"])
        if "market-prices" in url:
            return _make_response(mock_api["data"]["prices"])
        if "get-settings" in url:
            return _make_response(mock_api["data"]["ems_settings"])
        if "displayed-ev-charging-modes" in url:
            return _make_response(mock_api["data"]["ev_modes"])
        if "/assets/evs" in url:
            return _make_response(mock_api["data"]["ev_chargers"])
        raise ValueError(f"Unexpected GET URL: {url}")

    mock_api["client"].get.side_effect = get_router_no_gw
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


def _assets_with_duplicates(mock_api: dict) -> dict:
    data = json.loads(json.dumps(mock_api["data"]["status_and_assets"]))
    data["assets"] += [
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "type": "EV_CHARGER",
            "manufacturer": "Easee",
            "model": "Home",
            "serialnumber": "SN-EV-000002",
        },
        {
            "id": "00000000-0000-0000-0000-000000000022",
            "type": "HEAT_PUMP",
            "manufacturer": "Vaillant",
            "model": "VR940",
            "serialnumber": "SN-HP-000002",
        },
    ]
    return data


@pytest.mark.asyncio
async def test_multiple_assets_of_same_type_create_devices(
    hass: HomeAssistant, mock_config_entry, mock_api, enable_custom_integrations
):
    """Every asset of a type gets its own device, and EV entities follow chargerId."""
    with patch(
        "custom_components.einskomma5grad.api.system.System.get_status_and_assets",
        return_value=_assets_with_duplicates(mock_api),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    for serial in ("SN-EV-000001", "SN-EV-000002", "SN-HP-000001", "SN-HP-000002"):
        assert device_registry.async_get_device(
            identifiers={("einskomma5grad", serial)}
        ), serial

    second_charger = device_registry.async_get_device(
        identifiers={("einskomma5grad", "SN-EV-000002")}
    )
    assert second_charger is not None
    ev_entities = [
        e
        for e in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if "_ev_charging_mode_" in e.unique_id or "_ev_current_soc_" in e.unique_id
    ]
    assert ev_entities
    assert {e.device_id for e in ev_entities} == {second_charger.id}


@pytest.mark.asyncio
async def test_two_evs_attach_to_their_own_chargers(
    hass: HomeAssistant, mock_config_entry, mock_api, enable_custom_integrations
):
    """Two EVs get separate entities, each on its assigned charger (or the first as fallback)."""
    evs = json.loads(json.dumps(mock_api["data"]["ev_chargers"]))
    second = json.loads(json.dumps(evs[0]))
    second["id"] = "00000000-0000-0000-0000-0000000000aa"
    second["chargerId"] = "00000000-0000-0000-0000-000000000001"
    second["name"] = "Tesla"  # same name as the first EV
    evs[0]["chargerId"] = None  # falls back to the first charger
    evs.append(second)
    mock_api["data"]["ev_chargers"][:] = evs

    with patch(
        "custom_components.einskomma5grad.api.system.System.get_status_and_assets",
        return_value=_assets_with_duplicates(mock_api),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    first_dev = device_registry.async_get_device(
        identifiers={("einskomma5grad", "SN-EV-000001")}
    )
    second_dev = device_registry.async_get_device(
        identifiers={("einskomma5grad", "SN-EV-000002")}
    )
    assert first_dev is not None
    assert second_dev is not None
    modes = {
        e.unique_id: e
        for e in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if "_ev_charging_mode_" in e.unique_id
    }
    assert len(modes) == 2
    assert modes[f"einskomma5grad_ev_charging_mode_{SYSTEM_ID}_00000000-0000-0000-0000-000000000000"].device_id == first_dev.id
    assert modes[f"einskomma5grad_ev_charging_mode_{SYSTEM_ID}_00000000-0000-0000-0000-0000000000aa"].device_id == second_dev.id


def _reporter_calls(evs: list[str | None], asset_ids: list[str]):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from custom_components.einskomma5grad.coordinator import Coordinator

    coordinator = SimpleNamespace(error_reporter=MagicMock())
    chargers = [SimpleNamespace(assigned_charger_id=lambda a=a: a) for a in evs]
    assets = [SimpleNamespace(asset_id=i) for i in asset_ids]
    device_data = SimpleNamespace(assets_by_type={"EV_CHARGER": assets})
    Coordinator._report_multiple_chargers(cast(Coordinator, coordinator), chargers, device_data)
    return coordinator.error_reporter.capture_api_issue.call_args_list


def test_multiple_chargers_reported_as_counts_only():
    (call,) = _reporter_calls(["a", None], ["a", "b"])
    assert call.args[0] == "multiple_chargers"
    assert call.args[3] == {
        "evs": 2,
        "ev_charger_assets": 2,
        "evs_with_assigned_charger": 1,
        "distinct_assigned_chargers": 1,
        "assigned_matching_asset": 1,
    }


def test_single_charger_not_reported():
    assert _reporter_calls(["a"], ["a"]) == []


FIRST_CHARGER = "00000000-0000-0000-0000-000000000010"
SECOND_CHARGER = "00000000-0000-0000-0000-000000000001"


async def _setup_with_cards(hass, mock_config_entry, mock_api, powers: dict[str, float]):
    mock_api["data"]["live_overview"]["summaryCards"]["evChargers"] = [
        {"applianceId": cid, "currentSoc": None, "power": {"value": p, "unit": "W"}}
        for cid, p in powers.items()
    ]
    with patch(
        "custom_components.einskomma5grad.api.system.System.get_status_and_assets",
        return_value=_assets_with_duplicates(mock_api),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_per_charger_power_sensors_for_multiple_chargers(
    hass: HomeAssistant, mock_config_entry, mock_api, enable_custom_integrations
):
    """Each charger gets its own power sensor on its own device; existing ids stay."""
    await _setup_with_cards(
        hass, mock_config_entry, mock_api, {FIRST_CHARGER: 3700, SECOND_CHARGER: 0}
    )
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    for charger_id, serial, power in (
        (FIRST_CHARGER, "SN-EV-000001", "3700"),
        (SECOND_CHARGER, "SN-EV-000002", "0"),
    ):
        entity_id = entity_registry.async_get_entity_id(
            "sensor",
            "einskomma5grad",
            f"einskomma5grad_ev_charger_power_{SYSTEM_ID}_{charger_id}",
        )
        assert entity_id, charger_id
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        device = device_registry.async_get_device(
            identifiers={("einskomma5grad", serial)}
        )
        assert device is not None
        assert entry.device_id == device.id
        state = hass.states.get(entity_id)
        assert state is not None
        assert float(state.state) == float(power)

    # The aggregated sensor keeps its unique id
    assert entity_registry.async_get_entity_id(
        "sensor", "einskomma5grad", f"einskomma5grad_evChargersAggregated_{SYSTEM_ID}"
    )


@pytest.mark.asyncio
async def test_no_per_charger_sensor_for_single_charger(
    hass: HomeAssistant, mock_config_entry, mock_api, enable_custom_integrations
):
    await _setup_with_cards(hass, mock_config_entry, mock_api, {FIRST_CHARGER: 100})
    entity_registry = er.async_get(hass)
    assert not [
        e
        for e in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if "_ev_charger_power_" in e.unique_id
    ]
