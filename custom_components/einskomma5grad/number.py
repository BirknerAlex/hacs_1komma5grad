"""Number platform for 1KOMMA5GRAD integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import Coordinator
from .ev_current_soc import EVCurrentStateOfCharge

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the Number entities."""
    coordinator: Coordinator = hass.data[DOMAIN][config_entry.entry_id].coordinator

    entities = []

    for system in coordinator.data.systems:
        cards = coordinator.data.live_overview[system.id()]["summaryCards"]

        if "evs" not in cards:
            continue

        for ev in cards["evs"]:
            if "assignedChargerName" not in ev:
                continue

            entities.append(EVCurrentStateOfCharge(coordinator, system.id(), ev["id"]))

    async_add_entities(entities)

