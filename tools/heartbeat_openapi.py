"""Upsert Heartbeat API operations from a mitmproxy flow dump into an OpenAPI spec.

Usage: python tools/heartbeat_openapi.py FLOWS [--spec docs/heartbeat-openapi.json]

Only requests to heartbeat.1komma5grad.com are used. Operations in the dump are added
or updated; operations missing from it are kept, so retired API versions stay
documented, and `x-last-seen` tells when each one was last observed.

No captured values are written: schemas carry types, formats and UPPER_CASE enum
values only, and the run aborts without writing if any captured string would leak.
Brotli-compressed bodies need `pip install brotli`; without it they are skipped.
"""

from __future__ import annotations

import argparse
import datetime
import gzip
import json
import re
import sys
import zlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit

try:
    import brotli  # pyright: ignore[reportMissingImports]
except ImportError:
    brotli = None

HOST = "heartbeat.1komma5grad.com"
DEFAULT_SPEC = Path(__file__).resolve().parent.parent / "docs" / "heartbeat-openapi.json"

UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?$")
TIME = re.compile(r"^\d{2}:\d{2}(:\d{2})?$")
ENUM = re.compile(r"^[A-Z]+(_[A-Z0-9]+)*$")
# Path segments kept literally: API versions and lowercase words. Anything else in a
# path (UUIDs, numbers, slugs, codes) is treated as an identifier and becomes a parameter.
PATH_WORD = re.compile(r"^(v\d+|[a-z]+(-[a-z]+)*)$")
# Never turn values of these keys into enums, even when they look like one.
SENSITIVE_KEY = re.compile(
    r"name|mail|phone|address|city|zip|street|serial|code|token|^id$|Id$|iban|label|title"
    r"|description|url|text|message|hint",
    re.IGNORECASE,
)
# Path parameter name by the segment in front of the id.
ID_NAMES = {
    "systems": "systemId",
    "sites": "siteId",
    "users": "userId",
    "evs": "evId",
    "installers": "installerId",
    "modules": "moduleId",
}
# Enum values known beyond what a single dump shows.
KNOWN_ENUMS = {"chargingMode": ["QUICK_CHARGE", "SMART_CHARGE", "SOLAR_CHARGE"]}
REASONS = {200: "OK", 201: "Created", 204: "No Content", 304: "Not Modified (ETag matched)"}


# ---- mitmproxy flow file (tnetstring) -----------------------------------------


def _parse(data: bytes, i: int = 0) -> tuple[Any, int]:
    colon = data.index(b":", i)
    start = colon + 1
    end = start + int(data[i:colon])
    payload, kind, nxt = data[start:end], data[end : end + 1], end + 1
    if kind == b",":
        return payload, nxt
    if kind == b";":
        return payload.decode(), nxt
    if kind == b"#":
        return int(payload), nxt
    if kind == b"^":
        return float(payload), nxt
    if kind == b"!":
        return payload == b"true", nxt
    if kind == b"~":
        return None, nxt
    if kind == b"]":
        items, k = [], 0
        while k < len(payload):
            value, k = _parse(payload, k)
            items.append(value)
        return items, nxt
    if kind == b"}":
        obj, k = {}, 0
        while k < len(payload):
            key, k = _parse(payload, k)
            value, k = _parse(payload, k)
            obj[key.decode() if isinstance(key, bytes) else key] = value
        return obj, nxt
    raise ValueError(f"Unknown tnetstring type {kind!r}")


def read_flows(path: Path) -> Iterator[dict]:
    data = path.read_bytes()
    i = 0
    while i < len(data):
        flow, i = _parse(data, i)
        yield flow


def _text(value: Any) -> str:
    return value.decode(errors="replace") if isinstance(value, bytes) else (value or "")


def _header(message: dict | None, name: str) -> str:
    for key, value in (message or {}).get("headers") or []:
        if _text(key).lower() == name:
            return _text(value)
    return ""


