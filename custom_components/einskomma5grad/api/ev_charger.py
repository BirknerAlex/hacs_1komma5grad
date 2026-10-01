from enum import Enum

import requests

from .client import REQUEST_TIMEOUT, Client
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

    def assigned_charger_id(self) -> str | None:
        return self._data.get("chargerId")

    def name(self) -> str | None:
        return self._data.get("name")

    def charging_mode(self) -> ChargingMode:
        return ChargingMode(self._data["chargingMode"])

    def _patch(self, fields: dict, what: str) -> None:
        """PATCH the EV asset; the app always sends id, type and connectionStatus."""
        try:
            res = self._api.patch(
                url=self._api.HEARTBEAT_API
                + "/api/v2/sites/"
                + self._system.id()
                + "/assets/evs/"
                + self.id(),
                json={
                    "id": self.id(),
                    "connectionStatus": self._data.get("connectionStatus"),
                    **fields,
                    "type": self._data.get("type", "EV"),
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + self._api.get_token(),
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as err:
            raise RequestError(f"Failed to set {what} due to network error: {err}") from err

        if res.status_code != 200:
            raise RequestError(f"Failed to set {what}: " + res.text)

    def set_charging_mode(self, mode: ChargingMode) -> None:
        if self.charging_mode() == mode:
            return

        # Mirrors the app, which sends the schedule settings along with the mode.
        self._patch(
            {
                "departureTime": self._data.get("departureTime"),
                "targetSoc": self._data.get("targetSoc"),
                "defaultSoc": self._data.get("defaultSoc"),
                "chargingMode": mode.value,
            },
            "charging mode",
        )

        self._data["chargingMode"] = mode.value

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

        self._patch({"manualSoc": soc_decimal}, "state of charge")

        self._data["manualSoc"] = soc_decimal
