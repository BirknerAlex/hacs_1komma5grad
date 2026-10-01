"""Opt-in error reporting to GlitchTip, isolated from Home Assistant's own Sentry setup."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager, nullcontext
from copy import copy
from typing import Any

import sentry_sdk
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration
from sentry_sdk.integrations.logging import EventHandler, SentryLogsHandler
from sentry_sdk.scope import Scope, use_isolation_scope, use_scope
from sentry_sdk.tracing import Span
from sentry_sdk.utils import event_from_exception, exc_info_from_error

from .api.anonymize import mask_text
from .const import DOMAIN

DSN = "https://de662e72eaa24d5995f8f942e121e333@glitchtip.tyrola.dev/8"

_PACKAGE_LOGGER = f"custom_components.{DOMAIN}"

# An API problem that persists is reported once per this many seconds.
API_ISSUE_INTERVAL = 6 * 3600

TRACES_SAMPLE_RATE_DEV = 1.0
TRACES_SAMPLE_RATE_PROD = 0.1


def _traces_sample_rate(version: str) -> float:
    """Sample every trace on pre-releases (e.g. 1.5.1-dev.1), a tenth on releases."""
    return TRACES_SAMPLE_RATE_DEV if "dev" in version else TRACES_SAMPLE_RATE_PROD


def _before_send(event: Any, hint: Any) -> Any:
    """Drop events that do not originate from this integration and strip host info.

    The user is kept: it only carries the pseudonymous Heartbeat system id.
    """
    frames = [
        frame
        for exception in event.get("exception", {}).get("values", [])
        for frame in exception.get("stacktrace", {}).get("frames", [])
    ]
    own_frame = any(DOMAIN in (frame.get("module") or "") for frame in frames)
    own_logger = (event.get("logger") or "").startswith(_PACKAGE_LOGGER)
    if not (own_frame or own_logger):
        return None
    for frame in frames:
        frame.pop("abs_path", None)  # may contain the local user name
    # API errors and log messages can embed raw response bodies.
    for exception in event.get("exception", {}).get("values", []):
        if isinstance(exception.get("value"), str):
            exception["value"] = mask_text(exception["value"])
    logentry = event.get("logentry") or {}
    for key in ("message", "formatted"):
        if isinstance(logentry.get(key), str):
            logentry[key] = mask_text(logentry[key])
    if isinstance(event.get("message"), str):
        event["message"] = mask_text(event["message"])
    for key in ("server_name", "request", "contexts"):
        event.pop(key, None)
    return event


def _before_send_transaction(event: Any, hint: Any) -> Any:
    """Strip host info from transactions; keep the trace context."""
    for key in ("server_name", "request"):
        event.pop(key, None)
    contexts = event.get("contexts", {})
    event["contexts"] = {k: v for k, v in contexts.items() if k == "trace"}
    return event


class _IsolatedScope(Scope):
    """Scope that sends events with its own data only.

    `Scope.capture_event` merges the global and isolation scope into every
    event, which would leak tags, extras and event processors of Home
    Assistant's own Sentry setup into our reports.
    """

    def _merge_scopes(self, additional_scope=None, additional_scope_kwargs=None):  # type: ignore[no-untyped-def]
        """Use only this scope's data, e.g. for logs, whose global attributes
        (release, server address, ...) would otherwise come from Home Assistant."""
        merged = copy(self)
        if additional_scope is not None and not callable(additional_scope):
            merged.update_from_scope(additional_scope)
        return merged

    def capture_event(self, event, hint=None, scope=None, **scope_kwargs):  # type: ignore[no-untyped-def]
        # Not get_client(): that looks at the current scopes, not at this one.
        if self.client is None or not self.client.is_active():
            return None
        return self.client.capture_event(event=event, hint=hint, scope=self)


@contextmanager
def _use_isolated(scope: Scope) -> Iterator[None]:
    """Make `scope` current and isolation scope for the wrapped (sync) code."""
    with use_isolation_scope(scope), use_scope(scope):
        yield


class _EventHandler(EventHandler):
    """Sentry's logging event handler, bound to this integration's own scope."""

    def __init__(self, scope: Scope) -> None:
        super().__init__(level=logging.WARNING)
        self._scope = scope

    def emit(self, record: logging.LogRecord) -> None:
        with _use_isolated(self._scope):
            super().emit(record)


class _LogsHandler(SentryLogsHandler):
    """Sentry's structured logs handler, bound to this integration's own scope."""

    def __init__(self, scope: Scope) -> None:
        super().__init__(level=logging.INFO)
        self._scope = scope
        self.user_id: str | None = None

    def _extra_from_record(self, record: logging.LogRecord):  # type: ignore[no-untyped-def]
        extra = super()._extra_from_record(record)
        if self.user_id:
            extra["user.id"] = self.user_id
        return extra

    def emit(self, record: logging.LogRecord) -> None:
        with _use_isolated(self._scope):
            super().emit(record)


def _before_send_log(log: Any, hint: Any) -> Any:
    """Mask personal data and strip host and local path info from structured logs."""
    attributes = log["attributes"]
    log["body"] = mask_text(log["body"])
    for key, value in attributes.items():
        if key.startswith("sentry.message.") and isinstance(value, str):
            attributes[key] = mask_text(value)
    for key in (
        "server.address",
        "process.pid",
        "process.executable.name",
        "thread.id",
        "thread.name",
    ):
        attributes.pop(key, None)
    path = str(attributes.pop("code.file.path", ""))
    if (index := path.find("custom_components")) >= 0:
        attributes["code.file.path"] = path[index:]
    return log


class ErrorReporter:
    """Own Sentry client and scope; never touches the global Sentry state."""

    def __init__(self, client: sentry_sdk.Client) -> None:
        self._client = client
        self._scope = _IsolatedScope(client=client)
        if set_attribute := getattr(self._scope, "set_attribute", None):
            # Newer SDKs put these on logs from the global scope, which we don't use.
            set_attribute("sentry.release", client.options["release"])
            set_attribute("sentry.environment", client.options["environment"] or "production")
        self._handler = _EventHandler(self._scope)
        self._logs_handler = _LogsHandler(self._scope)
        # Set while a coordinator refresh is traced; HTTP spans attach to it.
        # Requests run in executor threads, which do not inherit contextvars.
        self._transaction: Any = None
        self._api_issues_sent: dict[tuple, float] = {}
        logging.getLogger(_PACKAGE_LOGGER).addHandler(self._handler)
        logging.getLogger(_PACKAGE_LOGGER).addHandler(self._logs_handler)

    @classmethod
    async def async_create(cls, hass: HomeAssistant) -> ErrorReporter:
        """Create a reporter; client construction does blocking work."""
        integration = await async_get_integration(hass, DOMAIN)

        def _create_client() -> sentry_sdk.Client:
            return sentry_sdk.Client(
                dsn=DSN,
                release=str(integration.version),
                default_integrations=False,
                auto_enabling_integrations=False,
                send_default_pii=False,
                include_local_variables=False,
                traces_sample_rate=_traces_sample_rate(str(integration.version)),
                max_breadcrumbs=0,
                enable_backpressure_handling=False,  # avoids a lingering monitor thread
                before_send=_before_send,
                before_send_transaction=_before_send_transaction,
                enable_logs=True,
                before_send_log=_before_send_log,
            )

        return cls(await hass.async_add_executor_job(_create_client))

    @contextmanager
    def trace(self, name: str, op: str) -> Iterator[None]:
        """Trace a unit of work as a transaction on this reporter's own scope."""
        # Sampling and sending look up the active client, so make ours current
        # for those synchronous steps only.
        with use_scope(self._scope):
            transaction = self._scope.start_transaction(name=name, op=op)
        self._transaction = transaction
        try:
            yield
        except BaseException:
            transaction.set_status("internal_error")
            raise
        finally:
            self._transaction = None
            with use_scope(self._scope):
                transaction.finish(scope=self._scope)

    def http_span(self, method: str, url: str) -> AbstractContextManager[Span | None]:
        """Trace one HTTP request as a child span of the running transaction."""
        transaction = self._transaction
        if transaction is None or not transaction.sampled:
            return nullcontext()
        return self._child_span(transaction, method, url)

    @contextmanager
    def _child_span(
        self, transaction: Any, method: str, url: str
    ) -> Iterator[Span]:
        span = transaction.start_child(op="http.client", name=f"{method} {url}")
        span.set_data("http.request.method", method)
        span.set_data("url", url)
        try:
            yield span
        except BaseException:
            span.set_status("internal_error")
            raise
        finally:
            span.finish(scope=self._scope)

    def capture_api_issue(
        self,
        kind: str,
        endpoint: str,
        status: int | None,
        details: dict,
        error: BaseException | None = None,
    ) -> None:
        """Report that the API no longer behaves as expected.

        `details` must already be anonymized (see api/anonymize.py). Issues are
        grouped per kind, endpoint and status and sent at most every
        API_ISSUE_INTERVAL seconds, as polling would repeat them every minute.
        """
        if error is not None:
            fingerprint = (kind, endpoint, type(error).__name__, mask_text(str(error)))
        else:
            fingerprint = (kind, endpoint, status)
        now = time.monotonic()
        last = self._api_issues_sent.get(fingerprint)
        if last is not None and now - last < API_ISSUE_INTERVAL:
            return
        self._api_issues_sent[fingerprint] = now

        extra = {"endpoint": endpoint, "status": status, **details}
        event: Any
        hint: Any
        if error is not None:
            extra["error"] = mask_text(f"{type(error).__name__}: {error}")
            event, hint = event_from_exception(
                exc_info_from_error(error),
                client_options=self._client.options,
                mechanism={"type": "api", "handled": True},
            )
        else:
            event, hint = {"message": f"API {kind}: {endpoint} -> {status}"}, {}
        event["level"] = "error"
        event["logger"] = f"{_PACKAGE_LOGGER}.api"
        event["fingerprint"] = [str(part) for part in fingerprint]
        event["tags"] = {"api_issue": kind}
        event["extra"] = extra
        self._scope.capture_event(event, hint)

    def capture_exception(self, error: BaseException) -> None:
        """Report an exception that is not logged by this integration."""
        self._scope.capture_exception(error)

    def set_system_ids(self, system_ids: list[str]) -> None:
        """Identify reports by the Heartbeat system id(s); no name or email is sent."""
        if system_ids:
            user_id = ",".join(sorted(system_ids))
            self._scope.set_user({"id": user_id})
            self._logs_handler.user_id = user_id

    async def async_close(self, hass: HomeAssistant) -> None:
        """Detach the handler and flush pending events."""
        logging.getLogger(_PACKAGE_LOGGER).removeHandler(self._handler)
        logging.getLogger(_PACKAGE_LOGGER).removeHandler(self._logs_handler)
        await hass.async_add_executor_job(self._client.close)
