import base64
import datetime
import functools
import hashlib
import json
import logging
import secrets
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any
from urllib.parse import parse_qs, urlsplit, urlunsplit

import jwt
import requests
from jwt import PyJWKClient

from .anonymize import describe_body, describe_payload, mask_text, url_template
from .error import AuthenticationError, RequestError

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30

# Expected failures that say nothing about the API: bad credentials, rate limits.
_EXPECTED_ERROR_STATUS = frozenset({401, 403, 429})

# Called with (method, url without query) and returns a context manager that
# yields an object with `set_http_status(int)`, or None.
HttpTracer = Callable[[str, str], AbstractContextManager[Any]]

# Requests mirror the 1KOMMA5° iOS app (version 1.83.0, build 3320) so they look the same.
APP_PACKAGE = "io.onecommafive.my.production.app"
APP_VERSION = "1.83.0"
APP_BUILD = "3320"
IOS_VERSION = "27.0"
APP_USER_AGENT = f"1KOMMA5%C2%B0/{APP_BUILD} CFNetwork/3896.100.1.2.1 Darwin/27.0.0"
# The login pages are shown in the in-app browser.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/27.0 Mobile/15E148 Safari/604.1"
)
BROWSER_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "user-agent": BROWSER_USER_AGENT,
    "accept-language": "de-DE,de;q=0.9",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "priority": "u=0, i",
}
# Sent with every Heartbeat and customer-identity request, next to x-user-id.
APP_HEADERS = {
    "x-app-package-name": APP_PACKAGE,
    "x-system-version": IOS_VERSION,
    "user-agent": APP_USER_AGENT,
    "x-app-build-number": APP_BUILD,
    "x-system-name": "iOS",
    "x-model": "iPhone",
    "x-app-version": APP_VERSION,
    "x-platform": "ios",
    "accept-language": "de",
    "accept": "*/*",
    "x-manufacturer": "apple",
}


def base64_url_encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


# Auth0 SDK telemetry, sent as `auth0Client` on /authorize and `auth0-client` on API calls.
AUTH0_CLIENT = base64_url_encode(
    json.dumps(
        {
            "version": "1.14.0",
            "name": "auth0-flutter",
            "env": {"swift": "5.x", "iOS": IOS_VERSION, "core": "2.10.0"},
        },
        separators=(",", ":"),
    ).encode()
)
# Headers of the Auth0 SDK's own requests (token exchange, refresh, JWKS).
AUTH0_SDK_HEADERS = {
    "accept": "*/*",
    "content-type": "application/json",
    "auth0-client": AUTH0_CLIENT,
    "accept-language": "de-DE,de;q=0.9",
    "priority": "u=3",
    "user-agent": APP_USER_AGENT,
}


