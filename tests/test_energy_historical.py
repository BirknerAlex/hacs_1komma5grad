"""Tests for the energy-historical fallback right after midnight."""

import datetime
from typing import cast
from unittest.mock import MagicMock

import pytest

from custom_components.einskomma5grad.api.error import RequestError
from custom_components.einskomma5grad.api.system import System


def _system(*responses) -> System:
    client = MagicMock()
    client.HEARTBEAT_API = "https://heartbeat.example"
    client.get_token.return_value = "token"
    client.get.side_effect = list(responses)
    return System(client, {"id": "sys"})


def _get(system: System) -> MagicMock:
    return cast(MagicMock, system.client).get


def _response(status, body=None):
    res = MagicMock(status_code=status, text="boom")
    res.json.return_value = body
    return res


DAY = datetime.date(2026, 10, 2)


def test_falls_back_to_15m_when_daily_aggregate_is_missing():
    system = _system(_response(500), _response(200, {"energyProduced": {"value": 0}}))

    assert system.get_energy_historical(DAY) == {"energyProduced": {"value": 0}}
    resolutions = [c.kwargs["params"]["resolution"] for c in _get(system).call_args_list]
    assert resolutions == ["1d", "15m"]


def test_raises_when_15m_fails_too():
    system = _system(_response(500), _response(500))

    with pytest.raises(RequestError):
        system.get_energy_historical(DAY)
    assert _get(system).call_count == 2


def test_no_fallback_for_explicit_resolution():
    system = _system(_response(500))

    with pytest.raises(RequestError):
        system.get_energy_historical(DAY, resolution="15m")
    assert _get(system).call_count == 1


def test_no_fallback_when_rate_limited():
    """A retry at 15m cannot help while the API throttles us."""
    system = _system(_response(429))

    with pytest.raises(RequestError):
        system.get_energy_historical(DAY)
    assert _get(system).call_count == 1
