"""Optional endpoints that return invalid JSON must not fail the whole refresh."""

from unittest.mock import MagicMock

import pytest

from custom_components.einskomma5grad.api.error import RequestError
from custom_components.einskomma5grad.api.system import System


def _system_returning_invalid_json() -> System:
    res = MagicMock(status_code=200)
    res.json.side_effect = ValueError("Expecting value")
    client = MagicMock()
    client.HEARTBEAT_API = "https://heartbeat.example"
    client.get_token.return_value = "token"
    client.get.return_value = res
    return System(client, {"id": "sys"})


def test_details_with_invalid_json_are_skipped():
    assert _system_returning_invalid_json().get_details() is None


def test_insight_with_invalid_json_raises_request_error():
    """RequestError lets the coordinator keep the previous value for that insight."""
    with pytest.raises(RequestError, match="invalid JSON"):
        _system_returning_invalid_json().get_heartbeat_prices()
