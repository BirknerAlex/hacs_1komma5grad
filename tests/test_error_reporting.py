"""Tests for opt-in error reporting."""

import logging
from unittest.mock import patch

import pytest
import sentry_sdk
from homeassistant.core import HomeAssistant

from custom_components.einskomma5grad.api.client import Client
from custom_components.einskomma5grad.error_reporting import (
    ErrorReporter,
    _before_send,
    _before_send_log,
    _before_send_transaction,
    _traces_sample_rate,
)

PACKAGE_FRAME = {"module": "custom_components.einskomma5grad.coordinator"}
OTHER_FRAME = {"module": "homeassistant.core"}


def _event(frame: dict) -> dict:
    return {
        "server_name": "my-host",
        "user": {"ip_address": "1.2.3.4"},
        "exception": {"values": [{"stacktrace": {"frames": [frame]}}]},
    }


def test_before_send_keeps_and_scrubs_own_events() -> None:
    """Events from this integration are kept without host info but with the user id."""
    result = _before_send(_event(PACKAGE_FRAME), {})
    assert result is not None
    assert "server_name" not in result
    assert result["user"] == {"ip_address": "1.2.3.4"}


def test_before_send_drops_foreign_events() -> None:
    """Events without frames from this integration are dropped."""
    assert _before_send(_event(OTHER_FRAME), {}) is None


def test_before_send_keeps_own_logger_messages() -> None:
    """Message events from this integration's loggers have no frames but are kept."""
    event = {"logger": "custom_components.einskomma5grad.api.client", "message": "x"}
    assert _before_send(event, {}) is event
    assert _before_send({"logger": "homeassistant.core"}, {}) is None


OWN_LOGGER = "custom_components.einskomma5grad.coordinator"


async def _capture(hass: HomeAssistant, emit) -> tuple[list[dict], list[dict]]:
    """Run `emit` with a reporter and return the (events, logs) it sent."""
    envelopes: list = []
    logs: list[dict] = []
    reporter = await ErrorReporter.async_create(hass)
    reporter.set_system_ids(["sys-1"])
    with (
        patch.object(reporter._client.transport, "capture_envelope", envelopes.append),
        patch.object(reporter._client.log_batcher, "add", side_effect=logs.append),
    ):
        emit()
    await reporter.async_close(hass)
    events = [
        item.payload.json
        for envelope in envelopes
        for item in envelope.items
        if item.type == "event"
    ]
    return events, logs


@pytest.mark.parametrize(
    ("logger_name", "expected_events"),
    [
        pytest.param(OWN_LOGGER, 1, id="own"),
        pytest.param("homeassistant.core", 0, id="foreign"),
    ],
)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_handler_only_reports_own_logger(
    hass: HomeAssistant, logger_name: str, expected_events: int
) -> None:
    """Logged exceptions are reported only from this integration's loggers."""

    def emit() -> None:
        try:
            raise ValueError("boom")
        except ValueError:
            logging.getLogger(logger_name).exception("failed")

    events, _ = await _capture(hass, emit)

    assert len(events) == expected_events
    if events:
        assert events[0]["exception"]["values"][0]["type"] == "ValueError"
        assert events[0]["user"] == {"id": "sys-1"}


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_warning_without_exception_is_an_event(hass: HomeAssistant) -> None:
    """Warnings are events with a groupable template; info is not an event."""
    logger = logging.getLogger(OWN_LOGGER)

    def emit() -> None:
        logger.warning("Failed to get %s", "prices")
        logger.info("quiet")

    events, _ = await _capture(hass, emit)

    assert len(events) == 1
    assert events[0]["level"] == "warning"
    assert events[0]["logentry"]["message"] == "Failed to get %s"
    assert events[0]["logentry"]["formatted"] == "Failed to get prices"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_info_and_above_are_sent_as_logs(hass: HomeAssistant) -> None:
    """Logs carry the system id but no host, process or local path info."""
    logger = logging.getLogger(OWN_LOGGER)
    logger.setLevel(logging.DEBUG)

    def emit() -> None:
        logger.debug("not sent")
        logger.info("Refreshed %s", "prices")

    _, logs = await _capture(hass, emit)

    assert [log["body"] for log in logs] == ["Refreshed prices"]
    attributes = logs[0]["attributes"]
    assert attributes["user.id"] == "sys-1"
    assert not attributes.get("code.file.path", "").startswith("/")
    assert attributes["sentry.release"]
    for key in ("server.address", "process.pid", "thread.name"):
        assert key not in attributes


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_events_do_not_include_global_scope_data(hass: HomeAssistant) -> None:
    """Data on Home Assistant's own global/isolation scope never reaches our events."""
    global_scope = sentry_sdk.get_global_scope()
    isolation_scope = sentry_sdk.get_isolation_scope()
    current_scope = sentry_sdk.get_current_scope()
    global_scope.set_tag("from", "ha-global")
    isolation_scope.set_tag("from", "ha-isolation")
    if set_attribute := getattr(global_scope, "set_attribute", None):  # newer SDKs
        set_attribute("from", "ha-global")
    try:
        events, logs = await _capture(
            hass, lambda: logging.getLogger(OWN_LOGGER).warning("hello")
        )
    finally:
        global_scope._tags.pop("from", None)
        getattr(global_scope, "_attributes", {}).pop("from", None)
        isolation_scope._tags.pop("from", None)

    assert events
    assert "from" not in events[0].get("tags", {})
    assert "from" not in logs[0]["attributes"]
    assert sentry_sdk.get_current_scope() is current_scope
    assert sentry_sdk.get_isolation_scope() is isolation_scope


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_global_sentry_untouched(hass: HomeAssistant) -> None:
    """Creating a reporter does not bind a client to the global scope."""
    reporter = await ErrorReporter.async_create(hass)
    assert not sentry_sdk.get_global_scope().client.is_active()
    await reporter.async_close(hass)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_system_ids_set_as_user(hass: HomeAssistant) -> None:
    """The Heartbeat system ids identify the user on the reporter's own scope."""
    reporter = await ErrorReporter.async_create(hass)
    reporter.set_system_ids(["b", "a"])
    assert reporter._scope._user == {"id": "a,b"}
    await reporter.async_close(hass)


