"""Tests for anonymized API response reporting."""

from unittest.mock import MagicMock, patch

import requests

from custom_components.einskomma5grad.api.anonymize import (
    describe_body,
    describe_payload,
    mask_text,
    url_template,
)
from custom_components.einskomma5grad.api.client import Client

SYSTEM_ID = "01M3WG0J2SWWASACH48FAXYZ12"


def _response(status: int, payload=None, text: str | None = None) -> requests.Response:
    res = requests.Response()
    res.status_code = status
    res._content = (text if text is not None else __import__("json").dumps(payload)).encode()
    return res


def test_describe_payload_keeps_structure_not_values() -> None:
    """Only keys and types survive; enum-like keys keep their (masked) value."""
    data = {
        "id": SYSTEM_ID,
        "owner": {"email": "me@example.com", "name": "Jane Doe"},
        "power": 12.5,
        "online": True,
        "chargeSettings": {"chargingMode": "SMART_CHARGE"},
        "items": [{"a": 1}, {"a": 2, "b": None}],
        SYSTEM_ID: {"x": 1},
    }
    shape = describe_payload(data)
    assert shape == {
        "id": "str",
        "owner": {"email": "str", "name": "str"},
        "power": "float",
        "online": "bool",
        "chargeSettings": {"chargingMode": "SMART_CHARGE"},
        "items": [{"a": "int", "b": "null"}],
        "<id>": {"x": "int"},
    }
    assert "example.com" not in str(shape)
    assert "Jane" not in str(shape)


def test_mask_text_masks_personal_data() -> None:
    text = f"user me@example.com system {SYSTEM_ID} serial 12345678"
    assert mask_text(text) == "user <email> system <id> serial <n>"
    assert len(mask_text("x" * 1000)) == 300


def test_url_template_drops_ids_and_query() -> None:
    url = f"https://heartbeat.1komma5grad.com/api/v2/sites/{SYSTEM_ID}/status?token=abc"
    assert url_template(url) == "https://heartbeat.1komma5grad.com/api/v2/sites/{id}/status"


def test_describe_body_falls_back_to_masked_text() -> None:
    assert describe_body(_response(502, text="<html>Bad gateway me@example.com</html>")) == (
        "<html>Bad gateway <email></html>"
    )
    assert describe_body(_response(500, {"error": "boom", "trace": "secret"})) == {
        "error": "boom",
        "trace": "str",
    }


def _client() -> tuple[Client, list]:
    client = Client("user", "pw")
    issues: list = []
    client.on_issue = lambda *args: issues.append(args)
    return client, issues


def _get(client: Client, url: str, res: requests.Response):
    with patch("requests.get", return_value=res):
        return client.get(url)


def test_server_error_is_reported_anonymized() -> None:
    client, issues = _client()
    url = f"https://heartbeat.1komma5grad.com/api/v3/systems/{SYSTEM_ID}/live-overview?x=1"
    _get(client, url, _response(500, {"error": "boom"}))
    assert issues == [
        (
            "http_error",
            "GET https://heartbeat.1komma5grad.com/api/v3/systems/{id}/live-overview",
            500,
            {"body": {"error": "boom"}},
        )
    ]


def test_expected_statuses_and_auth_host_are_ignored() -> None:
    client, issues = _client()
    _get(client, "https://heartbeat.1komma5grad.com/x", _response(429, {}))
    _get(client, "https://heartbeat.1komma5grad.com/x", _response(401, {}))
    _get(client, "https://auth.1komma5grad.com/authorize", _response(500, {}))
    assert issues == []


def test_invalid_json_is_reported_and_still_raises_for_caller() -> None:
    client, issues = _client()
    res = _get(client, "https://heartbeat.1komma5grad.com/x", _response(200, text="<html>"))
    assert issues[0][0] == "invalid_json"
    try:
        res.json()
    except ValueError:
        pass
    else:
        raise AssertionError("caller must still see the parse error")


def test_response_shape_is_remembered_and_json_cached() -> None:
    client, issues = _client()
    res = _get(client, "https://heartbeat.1komma5grad.com/api/x", _response(200, {"a": 1}))
    assert client.response_shapes == {"GET https://heartbeat.1komma5grad.com/api/x": {"a": "int"}}
    assert res.json() == {"a": 1}
    assert issues == []


def test_no_inspection_without_hook() -> None:
    client = Client("user", "pw")
    res = MagicMock()
    with patch("requests.get", return_value=res):
        assert client.get("https://heartbeat.1komma5grad.com/x") is res
    assert client.response_shapes == {}
