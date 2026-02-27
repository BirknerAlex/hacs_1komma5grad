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

    for ev_id, ev in coordinator.data.ev_data.items():
        entities.append(EVCurrentStateOfCharge(coordinator, ev.system_id, ev_id))

    async_add_entities(entities)