class Client:
    TOKEN_URL = "https://auth.1komma5grad.com/oauth/token"
    AUDIENCE = "https://1komma5grad.com/api"
    JWKS_URL = "https://auth.1komma5grad.com/.well-known/jwks.json"
    CLIENT_ID = "zJTm6GFGM5zHcmpl07xTsi6MP0TwRAw6"
    REDIRECT_URL = f"{APP_PACKAGE}://auth.1komma5grad.com/ios/{APP_PACKAGE}/callback"

    HEARTBEAT_API = "https://heartbeat.1komma5grad.com"

    def __init__(self, username, password):
        self.jwks_client = PyJWKClient(self.JWKS_URL, headers=AUTH0_SDK_HEADERS)
        self.state = None
        self.token_set: dict | None = None

        self.username = username
        self.password = password

        # Optional hook to trace outgoing HTTP requests, see HttpTracer.
        self.tracer: HttpTracer | None = None

        # Optional hook for API changes: (kind, endpoint, status, details). It only
        # ever receives anonymized data, see anonymize.py.
        self.on_issue: Callable[[str, str, int | None, dict], None] | None = None

        # Structure of the last response per endpoint, kept to attach to parse errors.
        self.response_shapes: dict[str, Any] = {}

    def _send(self, method: str, url: str, send: Callable[..., Any], **kwargs):
        """Send a request and inspect the response for API changes."""
        res = self._send_traced(method, url, send, **kwargs)
        if self.on_issue is not None:
            self._inspect(method, url, res)
        return res

    def _inspect(self, method: str, url: str, res) -> None:
        """Report unexpected statuses and invalid JSON, remember response shapes."""
        template = url_template(url)
        if (urlsplit(url).hostname or "").startswith("auth."):
            return  # login pages carry credentials, never look at them
        endpoint = f"{method} {template}"
        status = res.status_code
        if status >= 400:
            if status not in _EXPECTED_ERROR_STATUS:
                self.on_issue(  # type: ignore[misc]
                    "http_error", endpoint, status, {"body": describe_body(res)}
                )
            return
        if status == 204 or not res.content:
            return
        try:
            data = res.json()
        except ValueError:
            self.on_issue(  # type: ignore[misc]
                "invalid_json", endpoint, status, {"body": mask_text(res.text)}
            )
            return
        self.response_shapes[endpoint] = describe_payload(data)
        res.json = lambda **_: data  # avoid parsing the body twice

    def _send_traced(self, method: str, url: str, send: Callable[..., Any], **kwargs):
        """Send a request, wrapped in a trace span if a tracer is set."""
        if self.tracer is None:
            return send(url, **kwargs)
        # Drop query and fragment: they carry auth state and PKCE challenges.
        parts = urlsplit(url)
        with self.tracer(method, urlunsplit(parts._replace(query="", fragment=""))) as span:
            res = send(url, **kwargs)
            if span is not None:
                span.set_http_status(res.status_code)
            return res

    def get(self, url: str, **kwargs):
        return self._send("GET", url, requests.get, **self._with_app_headers(url, kwargs))

    def post(self, url: str, **kwargs):
        return self._send("POST", url, requests.post, **self._with_app_headers(url, kwargs))

    def patch(self, url: str, **kwargs):
        return self._send("PATCH", url, requests.patch, **self._with_app_headers(url, kwargs))

    def _with_app_headers(self, url: str, kwargs: dict) -> dict:
        """Add the app's headers to API requests; the caller's headers win."""
        host = urlsplit(url).hostname or ""
        if not host.endswith(".1komma5grad.com") or host.startswith("auth."):
            return kwargs
        headers = dict(APP_HEADERS)
        if user_id := self._user_id():
            headers["x-user-id"] = user_id
        return {**kwargs, "headers": {**headers, **(kwargs.get("headers") or {})}}

    def _user_id(self) -> str | None:
        """Auth0 user id (`sub`) of the current token, which the app sends as x-user-id."""
        if self.token_set is None:
            return None
        try:
            return jwt.decode(
                self.token_set["access_token"],
                options={"verify_signature": False, "verify_exp": False},
                algorithms=["RS256"],
            ).get("sub")
        except (jwt.PyJWTError, KeyError, TypeError):
            return None

    def get_token_parsed(self) -> jwt.PyJWT:
        if self.token_set is None:
            raise AuthenticationError("No token set")

        signing_key = self.jwks_client.get_signing_key_from_jwt(
            self.token_set["access_token"]
        )

        return jwt.decode(
            jwt=self.token_set["access_token"],
            key=signing_key,
            options={"verify_exp": True},
            audience=self.AUDIENCE,
            algorithms=["RS256"],
        )

    # Returns True if the token is expiring in less than 'before' seconds
    def is_token_expiring(self, before: int) -> bool:
        if self.token_set is None:
            return True

        try:
            # Decode locally without signature verification to avoid JWKS network calls
            token = jwt.decode(
                self.token_set["access_token"],
                options={"verify_signature": False, "verify_exp": False},
                algorithms=["RS256"],
            )

            now = datetime.datetime.now(datetime.timezone.utc)
            return token["exp"] - before < now.timestamp()
        except (jwt.PyJWTError, KeyError, TypeError):
            return True

    def get_token(self) -> str:
        if self.token_set is None:
            return self._login_with_retry()

        # Check for expiration and refresh token
        if self.is_token_expiring(60):
            try:
                return self.refresh_token()
            except AuthenticationError:
                return self._login_with_retry()

        return self.token_set["access_token"]

    def _login_with_retry(self) -> str:
        last_error = None
        for attempt in range(3):
            try:
                return self.login()
            except AuthenticationError as err:
                last_error = err
                delay = 2 ** (attempt + 1)  # 2s, 4s, 8s
                _LOGGER.warning(
                    "Login attempt %d failed: %s. Retrying in %ds...",
                    attempt + 1,
                    err,
                    delay,
                )
                time.sleep(delay)
        raise last_error or AuthenticationError("Login failed after retries")

    def login(self) -> str:
        try:
            session = _TracedSession(self)
            session.headers.update(BROWSER_HEADERS)

            verifier = generate_code_verifier()
            challenge = generate_code_challenge(verifier)

            # Authorize request, parameters in the order the app sends them
            login_res = session.get(
                "https://auth.1komma5grad.com/authorize",
                params={
                    "state": secrets.token_urlsafe(32),
                    "response_type": "code",
                    "redirect_uri": self.REDIRECT_URL,
                    "client_id": self.CLIENT_ID,
                    "code_challenge_method": "S256",
                    "login_hint": self.username,
                    "audience": self.AUDIENCE,
                    "code_challenge": challenge,
                    "ui_locales": "de",
                    "scope": "openid profile email offline_access",
                    "auth0Client": AUTH0_CLIENT,
                },
                timeout=REQUEST_TIMEOUT,
            )

            # Expecting status code 200 for successful request
            if login_res.status_code != 200:
                raise AuthenticationError(
                    "Authorization request returned wrong status code: "
                    + str(login_res.status_code)
                )

            # Get state from HTML response, it's inside a hidden input field
            self.state = (
                login_res.text.split('name="state" value="')[1].split('"')[0].strip()
            )

            # Make POST request to login
            login_post_res = session.post(
                login_res.url,
                data={
                    "state": self.state,
                    "username": self.username,
                    "password": self.password,
                },
                headers={
                    "origin": "https://auth.1komma5grad.com",
                    "referer": login_res.url,
                    "sec-fetch-site": "same-origin",
                },
                allow_redirects=False,
                timeout=REQUEST_TIMEOUT,
            )

            if login_post_res.status_code != 302:
                raise AuthenticationError("Failed to login: " + login_post_res.text)

            resume_url = "https://auth.1komma5grad.com" + login_post_res.headers["location"]
            resume_res = session.get(
                resume_url,
                headers={"referer": login_res.url, "sec-fetch-site": "same-origin"},
                allow_redirects=False,
                timeout=REQUEST_TIMEOUT,
            )

            if resume_res.status_code != 302:
                raise AuthenticationError("Failed to resume login: " + resume_res.text)

            # Extract code from the callback URL, which also carries the state
            code = parse_qs(urlsplit(resume_res.headers["location"]).query)["code"][0]

            # Make POST request to get token
            res = self.post(
                url=self.TOKEN_URL,
                json={
                    "client_id": self.CLIENT_ID,
                    "code": code,
                    "code_verifier": verifier,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.REDIRECT_URL,
                },
                headers=AUTH0_SDK_HEADERS,
                timeout=REQUEST_TIMEOUT,
            )

            if res.status_code != 200:
                raise AuthenticationError("Failed to get token: " + res.text)

            token_set = res.json()
            self.token_set = token_set

            return token_set["access_token"]
        except AuthenticationError:
            raise
        except requests.exceptions.RequestException as err:
            raise AuthenticationError(f"Login failed due to network error: {err}") from err

    def refresh_token(self) -> str:
        if self.token_set is None:
            raise AuthenticationError("No token set")

        if "refresh_token" not in self.token_set:
            raise AuthenticationError("No refresh token found")

        try:
            res = self.post(
                url=self.TOKEN_URL,
                json={
                    "client_id": self.CLIENT_ID,
                    "refresh_token": self.token_set["refresh_token"],
                    "grant_type": "refresh_token",
                },
                headers=AUTH0_SDK_HEADERS,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as err:
            raise AuthenticationError(f"Token refresh failed due to network error: {err}") from err

        if res.status_code != 200:
            raise AuthenticationError("Failed to refresh token: " + res.text)

        # Merge new tokens, preserving refresh_token if not included in response
        self.token_set.update(res.json())

        return self.token_set["access_token"]

    def get_user(self):
        try:
            res = self.get(
                url="https://customer-identity.1komma5grad.com/api/v1/users/me",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + self.get_token(),
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as err:
            raise RequestError(f"Failed to get user due to network error: {err}") from err

        if res.status_code != 200:
            raise RequestError("Failed to get user: " + res.text)

        return res.json()

    def close(self):
        try:
            res = self.get(
                url="https://auth.1komma5grad.com/v2/logout",
                params={"client_id": self.CLIENT_ID},
                allow_redirects=False,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as err:
            raise RequestError(f"Failed to logout due to network error: {err}") from err

        if res.status_code >= 400:
            raise RequestError("Failed to logout: " + res.text)

        self.token_set = None


class _TracedSession(requests.Session):
    """Session whose requests go through the client's tracer."""

    def __init__(self, client: Client) -> None:
        super().__init__()
        self._client = client

    def request(self, method, url, **kwargs):  # type: ignore[override]
        send = functools.partial(super().request, method)
        return self._client._send(str(method).upper(), url, send, **kwargs)


def generate_code_verifier():
    verifier = secrets.token_urlsafe(32)
    return verifier


def generate_code_challenge(verifier):
    sha256_hash = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64_url_encode(sha256_hash)
    return challenge