@pytest.mark.parametrize(
    ("version", "rate"),
    [("1.5.1-dev.1", 1.0), ("1.5.1", 0.1)],
)
def test_traces_sample_rate(version: str, rate: float) -> None:
    """Pre-releases are fully traced, releases are sampled at 10%."""
    assert _traces_sample_rate(version) == rate


def test_before_send_transaction_keeps_only_trace_context() -> None:
    """Transactions lose host info and every context but the trace."""
    event = {
        "server_name": "my-host",
        "request": {"url": "x"},
        "contexts": {"trace": {"trace_id": "t"}, "os": {"name": "linux"}},
    }
    result = _before_send_transaction(event, {})
    assert result == {"contexts": {"trace": {"trace_id": "t"}}}


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_http_requests_are_traced(hass: HomeAssistant) -> None:
    """A traced refresh sends one transaction with an http.client span per request."""
    sent: list[dict] = []
    reporter = await ErrorReporter.async_create(hass)
    reporter._client.options["traces_sample_rate"] = 1.0
    with patch.object(
        reporter._client, "capture_event", side_effect=lambda *a, **k: sent.append(k["event"] if "event" in k else a[0])
    ):
        client = Client("user", "pw")
        client.tracer = reporter.http_span
        response = type("R", (), {"status_code": 200})()
        with (
            patch("requests.get", return_value=response),
            reporter.trace("refresh", op="coordinator.refresh"),
        ):
            await hass.async_add_executor_job(
                lambda: client.get("https://example.com/a/b?secret=1")
            )
    await reporter.async_close(hass)

    assert len(sent) == 1
    assert sent[0]["type"] == "transaction"
    (span,) = sent[0]["spans"]
    assert span["op"] == "http.client"
    assert span["description"] == "GET https://example.com/a/b"
    assert span["data"]["http.response.status_code"] == 200
    assert not sentry_sdk.get_global_scope().client.is_active()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_api_issue_is_sent_once_per_interval(hass: HomeAssistant) -> None:
    """A persistent API problem is reported once, with anonymized details."""

    envelopes: list = []
    reporter = await ErrorReporter.async_create(hass)
    with patch.object(reporter._client.transport, "capture_envelope", envelopes.append):
        for _ in range(3):
            reporter.capture_api_issue("http_error", "GET https://h/x", 500, {"body": "str"})
        try:
            {}["chargeSettings"]
        except KeyError as err:
            reporter.capture_api_issue("parse_error", "refresh", None, {"responses": {}}, err)
    await reporter.async_close(hass)

    events = [i.payload.json for e in envelopes for i in e.items if i.type == "event"]
    assert len(events) == 2
    assert events[0]["extra"]["body"] == "str"
    assert events[0]["tags"]["api_issue"] == "http_error"
    assert events[1]["exception"]["values"][0]["type"] == "KeyError"
    assert "chargeSettings" in events[1]["extra"]["error"]


def test_before_send_masks_personal_data_in_messages() -> None:
    """Exception values and log messages never carry emails or identifiers."""
    event = _event(PACKAGE_FRAME)
    event["exception"]["values"][0]["value"] = "Failed to get systems: me@example.com"
    event["logentry"] = {
        "message": "Login failed: %s",
        "formatted": "Login failed: me@example.com 01M3WG0J2SWWASACH48FAXYZ12",
    }
    result = _before_send(event, {})
    assert result["exception"]["values"][0]["value"] == "Failed to get systems: <email>"
    assert result["logentry"]["formatted"] == "Login failed: <email> <id>"


def test_before_send_log_masks_body_and_parameters() -> None:
    log = {
        "body": "Login failed for me@example.com",
        "attributes": {"sentry.message.parameter.0": "me@example.com", "other": 1},
    }
    result = _before_send_log(log, {})
    assert result["body"] == "Login failed for <email>"
    assert result["attributes"]["sentry.message.parameter.0"] == "<email>"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_reporter_closed_when_setup_fails(
    hass: HomeAssistant, mock_api, mock_config_entry
) -> None:
    """A failed setup detaches the reporter's logging handlers."""
    package_logger = logging.getLogger("custom_components.einskomma5grad")
    before = list(package_logger.handlers)
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={"scan_interval": 60, "error_reporting": True}
    )
    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        side_effect=RuntimeError("boom"),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert package_logger.handlers == before
