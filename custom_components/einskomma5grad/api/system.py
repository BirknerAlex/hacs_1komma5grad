import datetime

import requests

from .client import Client
from .error import RequestError
from .ev_charger import EVCharger


class System:
    def __init__(self, client: Client, data: dict):
        self.client = client
        self.data = data

    def id(self) -> str:
        return self.data["id"]

    def get_live_overview(self):
        res = requests.get(
            url=self.client.HEARTBEAT_API
            + "/api/v1/systems/"
            + self.id()
            + "/live-overview",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self.client.get_token(),
            },
        )

        if res.status_code != 200:
            raise RequestError("Failed to get live data: " + res.text)

        return res.json()

    def get_ev_chargers(self) -> list[EVCharger]:
        res = requests.get(
            url=self.client.HEARTBEAT_API
            + "/api/v1/systems/"
            + self.id()
            + "/devices/evs",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self.client.get_token(),
            },
        )

        if res.status_code != 200:
            raise RequestError("Failed to get EV chargers: " + res.text)

        return [EVCharger(self.client, self, ev) for ev in res.json()]

    def get_ems_settings(self):
        res = requests.get(
            url=self.client.HEARTBEAT_API
            + "/api/v1/systems/"
            + self.id()
            + "/ems/actions/get-settings",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self.client.get_token(),
            },
        )

        if res.status_code != 200:
            raise RequestError("Failed to get EMS settings: " + res.text)

        return res.json()

    # Set the EMS mode of the system
    def set_ems_mode(self, auto: bool):
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
        )

        if res.status_code != 201:
            raise RequestError("Failed to set EMS mode: " + res.text)

    def get_prices(self, start: datetime, end: datetime):
        res = requests.get(
            url=self.client.HEARTBEAT_API
            + "/api/v1/systems/"
            + self.id()
            + "/charts/market-prices",
            params={
                "from": start.strftime("%Y-%m-%d"),
                "to": end.strftime("%Y-%m-%d"),
                "resolution": "1h",
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self.client.get_token(),
            },
        )

        if res.status_code != 200:
            raise RequestError("Failed to get prices: " + res.text)

        return res.json()["energyMarketWithGridCosts"]["data"]