class Bodies:
    """Decodes JSON bodies, counting the ones that need brotli."""

    def __init__(self) -> None:
        self.skipped_brotli = 0

    def json(self, message: dict | None) -> Any:
        content = (message or {}).get("content")
        if not content:
            return None
        encoding = _header(message, "content-encoding").lower()
        if encoding == "gzip":
            content = gzip.decompress(content)
        elif encoding == "deflate":
            content = zlib.decompress(content)
        elif encoding == "br":
            if brotli is None:
                self.skipped_brotli += 1
                return None
            content = brotli.decompress(content)
        try:
            return json.loads(content)
        except ValueError:
            return None


# ---- paths and schemas ------------------------------------------------------------


def template(path: str) -> tuple[str, list[str]]:
    """Replace everything that is not an API word with a named parameter."""
    segments = path.split("/")
    out: list[str] = []
    names: list[str] = []
    for i, seg in enumerate(segments):
        prev = segments[i - 1] if i else ""
        # Right after a collection only hyphenated sub-resources are literal
        # (e.g. evs/displayed-ev-charging-modes); a plain word there is an id.
        after_collection = prev in ID_NAMES and i >= 3 and "-" not in seg
        if seg and (not PATH_WORD.match(seg) or after_collection or prev == "modules"):
            name = ID_NAMES.get(prev, "id")
            while name in names:
                name += "2"
            names.append(name)
            out.append("{" + name + "}")
        else:
            out.append(seg)
    return "/".join(out), names


def infer(value: Any, key: str = "") -> dict:
    """Schema of one observed value; `x-req` tracks keys present in every sample."""
    if value is None:
        return {"nullable": True}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, str):
        if UUID.match(value):
            return {"type": "string", "format": "uuid"}
        if DATETIME.match(value):
            return {"type": "string", "format": "date-time"}
        if DATE.match(value):
            return {"type": "string", "format": "date"}
        if TIME.match(value):
            return {"type": "string", "pattern": "^\\d{2}:\\d{2}(:\\d{2})?$"}
        if ENUM.match(value) and not SENSITIVE_KEY.search(key):
            return {"type": "string", "enum": [value]}
        return {"type": "string"}
    if isinstance(value, list):
        items = None
        for item in value:
            items = merge(items, infer(item, key))
        return {"type": "array", "items": items or {}}
    if isinstance(value, dict):
        keys = list(value)
        if keys and all(UUID.match(k) or DATE.match(k) or DATETIME.match(k) for k in keys):
            # A map keyed by ids or dates: the keys are data, not names.
            values = None
            for item in value.values():
                values = merge(values, infer(item))
            return {"type": "object", "additionalProperties": values or {}}
        return {
            "type": "object",
            "properties": {k: infer(v, k) for k, v in value.items()},
            "x-req": set(keys),
        }
    return {}


def merge(a: dict | None, b: dict | None) -> dict | None:
    """Combine the schemas of two samples of the same value."""
    if a is None or b is None:
        return a if b is None else b
    if "type" not in a and "oneOf" not in a and a.get("nullable"):
        return {**b, "nullable": True}
    if "type" not in b and "oneOf" not in b and b.get("nullable"):
        return {**a, "nullable": True}
    nullable = a.get("nullable") or b.get("nullable")
    ta, tb = a.get("type"), b.get("type")
    if ta != tb:
        out = (
            {"type": "number"}
            if {ta, tb} == {"integer", "number"}
            else {"oneOf": (a.get("oneOf") or [a]) + (b.get("oneOf") or [b])}
        )
    elif ta == "object" and "properties" in a and "properties" in b:
        props = dict(a["properties"])
        for k, v in b["properties"].items():
            props[k] = merge(props.get(k), v)
        out = {"type": "object", "properties": props, "x-req": a["x-req"] & b["x-req"]}
    elif ta == "object":
        out = {
            "type": "object",
            "additionalProperties": merge(
                a.get("additionalProperties"), b.get("additionalProperties")
            )
            or {},
        }
    elif ta == "array":
        out = {"type": "array", "items": merge(a.get("items") or None, b.get("items") or None) or {}}
    elif ta == "string":
        out = {"type": "string"}
        for attr in ("format", "pattern"):
            if a.get(attr) and a.get(attr) == b.get(attr):
                out[attr] = a[attr]
        if "enum" in a and "enum" in b and "format" not in out:
            out["enum"] = sorted(set(a["enum"]) | set(b["enum"]))
    else:
        out = {"type": ta}
    if nullable:
        out["nullable"] = True
    return out


