from enum import Enum

import requests

from .client import Client
from .error import RequestError


class ChargingMode(Enum):
    """Enum representing different charging modes for the EV charger."""

    SMART_CHARGE = "SMART_CHARGE"
    QUICK_CHARGE = "QUICK_CHARGE"
    SOLAR_CHARGE = "SOLAR_CHARGE"


class EVCharger:
    """Class representing an EV charger."""

    def __init__(self, api: Client, system, data: dict) -> None:
        """Initialize the EVCharger with the given API client, system, and data."""

        self._system = system
        self._api = api
        self._data = data

    def id(self) -> str:
        return self._data["id"]

    def name(self) -> str | None:
        if "profile" in self._data and "name" in self._data["profile"]:
            return self._data["profile"]["name"]

        return None

    def charging_mode(self) -> ChargingMode:
        return ChargingMode(self._data["chargeSettings"]["chargingMode"])

    def set_charging_mode(self, mode: ChargingMode) -> None:
        if self.charging_mode() == mode:
            return

        res = requests.patch(
            url=self._api.HEARTBEAT_API
            + "/api/v1/systems/"
            + self._system.id()
            + "/devices/evs/"
            + self.id(),
            json={"chargeSettings": {"chargingMode": mode.value}},
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self._api.get_token(),
            },
        )

        if res.status_code != 200:
            raise RequestError("Failed to set charging mode: " + res.text)

        self._data["chargeSettings"]["chargingMode"] = mode.value

    def current_soc(self) -> float | None:
        if self.charging_mode() != ChargingMode.SMART_CHARGE:
            return None

        manual_soc = self._data.get("manualSoc")
        if manual_soc is None:
            return None

        return float(manual_soc * 100.0)

    def set_current_soc(self, soc: float) -> None:
        if self.charging_mode() != ChargingMode.SMART_CHARGE:
            return

        soc_decimal = 0
        if soc > 0:
            soc_decimal = float(soc / 100.0)

        res = requests.patch(
            url=self._api.HEARTBEAT_API
                + "/api/v1/systems/"
                + self._system.id()
                + "/devices/evs/"
                + self.id(),
            json={"id":  self.id(), "manualSoc": soc_decimal},
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self._api.get_token(),
            },
        )

        if res.status_code != 200:
            raise RequestError("Failed to set state of charge: " + res.text)

        self._data["manualSoc"] = soc
