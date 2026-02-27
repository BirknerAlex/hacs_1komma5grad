import base64
import datetime
import hashlib
import logging
import secrets
import time

import jwt
from jwt import PyJWKClient
import requests

from .error import AuthenticationError, RequestError

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30


class Client:
    TOKEN_URL = "https://auth.1komma5grad.com/oauth/token"
    AUDIENCE = "https://1komma5grad.com/api"
    JWKS_URL = "https://auth.1komma5grad.com/.well-known/jwks.json"
    CLIENT_ID = "zJTm6GFGM5zHcmpl07xTsi6MP0TwRAw6"
    OAUTH0_CLIENT_ID = "eyJuYW1lIjoiYXV0aDAtZmx1dHRlciIsInZlcnNpb24iOiIxLjcuMiIsImVudiI6eyJzd2lmdCI6IjUueCIsImlPUyI6IjE4LjAiLCJjb3JlIjoiMi43LjIifX0"
    REDIRECT_URL = "io.onecommafive.my.production.app://auth.1komma5grad.com/ios/io.onecommafive.my.production.app/callback"

    HEARTBEAT_API = "https://heartbeat.1komma5grad.com"

    def __init__(self, username, password):
        self.jwks_client = PyJWKClient(self.JWKS_URL)
        self.state = None
        self.token_set = None

        self.username = username
        self.password = password

    def get_token_parsed(self) -> jwt.PyJWT:
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

            return token["exp"] - before < datetime.datetime.now().timestamp()
        except Exception:
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
        raise last_error

    def login(self) -> str:
        try:
            session = requests.Session()

            verifier = generate_code_verifier()
            challenge = generate_code_challenge(verifier)

            self.state = ""

            # Authorize request
            login_res = session.get(
                "https://auth.1komma5grad.com/authorize",
                params={
                    "scope": "openid profile email offline_access",
                    "client_id": self.CLIENT_ID,
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                    "response_type": "code",
                    "audience": self.AUDIENCE,
                    "redirect_uri": self.REDIRECT_URL,
                    "state": self.state,
                    "auth0Client": self.OAUTH0_CLIENT_ID,
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
                    "action": "default",
                },
                allow_redirects=False,
                timeout=REQUEST_TIMEOUT,
            )

            if login_post_res.status_code != 302:
                raise AuthenticationError("Failed to login: " + login_post_res.text)

            resume_url = "https://auth.1komma5grad.com" + login_post_res.headers["location"]
            resume_res = session.get(resume_url, allow_redirects=False, timeout=REQUEST_TIMEOUT)

            if resume_res.status_code != 302:
                raise AuthenticationError("Failed to resume login: " + resume_res.text)

            # Extract code from location header
            code = resume_res.headers["location"].split("code=")[1]

            # Make POST request to get token
            res = requests.post(
                url=self.TOKEN_URL,
                json={
                    "client_id": self.CLIENT_ID,
                    "code": code,
                    "code_verifier": verifier,
                    "grant_type": "authorization_code",
                    "redirect_uri": "io.onecommafive.my.production.app://auth.1komma5grad.com/ios/io.onecommafive.my.production.app/callback",
                },
                timeout=REQUEST_TIMEOUT,
            )

            if res.status_code != 200:
                raise AuthenticationError("Failed to get token: " + res.text)

            self.token_set = res.json()

            return self.token_set["access_token"]
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
            res = requests.post(
                url=self.TOKEN_URL,
                json={
                    "client_id": self.CLIENT_ID,
                    "refresh_token": self.token_set["refresh_token"],
                    "grant_type": "refresh_token",
                },
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
            res = requests.get(
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
            res = requests.get(
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


def base64_url_encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def generate_code_verifier():
    verifier = secrets.token_urlsafe(32)
    return verifier


def generate_code_challenge(verifier):
    sha256_hash = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64_url_encode(sha256_hash)
    return challenge
