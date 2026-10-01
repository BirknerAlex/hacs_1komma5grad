"""Integration 101 Template integration using DataUpdateCoordinator."""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api.client import Client
from .api.error import ApiError
from .api.ev_charger import ChargingMode
from .api.system import System
from .api.systems import Systems
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    INSIGHTS_REFRESH_INTERVAL,
    PRICE_REFRESH_INTERVAL,
    SAVINGS_WINDOW_DAYS,
)

if TYPE_CHECKING:
    from .error_reporting import ErrorReporter

_LOGGER = logging.getLogger(__name__)

@dataclass
class EVData:
    """Class to hold EV data."""
    ev_name: str | None
    current_soc: float | None
    charging_mode: str | None
    system_id: str | None
    assigned_charger_id: str | None = None

@dataclass
class AssetInfo:
    """Individual device asset info from status-and-assets endpoint."""
    asset_id: str
    asset_type: str  # EV_CHARGER, HYBRID, HEAT_PUMP, METER
    manufacturer: str | None
    model: str | None
    serial_number: str | None
    name: str | None

@dataclass
class GatewayInfo:
    """Gateway device info."""
    gateway_id: str
    serial_number: str
    system_name: str
    system_id: str

@dataclass
class DeviceData:
    """Holds all device registry info for a system."""
    gateway: GatewayInfo | None = None
    assets_by_type: dict[str, list[AssetInfo]] | None = None

@dataclass
class SystemsData:
    """Class to hold api data."""

    systems: list[System]

    prices: dict[str, dict] | None = None

    live_overview: dict[str, dict] | None = None

    ems_settings: dict[str, dict] | None = None

    ev_data: dict[str, EVData] | None = None

    ev_charging_modes: dict[str, list[str]] | None = None

    device_data: dict[str, DeviceData] | None = None

    energy_today: dict[str, dict] | None = None

    # Per system: heartbeat_prices, comparison_price, energy_savings,
    # energy_trader and energy_trader_monthly (each None when unavailable).
    insights: dict[str, dict[str, dict | None]] | None = None

def _still_fresh(
    last: datetime.datetime | None, now: datetime.datetime, interval: timedelta
) -> bool:
    """Whether a cached response is recent enough and from the same local day.

    Day totals in these responses belong to the local day they were fetched on.
    """
    return (
        last is not None
        and now - last < interval
        and dt_util.as_local(last).date() == dt_util.as_local(now).date()
    )


