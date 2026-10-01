"""Helpers to describe API responses without leaking personal data.

Responses are reduced to their structure (keys and value types). String values
are only kept for a few keys known to hold enums or error messages, and are
masked and truncated. That is enough to see that the API changed, not what the
user's data is.
"""

import re
from typing import Any
from urllib.parse import urlsplit

# Keys whose string values are enums or server messages rather than user data.
SAFE_VALUE_KEYS = frozenset(
    {
        "chargingMode",
        "code",
        "detail",
        "error",
        "error_description",
        "errorCode",
        "kind",
        "message",
        "mode",
        "resolution",
        "state",
        "status",
        "title",
        "type",
        "unit",
    }
)

_MAX_DEPTH = 8
_MAX_KEYS = 60
_SAMPLE_ITEMS = 10
_MAX_TEXT = 300

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_ID = re.compile(r"(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{16,}")
_NUMBER = re.compile(r"\d{5,}")


def mask_text(text: str, limit: int = _MAX_TEXT) -> str:
    """Mask emails, identifiers and long numbers, and truncate."""
    text = _EMAIL.sub("<email>", text)
    text = _ID.sub("<id>", text)
    text = _NUMBER.sub("<n>", text)
    return text[:limit]


def url_template(url: str) -> str:
    """Return scheme, host and path with identifiers replaced by `{id}`."""
    parts = urlsplit(url)
    segments = [
        "{id}" if _ID.fullmatch(segment) or _NUMBER.fullmatch(segment) else segment
        for segment in parts.path.split("/")
    ]
    return f"{parts.scheme}://{parts.netloc}{'/'.join(segments)}"


def _merge(a: Any, b: Any) -> Any:
    if a == b:
        return a
    if isinstance(a, dict) and isinstance(b, dict):
        return {k: _merge(a[k], b[k]) if k in a and k in b else a.get(k, b.get(k)) for k in a | b}
    if isinstance(a, list) and isinstance(b, list):
        return [_merge(a[0], b[0])] if a and b else a or b
    options = sorted({str(x) for x in (a, b) if not isinstance(x, (dict, list))})
    return " | ".join(options) if options else "mixed"


def describe_payload(data: Any, key: str | None = None, depth: int = 0) -> Any:
    """Return the structure of a JSON value, see the module docstring."""
    if isinstance(data, dict):
        if depth >= _MAX_DEPTH:
            return "dict"
        return {
            ("<id>" if _ID.fullmatch(str(k)) else str(k)): describe_payload(v, str(k), depth + 1)
            for k, v in list(data.items())[:_MAX_KEYS]
        }
    if isinstance(data, list):
        if depth >= _MAX_DEPTH or not data:
            return []
        shapes = [describe_payload(item, key, depth + 1) for item in data[:_SAMPLE_ITEMS]]
        merged = shapes[0]
        for shape in shapes[1:]:
            merged = _merge(merged, shape)
        return [merged]
    if data is None:
        return "null"
    if isinstance(data, bool):
        return "bool"
    if isinstance(data, int):
        return "int"
    if isinstance(data, float):
        return "float"
    if isinstance(data, str):
        return mask_text(data) if key in SAFE_VALUE_KEYS else "str"
    return type(data).__name__


def describe_body(response: Any) -> Any:
    """Describe an HTTP response body: its JSON structure, or masked text."""
    try:
        return describe_payload(response.json())
    except ValueError:
        return mask_text(response.text)
