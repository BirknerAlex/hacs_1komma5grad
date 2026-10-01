import datetime
import logging

import requests

from .client import REQUEST_TIMEOUT, Client
from .error import RequestError
from .ev_charger import EVCharger

_LOGGER = logging.getLogger(__name__)


class System:
    def __init__(self, client: Client, data: dict):
        self.client = client
        self.data = data

    def id(self) -> str:
        return self.data["id"]

    def get_status_and_assets(self) -> dict | None:
        """Fetch site status and assets. Returns None on any failure."""
        try:
            res = self.client.get(
                url=self.client.HEARTBEAT_API
                + "/api/v3/sites/"
                + self.id()
                + "/status-and-assets",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + self.client.get_token(),
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException:
            _LOGGER.debug("Failed to fetch status-and-assets for system %s", self.id())
            return None

        if res.status_code != 200:
            _LOGGER.debug(
                "status-and-assets returned %s for system %s",
                res.status_code,
                self.id(),
            )
            return None

        return res.json()

    def get_details(self) -> dict | None:
        """Fetch extended system metadata, the only source of `deviceGateways`.

        Returns None on any failure; gateway info is optional.
        """
        try:
            res = self.client.get(
                url=self.client.HEARTBEAT_API
                + "/api/v1/systems/"
                + self.id()
                + "/details",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + self.client.get_token(),
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException:
            _LOGGER.debug("Failed to fetch details for system %s", self.id())
            return None

        if res.status_code != 200:
            _LOGGER.debug(
                "details returned %s for system %s", res.status_code, self.id()
            )
            return None

        try:
            return res.json()
        except ValueError:
            _LOGGER.debug("details returned invalid JSON for system %s", self.id())
            return None

    def get_live_overview(self):
        try:
            res = self.client.get(
                url=self.client.HEARTBEAT_API
                + "/api/v3/systems/"
                + self.id()
                + "/live-overview",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + self.client.get_token(),
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as err:
            raise RequestError(f"Failed to get live data due to network error: {err}") from err

        if res.status_code != 200:
            raise RequestError("Failed to get live data: " + res.text)

        return res.json()

    def get_ev_chargers(self) -> list[EVCharger]:
        try:
            res = self.client.get(
                url=self.client.HEARTBEAT_API
                + "/api/v2/sites/"
                + self.id()
                + "/assets/evs",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + self.client.get_token(),
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as err:
            raise RequestError(f"Failed to get EV chargers due to network error: {err}") from err

        if res.status_code != 200:
            raise RequestError("Failed to get EV chargers: " + res.text)

        return [EVCharger(self.client, self, ev) for ev in res.json()]

    def get_ems_settings(self):
        try:
            res = self.client.get(
                url=self.client.HEARTBEAT_API
                + "/api/v1/systems/"
                + self.id()
                + "/ems/actions/get-settings",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + self.client.get_token(),
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as err:
            raise RequestError(f"Failed to get EMS settings due to network error: {err}") from err

        if res.status_code != 200:
            raise RequestError("Failed to get EMS settings: " + res.text)

        return res.json()

    # Set the EMS mode of the system
    def set_ems_mode(self, auto: bool):
        try:
            res = self.client.post(
                url=self.client.HEARTBEAT_API
                + "/api/v1/systems/"
                + self.id()
                + "/ems/actions/set-manual-override",
                json={"manualSettings": {}, "overrideAutoSettings": auto is False},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + self.client.get_token(),
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as err:
            raise RequestError(f"Failed to set EMS mode due to network error: {err}") from err

        if res.status_code != 201:
            raise RequestError("Failed to set EMS mode: " + res.text)

    def get_displayed_ev_charging_modes(self) -> list[str]:
        try:
            res = self.client.get(
                url=self.client.HEARTBEAT_API
                + "/api/v1/sites/"
                + self.id()
                + "/assets/evs/displayed-ev-charging-modes",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + self.client.get_token(),
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as err:
            raise RequestError(f"Failed to get EV charging modes due to network error: {err}") from err

        if res.status_code != 200:
            raise RequestError("Failed to get EV charging modes: " + res.text)

        data = res.json()
        return [
            mode["type"]
            for mode in data.get("displayedEvChargingModes", [])
            if not mode.get("disabled", False)
        ]

    def get_prices(self, start: datetime.datetime, end: datetime.datetime):
        try:
            res = self.client.get(
                url=self.client.HEARTBEAT_API
                + "/api/v4/systems/"
                + self.id()
                + "/charts/market-prices",
                params={
                    "from": start.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "to": end.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "resolution": "15m",
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + self.client.get_token(),
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as err:
            raise RequestError(f"Failed to get prices due to network error: {err}") from err

        if res.status_code != 200:
            raise RequestError("Failed to get prices: " + res.text)

        return res.json()

    def get_energy_historical(self, day: datetime.date, resolution: str = "1d"):
        """Fetch measured historical energy totals for a single day.

        Returns the API's aggregated daily energy values (production, grid,
        battery, consumption) in kWh, matching the figures shown in the
        1KOMMA5GRAD dashboard.
        """
        date_str = day.strftime("%Y-%m-%d")
        try:
            res = self.client.get(
                url=self.client.HEARTBEAT_API
                + "/api/v3/systems/"
                + self.id()
                + "/energy-historical",
                params={
                    "from": date_str,
                    "to": date_str,
                    "resolution": resolution,
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + self.client.get_token(),
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as err:
            raise RequestError(
                f"Failed to get historical energy due to network error: {err}"
            ) from err

        if res.status_code != 200:
            # A retry cannot help while rate limited.
            if resolution == "1d" and res.status_code != 429:
                # The daily aggregate does not exist yet right after midnight and
                # fails with an upstream error; 15m totals are available at once.
                _LOGGER.debug(
                    "energy-historical 1d returned %s for system %s, retrying with 15m",
                    res.status_code,
                    self.id(),
                )
                return self.get_energy_historical(day, resolution="15m")
            raise RequestError("Failed to get historical energy: " + res.text)

        return res.json()

    def _get_json(self, url: str, what: str, params: dict | None = None):
        """GET a JSON document, raising RequestError on any failure."""
        try:
            res = self.client.get(
                url=url,
                params=params,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + self.client.get_token(),
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as err:
            raise RequestError(f"Failed to get {what} due to network error: {err}") from err

        if res.status_code != 200:
            raise RequestError(f"Failed to get {what}: " + res.text)

        try:
            return res.json()
        except ValueError as err:
            raise RequestError(f"Failed to get {what}: invalid JSON") from err

    def get_heartbeat_prices(self):
        """Effective Heartbeat price and cost breakdown for day/week/month/halfYear/year."""
        return self._get_json(
            self.client.HEARTBEAT_API + "/api/v3/heartbeat-prices",
            "Heartbeat prices",
            {"siteId": self.id()},
        )

    def get_comparison_price(self):
        """Reference tariff the savings are compared against."""
        return self._get_json(
            self.client.HEARTBEAT_API + "/api/v2/comparison-price",
            "comparison price",
            {"siteId": self.id()},
        )

    def get_energy_savings(self, start: datetime.date, end: datetime.date):
        """Aggregated savings in EUR; the API only accepts dates, not times."""
        return self._get_json(
            self.client.HEARTBEAT_API
            + "/api/v1/systems/"
            + self.id()
            + "/energy-savings",
            "energy savings",
            {"from": start.strftime("%Y-%m-%d"), "to": end.strftime("%Y-%m-%d")},
        )

    def get_energy_trader(self):
        """Cumulative Energy Trader savings."""
        return self._get_json(
            self.client.HEARTBEAT_API + "/api/v2/energy-trader",
            "Energy Trader",
            {"siteId": self.id()},
        )

    def get_energy_trader_monthly_savings(self):
        """Average monthly Energy Trader savings (the path takes the site id)."""
        return self._get_json(
            self.client.HEARTBEAT_API
            + "/api/v1/energy-trader-savings/"
            + self.id()
            + "/month",
            "Energy Trader monthly savings",
        )
