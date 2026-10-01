"""Regression test for GitHub issue #45.

The market-prices endpoint allows 1 request/minute per site, which the
default 60s poll interval hits exactly. Prices must be fetched
infrequently and a rate-limited response must not blank other data.
"""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.einskomma5grad.api.error import RequestError
from custom_components.einskomma5grad.const import (
    DOMAIN,
    PRICE_REFRESH_INTERVAL,
)
from tests.conftest import load_mock


async def _setup(hass, mock_config_entry):
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN][mock_config_entry.entry_id].coordinator


async def test_prices_fetched_once_within_refresh_interval(
    hass: HomeAssistant, mock_config_entry, mock_api, enable_custom_integrations
):
    """Polling every minute must not refetch prices every minute."""
    from custom_components.einskomma5grad.api.system import System

    with patch.object(
        System, "get_prices", autospec=True, return_value=load_mock(
            "GET_systems_id_charts_market-prices.json"
        ),
    ) as get_prices:
        coordinator = await _setup(hass, mock_config_entry)
        await coordinator.async_refresh()
        await coordinator.async_refresh()
        assert get_prices.call_count == 1

        later = dt_util.utcnow() + PRICE_REFRESH_INTERVAL + timedelta(seconds=1)
        with patch("custom_components.einskomma5grad.coordinator.dt_util.utcnow", return_value=later):
            await coordinator.async_refresh()
        assert get_prices.call_count == 2


async def test_rate_limited_prices_keep_previous_and_other_data(
    hass: HomeAssistant, mock_config_entry, mock_api, enable_custom_integrations
):
    """A rate-limited price call keeps cached prices; update still succeeds."""
    from custom_components.einskomma5grad.api.system import System

    prices = load_mock("GET_systems_id_charts_market-prices.json")
    with patch.object(
        System, "get_prices", autospec=True,
        side_effect=[prices, RequestError("Too many market-prices requests")],
    ):
        coordinator = await _setup(hass, mock_config_entry)
        later = dt_util.utcnow() + PRICE_REFRESH_INTERVAL + timedelta(seconds=1)
        with patch("custom_components.einskomma5grad.coordinator.dt_util.utcnow", return_value=later):
            await coordinator.async_refresh()

        assert coordinator.last_update_success
        sid = coordinator.data.systems[0].id()
        assert coordinator.data.prices[sid] == prices
        assert coordinator.data.live_overview[sid] is not None
