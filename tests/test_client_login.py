"""Login and request headers mirror the 1KOMMA5° iOS app."""

from unittest.mock import MagicMock, patch

import jwt

from custom_components.einskomma5grad.api.client import (
    AUTH0_CLIENT,
    AUTH0_SDK_HEADERS,
    BROWSER_USER_AGENT,
    Client,
)

LOGIN_URL = "https://auth.1komma5grad.com/u/login?state=login-state&ui_locales=de"


def _token(sub: str = "auth0|test") -> str:
    return jwt.encode({"sub": sub}, "secret", algorithm="HS256")


def _response(status: int, text: str = "", location: str | None = None, url: str = ""):
    res = MagicMock(status_code=status, text=text, content=text.encode(), url=url)
    res.headers = {"location": location} if location else {}
    return res


def test_auth0_client_matches_the_app() -> None:
    """auth0-flutter 1.14.0 on iOS 27.0, exactly as captured from the app."""
    assert AUTH0_CLIENT == (
        "eyJ2ZXJzaW9uIjoiMS4xNC4wIiwibmFtZSI6ImF1dGgwLWZsdXR0ZXIiLCJlbnYiOnsic3dpZnQiOiI1Ln"
        "giLCJpT1MiOiIyNy4wIiwiY29yZSI6IjIuMTAuMCJ9fQ"
    )


def test_api_requests_carry_app_headers() -> None:
    client = Client("user", "pw")
    client.token_set = {"access_token": _token()}

    with patch("requests.get", return_value=_response(200)) as get:
        client.get(
            "https://heartbeat.1komma5grad.com/api/v2/systems",
            headers={"Authorization": "Bearer t", "accept-language": "en"},
        )
    headers = get.call_args.kwargs["headers"]
    assert headers["x-app-version"] == "1.83.0"
    assert headers["x-app-build-number"] == "3320"
    assert headers["x-platform"] == "ios"
    assert headers["user-agent"].startswith("1KOMMA5%C2%B0/3320 ")
    assert headers["x-user-id"] == "auth0|test"
    assert headers["Authorization"] == "Bearer t"
    assert headers["accept-language"] == "en"  # the caller's headers win


def test_auth_and_foreign_hosts_get_no_app_headers() -> None:
    client = Client("user", "pw")
    with patch("requests.get", return_value=_response(200)) as get:
        client.get("https://auth.1komma5grad.com/v2/logout")
        client.get("https://example.com/x")
    assert all("headers" not in call.kwargs for call in get.call_args_list)


def test_login_looks_like_the_app() -> None:
    """Browser steps use Safari headers, the token exchange the Auth0 SDK's."""
    client = Client("me@example.com", "pw")
    session_calls: list = []

    def session_request(self, method, url, **kwargs):
        session_calls.append((method, url, {**self.headers, **(kwargs.get("headers") or {})}, kwargs))
        if url.endswith("/authorize"):
            return _response(200, '<input name="state" value="login-state">', url=LOGIN_URL)
        if method == "POST":
            return _response(302, location="/authorize/resume?state=resume")
        return _response(
            302,
            location=f"{client.REDIRECT_URL}?code=the-code&state={session_calls[0][3]['params']['state']}",
        )

    token = _response(200)
    token.json = lambda: {"access_token": _token(), "refresh_token": "r"}
    with (
        patch("requests.Session.request", session_request),
        patch("requests.post", return_value=token) as post,
    ):
        client.login()

    (_, _, authorize_headers, authorize), (_, _, post_headers, login), (_, _, resume_headers, _) = (
        session_calls
    )
    params = authorize["params"]
    assert list(params) == [
        "state", "response_type", "redirect_uri", "client_id", "code_challenge_method",
        "login_hint", "audience", "code_challenge", "ui_locales", "scope", "auth0Client",
    ]
    assert len(params["state"]) == 43
    assert params["login_hint"] == "me@example.com"
    assert params["auth0Client"] == AUTH0_CLIENT
    assert authorize_headers["user-agent"] == BROWSER_USER_AGENT

    assert login["data"] == {"state": "login-state", "username": "me@example.com", "password": "pw"}
    assert post_headers["referer"] == LOGIN_URL
    assert post_headers["sec-fetch-site"] == "same-origin"
    assert resume_headers["referer"] == LOGIN_URL

    # The callback carries the state after the code; only the code is exchanged.
    assert post.call_args.kwargs["json"]["code"] == "the-code"
    assert post.call_args.kwargs["headers"] == AUTH0_SDK_HEADERS
    assert client.token_set == {"access_token": token.json()["access_token"], "refresh_token": "r"}