def finalize(schema: Any) -> Any:
    """Turn `x-req` into `required` and recurse."""
    if not isinstance(schema, dict):
        return schema
    schema = dict(schema)
    if "properties" in schema:
        present = schema.pop("x-req", set())
        schema["properties"] = {k: finalize(v) for k, v in schema["properties"].items()}
        required = sorted(k for k in present if not schema["properties"][k].get("nullable"))
        if required:
            schema["required"] = required
    for attr in ("items", "additionalProperties"):
        if isinstance(schema.get(attr), dict):
            schema[attr] = finalize(schema[attr])
    if "oneOf" in schema:
        schema["oneOf"] = [finalize(s) for s in schema["oneOf"]]
    return schema


def query_schema(values: list[str]) -> dict:
    present = [v for v in values if v]
    if present and all(UUID.match(v) for v in present):
        return {"type": "string", "format": "uuid"}
    if present and all(DATE.match(v) for v in present):
        return {"type": "string", "format": "date"}
    if present and all(DATETIME.match(v) for v in present):
        return {"type": "string", "format": "date-time"}
    if present and all(re.fullmatch(r"-?\d+", v) for v in present):
        return {"type": "integer"}
    if present and all(v in ("true", "false") for v in present):
        return {"type": "boolean"}
    return {"type": "string"}


# ---- observation ---------------------------------------------------------------


class Observation:
    """Everything seen for one path and method."""

    def __init__(self, path_params: list[str]) -> None:
        self.path_params = path_params
        self.query: dict[str, list[str]] = {}
        self.repeated_query: set[str] = set()
        self.request: dict | None = None
        self.responses: dict[int, dict | None] = {}
        self.last_seen = 0.0


def observe(flows_path: Path) -> tuple[dict[tuple[str, str], Observation], set[str], dict]:
    """Collect observations, every captured string (for the leak check) and dump info."""
    bodies = Bodies()
    observations: dict[tuple[str, str], Observation] = {}
    captured: set[str] = set()
    app_version = ""

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for v in value.values():
                collect(v)
        elif isinstance(value, list):
            for v in value:
                collect(v)
        elif isinstance(value, str):
            captured.add(value)

    for flow in read_flows(flows_path):
        request = flow.get("request") or {}
        if _text(request.get("host")) != HOST:
            continue
        url = urlsplit(_text(request.get("path")))
        path, path_params = template(url.path)
        method = _text(request.get("method")).lower()
        obs = observations.setdefault((path, method), Observation(path_params))
        obs.last_seen = max(obs.last_seen, request.get("timestamp_start") or 0.0)
        app_version = _header(request, "x-app-version") or app_version
        captured.update(unquote(seg) for seg in url.path.split("/"))

        seen_here: set[str] = set()
        for key, value in parse_qsl(url.query, keep_blank_values=True):
            obs.query.setdefault(key, []).append(value)
            captured.add(value)
            if key in seen_here:
                obs.repeated_query.add(key)
            seen_here.add(key)

        request_body = bodies.json(request)
        if request_body is not None:
            collect(request_body)
            obs.request = merge(obs.request, infer(request_body))

        response = flow.get("response") or {}
        status = response.get("status_code")
        if status:
            response_body = bodies.json(response)
            if response_body is not None:
                collect(response_body)
                obs.responses[status] = merge(obs.responses.get(status), infer(response_body))
            else:
                obs.responses.setdefault(status, None)

    info = {"app_version": app_version, "skipped_brotli": bodies.skipped_brotli}
    return observations, captured, info


