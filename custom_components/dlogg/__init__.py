"""The D-LOGG USB integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_BAUDRATE,
    CONF_CHANNELS,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    DEFAULT_BAUDRATE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import DLoggCoordinator
from .dlogg import DLoggClient

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


def get_channel_config(entry: ConfigEntry) -> dict[str, dict[str, str]]:
    """Return the channel configuration, with options overriding the initial config."""
    channels = dict(entry.data.get(CONF_CHANNELS, {}))
    channels.update(entry.options.get(CONF_CHANNELS, {}))
    return channels


def get_scan_interval(entry: ConfigEntry) -> int:
    """Return the polling interval, preferring the options flow value."""
    return entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the D-LOGG integration from a config entry."""
    client = DLoggClient(
        entry.data[CONF_PORT],
        entry.data.get(CONF_BAUDRATE, DEFAULT_BAUDRATE),
    )
    coordinator = DLoggCoordinator(hass, entry, client, get_scan_interval(entry))
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when the options change."""
    await hass.config_entries.async_reload(entry.entry_id)
