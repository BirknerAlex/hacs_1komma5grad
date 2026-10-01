"""Regression tests for EV state of charge handling."""

from typing import cast
from unittest.mock import MagicMock

from custom_components.einskomma5grad.api.ev_charger import ChargingMode, EVCharger


def _charger() -> EVCharger:
    api = MagicMock()
    api.HEARTBEAT_API = "https://heartbeat.example"
    api.get_token.return_value = "token"
    api.patch.return_value = MagicMock(status_code=200)
    system = MagicMock()
    system.id.return_value = "sys"
    data = {
        "id": "ev1",
        "chargingMode": "SMART_CHARGE",
        "manualSoc": 0.5,
    }
    return EVCharger(api, system, data)


def _patch_mock(charger: EVCharger) -> MagicMock:
    return cast(MagicMock, charger._api).patch


def test_set_current_soc_sends_and_caches_decimal():
    """The API uses 0-1; the cache must keep that unit so current_soc() reads back correctly."""
    charger = _charger()

    charger.set_current_soc(80)

    assert _patch_mock(charger).call_args.kwargs["json"]["manualSoc"] == 0.8
    assert charger.current_soc() == 80.0


def test_patches_go_to_v2_site_asset_with_app_body():
    """PATCH the v2 site asset, sending the same envelope as the app."""
    charger = _charger()
    charger._data.update(
        {
            "type": "EV",
            "connectionStatus": {"status": "UNKNOWN"},
            "departureTime": "08:00",
            "targetSoc": 0.59,
            "defaultSoc": 0.2,
        }
    )

    charger.set_current_soc(60)
    kwargs = _patch_mock(charger).call_args.kwargs
    assert kwargs["url"] == "https://heartbeat.example/api/v2/sites/sys/assets/evs/ev1"
    assert kwargs["json"] == {
        "id": "ev1",
        "connectionStatus": {"status": "UNKNOWN"},
        "manualSoc": 0.6,
        "type": "EV",
    }

    charger.set_charging_mode(ChargingMode.SOLAR_CHARGE)
    assert _patch_mock(charger).call_args.kwargs["json"] == {
        "id": "ev1",
        "connectionStatus": {"status": "UNKNOWN"},
        "departureTime": "08:00",
        "targetSoc": 0.59,
        "defaultSoc": 0.2,
        "chargingMode": "SOLAR_CHARGE",
        "type": "EV",
    }
    assert charger.charging_mode() == ChargingMode.SOLAR_CHARGE


def test_reads_flat_v2_fields():
    """Name, charger and mode come from the flat v2 asset shape."""
    charger = _charger()
    charger._data.update({"name": "Tesla", "chargerId": "c1"})

    assert charger.name() == "Tesla"
    assert charger.assigned_charger_id() == "c1"
    assert charger.charging_mode() == ChargingMode.SMART_CHARGE