def operation_id(method: str, path: str) -> str:
    path = re.sub(r"\{(\w)(\w*)\}", lambda m: "By-" + m.group(1).upper() + m.group(2), path)
    words = re.split(r"[^A-Za-z0-9]+", path.replace("/api/", "/"))
    return method + "".join(w[0].upper() + w[1:] for w in words if w)


def build_operation(path: str, method: str, obs: Observation) -> dict:
    segments = [s for s in path.split("/") if s and not s.startswith("{")]
    params: list[dict] = [
        {
            "name": name,
            "in": "path",
            "required": True,
            "schema": {"type": "string"} if name == "moduleId" else {"type": "string", "format": "uuid"},
        }
        for name in obs.path_params
    ]
    for name, values in sorted(obs.query.items()):
        schema = query_schema(values)
        param = {"name": name, "in": "query", "required": False, "schema": schema}
        if name in obs.repeated_query:
            param["schema"] = {"type": "array", "items": schema}
            param["explode"] = True
        params.append(param)

    operation: dict = {
        "tags": [segments[2] if len(segments) > 2 else "misc"],
        "operationId": operation_id(method, path),
        "summary": f"{method.upper()} {path}",
    }
    if params:
        operation["parameters"] = params
    if obs.request is not None:
        operation["requestBody"] = {
            "required": True,
            "content": {"application/json": {"schema": finalize(obs.request)}},
        }
    responses: dict = {}
    for status, schema in sorted(obs.responses.items()):
        entry: dict = {"description": REASONS.get(status, str(status))}
        if schema is not None:
            entry["content"] = {"application/json": {"schema": finalize(schema)}}
        responses[str(status)] = entry
    operation["responses"] = responses or {"default": {"description": "Not observed"}}
    operation["x-last-seen"] = (
        datetime.datetime.fromtimestamp(obs.last_seen, datetime.UTC).date().isoformat()
    )
    return operation


# ---- upsert --------------------------------------------------------------------


def _schema(container: dict | None) -> dict | None:
    return ((container or {}).get("content") or {}).get("application/json", {}).get("schema")


def carry_enums(old: Any, new: Any) -> None:
    """Keep enum values of the old schema that this dump did not show."""
    if not isinstance(old, dict) or not isinstance(new, dict):
        return
    if "enum" in old and "enum" in new:
        new["enum"] = sorted(set(old["enum"]) | set(new["enum"]))
    for key, value in (new.get("properties") or {}).items():
        carry_enums((old.get("properties") or {}).get(key), value)
    for attr in ("items", "additionalProperties"):
        carry_enums(old.get(attr), new.get(attr))


def apply_known_enums(schema: Any) -> None:
    if isinstance(schema, dict):
        for key, value in (schema.get("properties") or {}).items():
            if key in KNOWN_ENUMS and isinstance(value, dict) and "enum" in value:
                value["enum"] = sorted(set(value["enum"]) | set(KNOWN_ENUMS[key]))
        for value in schema.values():
            apply_known_enums(value)
    elif isinstance(schema, list):
        for value in schema:
            apply_known_enums(value)


def upsert_operation(old: dict | None, new: dict) -> dict:
    """Update an operation with what the dump showed, keeping what it did not."""
    if old is None:
        return new
    merged = {**old, **{k: new[k] for k in ("tags", "operationId", "summary", "x-last-seen")}}

    params = {(p["in"], p["name"]): p for p in old.get("parameters") or []}
    params.update({(p["in"], p["name"]): p for p in new.get("parameters") or []})
    if params:
        merged["parameters"] = list(params.values())

    if "requestBody" in new:
        carry_enums(_schema(old.get("requestBody")), _schema(new["requestBody"]))
        merged["requestBody"] = new["requestBody"]

    responses = {k: v for k, v in (old.get("responses") or {}).items() if k != "default"}
    for status, entry in new["responses"].items():
        if status == "default":
            continue
        if "content" in entry:
            carry_enums(_schema(responses.get(status)), _schema(entry))
            responses[status] = entry
        else:
            responses.setdefault(status, entry)  # a 304 or skipped body keeps the old schema
    merged["responses"] = dict(sorted(responses.items())) or new["responses"]
    return merged


