"""The 1KOMMA5GRAD integration."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_ERROR_REPORTING, DEFAULT_ERROR_REPORTING, DOMAIN
from .coordinator import Coordinator
from .error_reporting import ErrorReporter

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SELECT, Platform.SWITCH, Platform.NUMBER]


@dataclass
class RuntimeData:
    """Class to hold your data."""

    coordinator: Coordinator
    cancel_update_listener: Callable
    error_reporter: ErrorReporter | None = None


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up 1KOMMA5GRAD from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    # Initialise the coordinator that manages data updates from your api.
    # This is defined in coordinator.py
    coordinator = Coordinator(hass, config_entry)

    # Perform an initial data load from api.
    # async_config_entry_first_refresh() is special in that it does not log errors if it fails
    await coordinator.async_config_entry_first_refresh()

    error_reporter = None
    if config_entry.options.get(CONF_ERROR_REPORTING, DEFAULT_ERROR_REPORTING):
        error_reporter = await ErrorReporter.async_create(hass)
        coordinator.set_error_reporter(error_reporter)
        error_reporter.set_system_ids(
            [system.id() for system in coordinator.data.systems]
        )

    try:
        # Initialise a listener for config flow options changes.
        # See config_flow for defining an options setting that shows up as configure on the integration.
        cancel_update_listener = config_entry.add_update_listener(_async_update_listener)

        # Add the coordinator and update listener to hass data to make
        # accessible throughout your integration
        # Note: this will change on HA2024.6 to save on the config entry.
        hass.data[DOMAIN][config_entry.entry_id] = RuntimeData(
            coordinator, cancel_update_listener, error_reporter
        )

        # Setup platforms (based on the list of entity types in PLATFORMS defined above)
        # This calls the async_setup method in each of your entity type files.
        await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    except BaseException:
        # Home Assistant does not call async_unload_entry for a failed setup, and
        # the reporter's logging handlers would stay attached.
        if error_reporter:
            await error_reporter.async_close(hass)
        raise

    # Return true to denote a successful setup.
    return True


async def _async_update_listener(hass: HomeAssistant, config_entry):
    """Handle config options update."""
    # Reload the integration when the options change.
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # This is called when you remove your integration or shutdown HA.
    # If you have created any custom services, they need to be removed here too.

    # Remove the config options update listener
    hass.data[DOMAIN][config_entry.entry_id].cancel_update_listener()

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    # Remove the config entry from the hass data object.
    if unload_ok:
        runtime_data = hass.data[DOMAIN].pop(config_entry.entry_id)
        if runtime_data.error_reporter:
            await runtime_data.error_reporter.async_close(hass)

    # Return that unloading was successful.
    return unload_ok
