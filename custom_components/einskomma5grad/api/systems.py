import requests

from .client import Client
from .error import RequestError
from .system import System


class Systems:
    def __init__(self, client: Client):
        self.client = client

    def get_system(self, system_id: str) -> System:
        res = requests.get(
            url=self.client.HEARTBEAT_API + "/api/v2/systems/" + system_id,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self.client.get_token(),
            },
        )

        if res.status_code != 200:
            raise RequestError("Failed to get system: " + res.text)

        return System(self.client, res.json())

    # Returns a list with all systems the user has access to
    def get_systems(self) -> list[System]:
        res = requests.get(
            url=self.client.HEARTBEAT_API + "/api/v2/systems",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self.client.get_token(),
            },
        )

        if res.status_code != 200:
            raise RequestError("Failed to get systems: " + res.text)

        systems = res.json()["data"]

        # remove systems with id == "00000000-0000-0000-0000-000000000000"
        systems = [
            system
            for system in systems
            if system["id"] != "00000000-0000-0000-0000-000000000000"
        ]

        return [System(self.client, system) for system in systems]