def empty_spec() -> dict:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "1KOMMA5° Heartbeat API (unofficial)",
            "version": "",
            "description": (
                "Reverse-engineered from 1KOMMA5° iOS app traffic with tools/heartbeat_openapi.py. "
                "Schemas are inferred from observed requests and contain no captured values. "
                "Enums list observed values, so others may exist. Operations not seen in the "
                "latest dump are kept; see x-last-seen."
            ),
        },
        "servers": [{"url": f"https://{HOST}"}],
        "security": [{"auth0": ["openid", "profile", "email", "offline_access"]}],
        "components": {
            "securitySchemes": {
                "auth0": {
                    "type": "oauth2",
                    "description": (
                        "Auth0 authorization code flow with PKCE, audience "
                        "https://1komma5grad.com/api. Send the access token as Bearer token."
                    ),
                    "flows": {
                        "authorizationCode": {
                            "authorizationUrl": "https://auth.1komma5grad.com/authorize",
                            "tokenUrl": "https://auth.1komma5grad.com/oauth/token",
                            "refreshUrl": "https://auth.1komma5grad.com/oauth/token",
                            "scopes": {
                                "openid": "OpenID",
                                "profile": "Profile",
                                "email": "Email",
                                "offline_access": "Refresh token",
                            },
                        }
                    },
                }
            }
        },
        "paths": {},
    }


def find_leaks(operations: list[dict], captured: set[str]) -> list[str]:
    """Captured strings that would end up in the spec as values."""
    names: set[str] = set()
    values: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            names.update((node.get("properties") or {}).keys())
            if "name" in node and "in" in node:
                names.add(node["name"])
            for key, value in node.items():
                if key != "x-last-seen":  # derived from flow timestamps
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str):
            values.add(node)

    walk(operations)
    # Literal path segments are API words by construction (see template); tags and
    # summaries repeat them.
    for operation in operations:
        names.update(seg for seg in operation["summary"].split(" ", 1)[1].split("/")
                     if PATH_WORD.match(seg))
    return sorted(
        v
        for v in values & captured
        if len(v) >= 3 and v not in ("true", "false") and not ENUM.match(v) and v not in names
    )


def upsert(flows_path: Path, spec_path: Path) -> dict:
    observations, captured, info = observe(flows_path)
    spec = json.loads(spec_path.read_text()) if spec_path.exists() else empty_spec()
    paths: dict = spec.setdefault("paths", {})

    built = []
    added = updated = 0
    for (path, method), obs in observations.items():
        new = build_operation(path, method, obs)
        apply_known_enums(new)
        old = paths.get(path, {}).get(method)
        added += old is None
        updated += old is not None
        built.append(new)
        paths.setdefault(path, {})[method] = upsert_operation(old, new)

    leaks = find_leaks(built, captured)
    if leaks:
        raise SystemExit(
            f"Aborted, nothing written: {len(leaks)} captured value(s) would leak into the spec."
        )

    spec["paths"] = {p: dict(sorted(ops.items())) for p, ops in sorted(paths.items())}
    last_seen = max(
        (op.get("x-last-seen", "") for ops in spec["paths"].values() for op in ops.values()),
        default="",
    )
    spec["info"]["version"] = f"observed-{last_seen}"
    if info["app_version"]:
        spec["info"]["x-app-version"] = info["app_version"]

    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")

    total = sum(len(ops) for ops in spec["paths"].values())
    return {
        "added": added,
        "updated": updated,
        "kept": total - added - updated,
        "skipped_brotli": info["skipped_brotli"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("flows", type=Path, help="mitmproxy flow file")
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC, help="OpenAPI JSON to upsert into")
    args = parser.parse_args()

    result = upsert(args.flows, args.spec)
    print(
        f"{args.spec}: {result['added']} added, {result['updated']} updated, "
        f"{result['kept']} kept from earlier dumps"
    )
    if result["skipped_brotli"]:
        print(
            f"warning: {result['skipped_brotli']} brotli bodies skipped (pip install brotli); "
            "their existing schemas were kept",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