class Coordinator(DataUpdateCoordinator[SystemsData]):
    """1KOMMA5GRAD coordinator."""

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

        # Market prices cover a 2-day window at 15m resolution and the API
        # allows only 1 request/minute, so they are refetched far less often
        # than the rest of the data.
        self._prices_fetched_at: dict[str, datetime.datetime] = {}
        self._insights_fetched_at: dict[str, datetime.datetime] = {}

        # Set by async_setup_entry when the user opted in to error reporting.
        # Home Assistant logs UpdateFailed itself, so it is reported explicitly.
        self.error_reporter: ErrorReporter | None = None

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

    def _previous_value(self, field: str, system_id: str):
        """Return the last successfully fetched value for a field, if any."""
        if self.data is None:
            return None
        return getattr(self.data, field, {}).get(system_id)

    async def _fetch_field(self, label, field, system_id, func, *args, fallback="previous"):
        """Run one API call, isolating its failure from the rest of the update.

        A single flaky endpoint must not abort the whole coordinator refresh
        (which would freeze unrelated data, e.g. price forecasts, at their
        last-known values). On ApiError, `fallback` decides what's returned:
        - "previous": last successfully fetched value for `field`/`system_id`
        - "empty_list" / "none": a fixed placeholder, for fields we don't cache
        """
        try:
            return await self.hass.async_add_executor_job(func, *args)
        except ApiError:
            if fallback == "previous":
                _LOGGER.warning(
                    "Failed to get %s for system %s, keeping previous data",
                    label, system_id,
                )
                return self._previous_value(field, system_id)

            _LOGGER.warning("Failed to get %s for system %s, skipping", label, system_id)
            return [] if fallback == "empty_list" else None

    async def _fetch_prices(self, system: System, sid: str, start, end):
        """Fetch prices, reusing the cached value within PRICE_REFRESH_INTERVAL."""
        now = dt_util.utcnow()
        previous = self._previous_value("prices", sid)
        last = self._prices_fetched_at.get(sid)
        if previous is not None and _still_fresh(last, now, PRICE_REFRESH_INTERVAL):
            return previous

        # Record the attempt even on failure so a rate-limited endpoint isn't
        # hammered on every poll.
        self._prices_fetched_at[sid] = now
        return await self._fetch_field(
            "prices", "prices", sid, system.get_prices, start, end,
        )

    async def _fetch_insights(self, system: System, sid: str) -> dict[str, dict | None]:
        """Fetch the slowly changing price and savings figures once per hour.

        Every figure is isolated: one failing endpoint (e.g. Energy Trader on a
        contract without it) keeps its previous value and does not affect the rest.
        """
        previous = self._previous_value("insights", sid) or {}
        now = dt_util.utcnow()
        last = self._insights_fetched_at.get(sid)
        if previous and _still_fresh(last, now, INSIGHTS_REFRESH_INTERVAL):
            return previous

        # Record the attempt even on failure, like the prices.
        self._insights_fetched_at[sid] = now
        today = dt_util.now().date()
        calls = {
            "heartbeat_prices": (system.get_heartbeat_prices, ()),
            "comparison_price": (system.get_comparison_price, ()),
            "energy_savings": (
                system.get_energy_savings,
                (today - timedelta(days=SAVINGS_WINDOW_DAYS), today),
            ),
            "energy_trader": (system.get_energy_trader, ()),
            "energy_trader_monthly": (system.get_energy_trader_monthly_savings, ()),
        }
        result: dict[str, dict | None] = {}
        for key, (func, args) in calls.items():
            try:
                result[key] = await self.hass.async_add_executor_job(func, *args)
            except ApiError:
                _LOGGER.debug("Failed to get %s for system %s, keeping previous", key, sid)
                result[key] = previous.get(key)
        return result

    def get_insights_by_id(self, system_id: str) -> dict[str, dict | None]:
        """Return the price and savings figures by system id."""
        if self.data.insights is None:
            return {}
        return self.data.insights.get(system_id) or {}

    def set_error_reporter(self, error_reporter: ErrorReporter) -> None:
        """Enable error reporting and tracing of refreshes and HTTP requests."""
        self.error_reporter = error_reporter
        self.api.tracer = error_reporter.http_span
        self.api.on_issue = error_reporter.capture_api_issue

    async def async_update_data(self) -> SystemsData:
        """Fetch data from the API, traced if error reporting is enabled."""
        if self.error_reporter is None:
            return await self._fetch_all()
        with self.error_reporter.trace("coordinator refresh", op="coordinator.refresh"):
            return await self._fetch_all()

    async def _fetch_all(self) -> SystemsData:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """

        systems_client = Systems(self.api)

        try:
            systems = await self.hass.async_add_executor_job(systems_client.get_systems)

            # Local midnight, so the day totals in the price response cover the
            # local calendar day like the other daily figures.
            start = dt_util.start_of_local_day().astimezone(datetime.timezone.utc)
            end = start + timedelta(days=2)

            # Local calendar day, so daily energy totals align with the dashboard.
            today = dt_util.now().date()

            prices = {}
            ems_settings = {}
            live_overview = {}
            ev_data = {}
            ev_charging_modes = {}
            device_data = {}
            energy_today = {}
            insights = {}
            for system in systems:
                sid = system.id()

                prices[sid] = await self._fetch_prices(system, sid, start, end)
                insights[sid] = await self._fetch_insights(system, sid)
                energy_today[sid] = await self._fetch_field(
                    "historical energy", "energy_today", sid,
                    system.get_energy_historical, today, fallback="none",
                )
                ems_settings[sid] = await self._fetch_field(
                    "EMS settings", "ems_settings", sid,
                    system.get_ems_settings, fallback="none",
                )
                live_overview[sid] = await self._fetch_field(
                    "live overview", "live_overview", sid, system.get_live_overview,
                )
                ev_charging_modes[sid] = await self._fetch_field(
                    "EV charging modes", "ev_charging_modes", sid,
                    system.get_displayed_ev_charging_modes,
                )

                ev_chargers = await self._fetch_field(
                    "EV chargers", "ev_chargers", sid,
                    system.get_ev_chargers, fallback="empty_list",
                )
                for ev_charger in ev_chargers or []:
                    ev_data[ev_charger.id()] = EVData(
                        ev_name=ev_charger.name(),
                        current_soc=ev_charger.current_soc(),
                        charging_mode=ev_charger.charging_mode().value,
                        system_id=sid,
                        assigned_charger_id=ev_charger.assigned_charger_id(),
                    )

                # Fetch device info (gateway + assets) — purely optional
                device_data[sid] = await self._fetch_device_data(system)
                self._report_multiple_chargers(ev_chargers or [], device_data[sid])

            # What is returned here is stored in self.data by the DataUpdateCoordinator
            return SystemsData(
                systems=systems,
                prices=prices,
                live_overview=live_overview,
                ems_settings=ems_settings,
                ev_data=ev_data,
                ev_charging_modes=ev_charging_modes,
                device_data=device_data,
                energy_today=energy_today,
                insights=insights,
            )
        except ApiError as err:
            if self.error_reporter:
                self.error_reporter.capture_api_issue(
                    "api_error", "coordinator refresh", None, {}, error=err
                )
            raise UpdateFailed(err) from err
        except (KeyError, TypeError, ValueError, AttributeError, IndexError) as err:
            # The API answered, but not in the shape we expect: it probably changed.
            if self.error_reporter:
                self.error_reporter.capture_api_issue(
                    "parse_error",
                    "coordinator refresh",
                    None,
                    {"responses": dict(self.api.response_shapes)},
                    error=err,
                )
            raise UpdateFailed(f"Unexpected API response: {err!r}") from err

    def _report_multiple_chargers(self, ev_chargers: list, device_data) -> None:
        """Report (counts only) how multi-charger systems look, to verify support."""
        if self.error_reporter is None:
            return
        charger_assets = (device_data.assets_by_type or {}).get("EV_CHARGER", [])
        if len(ev_chargers) < 2 and len(charger_assets) < 2:
            return
        asset_ids = {asset.asset_id for asset in charger_assets}
        assigned = [c.assigned_charger_id() for c in ev_chargers]
        self.error_reporter.capture_api_issue(
            "multiple_chargers",
            "assets/evs",
            None,
            {
                "evs": len(ev_chargers),
                "ev_charger_assets": len(charger_assets),
                "evs_with_assigned_charger": sum(1 for a in assigned if a),
                "distinct_assigned_chargers": len({a for a in assigned if a}),
                "assigned_matching_asset": sum(1 for a in assigned if a in asset_ids),
            },
        )

    def set_charging_mode(self, system_id: str, ev_id: str, mode: str):
        """Set the charging mode for an EV."""
        systems = Systems(self.api)
        system = systems.get_system(system_id)

        for charger in system.get_ev_chargers():
            if charger.id() == ev_id:
                charger.set_charging_mode(ChargingMode(mode))
                return

        _LOGGER.error("EV with id %s not found in system %s", ev_id, system_id)

    def set_ev_current_soc(self, system_id: str, ev_id: str, soc: float):
        """Set the current state of charge for an EV."""
        systems = Systems(self.api)
        system = systems.get_system(system_id)

        for charger in system.get_ev_chargers():
            if charger.id() == ev_id:
                charger.set_current_soc(soc)
                return

        _LOGGER.error("EV with id %s not found in system %s", ev_id, system_id)

    def get_ev_data(self, ev_id: str) -> EVData | None:
        """Return current state of charge by EV id."""
        if self.data.ev_data is None:
            return None
        return self.data.ev_data.get(ev_id)

    def get_system_by_id(self, system_id: str) -> System | None:
        """Return device by device id."""
        for system in self.data.systems:
            if system.id() == system_id:
                return system

        return None

    def get_prices_by_id(self, system_id: str) -> dict | None:
        """Return prices by system id."""
        if self.data.prices is None:
            return None
        return self.data.prices.get(system_id)

    def set_ems_auto_mode(self, system_id: str, enable: bool):
        """Enable EMS auto mode."""
        systems = Systems(self.api)
        systems.get_system(system_id).set_ems_mode(enable)

    def get_device_data_by_id(self, system_id: str) -> DeviceData | None:
        """Return device data by system id."""
        if self.data.device_data is None:
            return None
        return self.data.device_data.get(system_id)

    async def _fetch_device_data(self, system: System) -> DeviceData:
        """Fetch gateway and asset device info. Never raises."""
        result = DeviceData()

        # Gateway info from existing system data
        try:
            details = await self.hass.async_add_executor_job(system.get_details)
            gateways = (details or system.data).get("deviceGateways") or []
            if gateways:
                gw = gateways[0]
                serial = gw.get("serialNumber")
                if serial:
                    result.gateway = GatewayInfo(
                        gateway_id=gw.get("id", ""),
                        serial_number=serial,
                        system_name=system.data.get("systemName", ""),
                        system_id=system.id(),
                    )
        except (KeyError, TypeError, AttributeError, IndexError):
            _LOGGER.debug("Could not extract gateway info for system %s", system.id())

        # Assets from status-and-assets endpoint
        try:
            response = await self.hass.async_add_executor_job(
                system.get_status_and_assets,
            )
            if response and "assets" in response:
                assets_by_type = {}
                for asset in response["assets"]:
                    asset_type = asset.get("type")
                    if not asset_type:
                        continue
                    assets_by_type.setdefault(asset_type, []).append(AssetInfo(
                        asset_id=asset.get("id", ""),
                        asset_type=asset_type,
                        manufacturer=asset.get("manufacturer"),
                        model=asset.get("model"),
                        serial_number=asset.get("serialnumber"),
                        name=asset.get("name"),
                    ))
                result.assets_by_type = assets_by_type
        except (KeyError, TypeError, AttributeError):
            _LOGGER.debug("Could not fetch assets for system %s", system.id())

        return result

    def get_live_data_by_id(self, system_id: str) -> dict | None:
        """Return prices by system id."""
        if self.data.live_overview is None:
            return None
        return self.data.live_overview.get(system_id)

    def get_energy_today_by_id(self, system_id: str) -> dict | None:
        """Return today's measured energy totals by system id."""
        if self.data.energy_today is None:
            return None
        return self.data.energy_today.get(system_id)
