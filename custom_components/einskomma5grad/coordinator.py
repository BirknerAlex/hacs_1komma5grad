"""Integration 101 Template integration using DataUpdateCoordinator."""

from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import DOMAIN, HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api.client import Client
from .api.error import ApiError
from .api.ev_charger import ChargingMode
from .api.system import System
from .api.systems import Systems
from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class SystemsData:
    """Class to hold api data."""

    systems: list[System]

    prices: dict[str, dict] = None

    live_overview: dict[str, dict] = None

    ems_settings: dict[str, bool] = None


class Coordinator(DataUpdateCoordinator):
    """1KOMMA5GRAD coordinator."""

    data: SystemsData

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator."""

        self.hass = hass

        # Initialise your api here
        self.api = Client(
            config_entry.data[CONF_USERNAME], config_entry.data[CONF_PASSWORD]
        )

        # set variables from options.  You need a default here incase options have not been set
        self.poll_interval = config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        # Initialise DataUpdateCoordinator
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN} ({config_entry.unique_id})",
            # Method to call on every update interval.
            update_method=self.async_update_data,
            # Polling interval. Will only be polled if there are subscribers.
            # Using config option here but you can just use a value.
            update_interval=timedelta(seconds=self.poll_interval),
        )

    async def async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """

        systems_client = Systems(self.api)

        try:
            systems = await self.hass.async_add_executor_job(systems_client.get_systems)

            start = dt_util.now() - timedelta(hours=2)
            end = dt_util.now() + timedelta(hours=2)

            prices = {}
            ems_settings = {}
            live_overview = {}
            for system in systems:
                prices[system.id()] = await self.hass.async_add_executor_job(
                    system.get_prices,
                    start,
                    end,
                )

                ems_settings[system.id()] = await self.hass.async_add_executor_job(
                    system.get_ems_settings,
                )

                live_overview[system.id()] = await self.hass.async_add_executor_job(
                    system.get_live_overview,
                )
            # What is returned here is stored in self.data by the DataUpdateCoordinator
            return SystemsData(
                systems=systems,
                prices=prices,
                live_overview=live_overview,
                ems_settings=ems_settings,
            )
        except ApiError as err:
            raise UpdateFailed(err) from err

    def set_charging_mode(self, system_id: str, ev_id: str, mode: str):
        """Set the charging mode for an EV."""
        systems = Systems(self.api)
        system = systems.get_system(system_id)

        for charger in system.get_ev_chargers():
            if charger.id() == ev_id:
                charger.set_charging_mode(ChargingMode(mode))

    def get_system_by_id(self, system_id: str) -> System | None:
        """Return device by device id."""
        for system in self.data.systems:
            if system.id() == system_id:
                return system

        return None

    def get_prices_by_id(self, system_id: str) -> dict | None:
        """Return prices by system id."""

        return self.data.prices[system_id]

    def set_ems_auto_mode(self, system_id: str, enable: bool):
        """Enable EMS auto mode."""
        systems = Systems(self.api)
        systems.get_system(system_id).set_ems_mode(enable)

    def get_live_data_by_id(self, system_id: str) -> dict | None:
        """Return prices by system id."""

        return self.data.live_overview[system_id]
