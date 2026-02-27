import datetime

import requests

from .client import Client, REQUEST_TIMEOUT
from .error import RequestError
from .ev_charger import EVCharger


class System:
    def __init__(self, client: Client, data: dict):
        self.client = client
        self.data = data

    def id(self) -> str:
        return self.data["id"]

    def get_live_overview(self):
        try:
            res = requests.get(
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
            res = requests.get(
                url=self.client.HEARTBEAT_API
                + "/api/v1/systems/"
                + self.id()
                + "/devices/evs",
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
            res = requests.get(
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
            res = requests.post(
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
            res = requests.get(
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

    def get_prices(self, start: datetime, end: datetime):
        try:
            res = requests.get(
                url=self.client.HEARTBEAT_API
                + "/api/v4/systems/"
                + self.id()
                + "/charts/market-prices",
                params={
                    "from": start.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "to": end.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "resolution": "1h",
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
