"""The slowly changing price and savings figures are fetched hourly, each in isolation."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.einskomma5grad.api.error import RequestError
from custom_components.einskomma5grad.api.system import System
from custom_components.einskomma5grad.const import DOMAIN, INSIGHTS_REFRESH_INTERVAL


async def _setup(hass, mock_config_entry):
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN][mock_config_entry.entry_id].coordinator


async def test_insights_fetched_once_per_interval(
    hass: HomeAssistant, mock_config_entry, mock_api, enable_custom_integrations
):
    with patch.object(
        System, "get_comparison_price", autospec=True, return_value={"comparisonPrice": {}}
    ) as call:
        coordinator = await _setup(hass, mock_config_entry)
        await coordinator.async_refresh()
        await coordinator.async_refresh()
        assert call.call_count == 1

        later = dt_util.utcnow() + INSIGHTS_REFRESH_INTERVAL + timedelta(seconds=1)
        with patch("custom_components.einskomma5grad.coordinator.dt_util.utcnow", return_value=later):
            await coordinator.async_refresh()
        assert call.call_count == 2


async def test_failing_endpoint_does_not_affect_the_others(
    hass: HomeAssistant, mock_config_entry, mock_api, enable_custom_integrations
):
    """Energy Trader is missing on some contracts: the rest must still update."""
    with patch.object(
        System, "get_energy_trader", autospec=True, side_effect=RequestError("404")
    ):
        coordinator = await _setup(hass, mock_config_entry)

    assert coordinator.last_update_success
    insights = coordinator.get_insights_by_id(coordinator.data.systems[0].id())
    assert insights["energy_trader"] is None
    assert insights["heartbeat_prices"] is not None
    assert insights["energy_savings"] is not None


async def test_failed_refresh_keeps_previous_value(
    hass: HomeAssistant, mock_config_entry, mock_api, enable_custom_integrations
):
    coordinator = await _setup(hass, mock_config_entry)
    sid = coordinator.data.systems[0].id()
    before = coordinator.get_insights_by_id(sid)["energy_savings"]
    assert before is not None

    later = dt_util.utcnow() + INSIGHTS_REFRESH_INTERVAL + timedelta(seconds=1)
    with patch.object(
        System, "get_energy_savings", autospec=True, side_effect=RequestError("boom")
    ), patch("custom_components.einskomma5grad.coordinator.dt_util.utcnow", return_value=later):
        await coordinator.async_refresh()

    assert coordinator.get_insights_by_id(sid)["energy_savings"] == before


def test_cache_expires_at_local_midnight():
    """Day totals belong to the local day they were fetched on."""
    from custom_components.einskomma5grad.coordinator import _still_fresh

    midnight = dt_util.start_of_local_day(dt_util.now() + timedelta(days=1))
    before = midnight - timedelta(minutes=10)

    assert _still_fresh(before - timedelta(minutes=5), before, INSIGHTS_REFRESH_INTERVAL)
    assert not _still_fresh(before, midnight + timedelta(minutes=10), INSIGHTS_REFRESH_INTERVAL)
    assert not _still_fresh(before - INSIGHTS_REFRESH_INTERVAL * 2, before, INSIGHTS_REFRESH_INTERVAL)
    assert not _still_fresh(None, before, INSIGHTS_REFRESH_INTERVAL)
