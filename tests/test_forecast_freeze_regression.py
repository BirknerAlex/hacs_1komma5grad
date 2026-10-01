"""Regression test for GitHub issue #40.

The `forecast` attribute on the electricity price sensor stops updating
once the day-ahead auction results for the next day are published,
because a single unguarded API call failing during a coordinator poll
(coordinator.py `get_live_overview`, `get_ev_chargers`, etc. are not
wrapped in try/except like `get_energy_historical`/`get_ems_settings`)
aborts the *entire* update via `UpdateFailed`, leaving `self._prices`
(and therefore `forecast`) pinned to whatever was fetched on the last
successful poll — even though fresh price data was available.
"""

import copy
import json
from datetime import datetime, timedelta
from typing import cast
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.core import HomeAssistant

from custom_components.einskomma5grad.const import DOMAIN
from tests.conftest import SYSTEM_SLUG, load_mock

PRICE_ENTITY = f"sensor.electricity_price_{SYSTEM_SLUG}"

# Frozen at 2026-03-29 08:30 UTC (= 09:30 CET), matching test_sensor.py.
FROZEN_NOW = datetime(2026, 3, 29, 8, 30, 0, tzinfo=ZoneInfo("UTC"))


def _make_response(data, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = data
    resp.text = json.dumps(data)
    return resp


@pytest.fixture
def mock_api_flaky_second_poll():
    """Like conftest's mock_api, but:

    - The market-prices endpoint returns only "today" on the first poll,
      and "today + tomorrow" (day-ahead results published) on the second.
    - The live-overview endpoint fails with a RequestError on the second
      poll, simulating a transient upstream hiccup unrelated to prices.
    """
    from custom_components.einskomma5grad.api.error import RequestError

    prices_full = cast(dict, load_mock("GET_systems_id_charts_market-prices.json"))
    prices_today_only = copy.deepcopy(prices_full)
    prices_today_only["timeseries"] = {
        k: v
        for k, v in prices_full["timeseries"].items()
        if k.startswith(("2026-03-28", "2026-03-29"))
    }

    mock_data = {
        "systems": load_mock("GET_systems.json"),
        "live_overview": load_mock("GET_systems_id_live-overview.json"),
        "ems_settings": load_mock("GET_systems_id_ems_actions_get-settings.json"),
        "ev_chargers": load_mock("GET_systems_id_devices_evs.json"),
        "ev_modes": load_mock(
            "GET_sites_id_assets_evs_displayed-ev-charging-modes.json"
        ),
        "status_and_assets": load_mock("GET_sites_id_status-and-assets.json"),
        "energy_today": load_mock("GET_systems_id_energy-historical.json"),
    }

    call_counts = {"market-prices": 0, "live-overview": 0}

    def get_router(url, **kwargs):
        if "status-and-assets" in url:
            return _make_response(mock_data["status_and_assets"])
        if "energy-historical" in url:
            return _make_response(mock_data["energy_today"])
        if "/api/v2/systems" in url:
            path = url.split("/api/v2/systems")[1]
            if path and path != "/":
                return _make_response(cast(dict, mock_data["systems"])["data"][0])
            return _make_response(mock_data["systems"])
        if "live-overview" in url:
            call_counts["live-overview"] += 1
            # Call #1 happens during hass's automatic
            # async_config_entry_first_refresh() on setup. Call #2 is the
            # test's first *explicit* refresh (day-ahead not published yet).
            # Call #3 is the second explicit refresh (day-ahead published),
            # where we simulate the unrelated transient failure.
            if call_counts["live-overview"] == 3:
                raise RequestError("simulated transient failure")
            return _make_response(mock_data["live_overview"])
        if "market-prices" in url:
            call_counts["market-prices"] += 1
            if call_counts["market-prices"] <= 2:
                return _make_response(prices_today_only)
            return _make_response(prices_full)
        if "get-settings" in url:
            return _make_response(mock_data["ems_settings"])
        if "displayed-ev-charging-modes" in url:
            return _make_response(mock_data["ev_modes"])
        if "/devices/evs" in url:
            return _make_response(mock_data["ev_chargers"])
        raise ValueError(f"Unexpected GET URL: {url}")

    def post_router(url, **kwargs):
        if "set-manual-override" in url:
            return _make_response({}, status=201)
        raise ValueError(f"Unexpected POST URL: {url}")

    def patch_router(url, **kwargs):
        if "/devices/evs/" in url:
            return _make_response({})
        raise ValueError(f"Unexpected PATCH URL: {url}")

    with (
        patch(
            "custom_components.einskomma5grad.coordinator.Client"
        ) as mock_client_cls,
        patch(
            "custom_components.einskomma5grad.api.systems.requests.get",
            side_effect=get_router,
        ),
        patch(
            "custom_components.einskomma5grad.api.system.requests.get",
            side_effect=get_router,
        ),
        patch(
            "custom_components.einskomma5grad.api.system.requests.post",
            side_effect=post_router,
        ),
        patch(
            "custom_components.einskomma5grad.api.ev_charger.requests.patch",
            side_effect=patch_router,
        ),
    ):
        client = MagicMock()
        client.get_token.return_value = "mock_token"
        client.HEARTBEAT_API = "https://heartbeat.1komma5grad.com"
        client.get.side_effect = get_router
        client.post.side_effect = post_router
        client.patch.side_effect = patch_router
        mock_client_cls.return_value = client

        yield {"client": client, "data": mock_data}


async def test_forecast_still_updates_when_unrelated_endpoint_fails(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api_flaky_second_poll,
    enable_custom_integrations,
):
    """Day-ahead prices must reach the sensor even if another endpoint hiccups.

    Reproduces GitHub issue #40: after the day-ahead auction results for
    the next day are published, the `forecast` attribute should extend
    into the next day on the next poll. It must not stay frozen just
    because an unrelated endpoint (live-overview) failed once.
    """
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.einskomma5grad.sensor_electricity_price.dt_util.now",
        return_value=FROZEN_NOW,
    ), patch(
        "custom_components.einskomma5grad.coordinator.dt_util.now",
        return_value=FROZEN_NOW,
    ), patch(
        # Disable price throttling so every poll refetches prices.
        "custom_components.einskomma5grad.coordinator.PRICE_REFRESH_INTERVAL",
        timedelta(0),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id].coordinator

        # First poll: only "today"'s prices are available (day-ahead not
        # yet published). forecast should NOT reach into the next day.
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        state = hass.states.get(PRICE_ENTITY)
        assert state is not None
        forecast_after_first_poll = state.attributes["forecast"]
        assert all(
            entry["datetime"] < "2026-03-30T00:00:00"
            for entry in forecast_after_first_poll
        )

        # Second poll: day-ahead results for tomorrow are now published,
        # but an unrelated endpoint (live-overview) fails transiently.
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        state = hass.states.get(PRICE_ENTITY)
        assert state is not None
        forecast_after_second_poll = state.attributes.get("forecast")

        assert forecast_after_second_poll is not None and any(
            entry["datetime"].startswith("2026-03-30")
            for entry in forecast_after_second_poll
        ), (
            "forecast did not extend into the next day after day-ahead "
            "prices were published — the price fetch was blocked by an "
            "unrelated endpoint failure (see coordinator.py async_update_data, "
            "unguarded calls around get_live_overview/get_ev_chargers). "
            f"state={state.state!r} attrs={dict(state.attributes)}"
        )
