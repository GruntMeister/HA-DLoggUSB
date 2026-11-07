"""Switch platform for the D-LOGG USB integration (digital channels and outputs)."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_channel_config
from .const import CONF_CHANNEL_NAME, CONF_CHANNEL_TYPE, CONF_PORT, DOMAIN, TYPE_SWITCH
from .coordinator import DLoggCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one read-only switch per channel configured as switch."""
    coordinator: DLoggCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        DLoggSwitch(coordinator, entry, channel, config)
        for channel, config in get_channel_config(entry).items()
        if config.get(CONF_CHANNEL_TYPE) == TYPE_SWITCH
    ]
    async_add_entities(entities)


class DLoggSwitch(CoordinatorEntity[DLoggCoordinator], SwitchEntity):
    """Read-only switch mirroring a digital D-LOGG channel or output.

    The D-LOGG protocol only exposes the current state, so the switch
    cannot be toggled from Home Assistant.
    """

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: DLoggCoordinator,
        entry: ConfigEntry,
        channel: str,
        config: dict[str, str],
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._channel = channel
        self._attr_name = config.get(CONF_CHANNEL_NAME, channel)
        self._attr_unique_id = f"{entry.entry_id}_{channel}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="D-LOGG",
            manufacturer="Technische Alternative",
            model="D-LOGG USB",
            serial_number=entry.data.get(CONF_PORT),
        )

    @property
    def is_on(self) -> bool | None:
        """Return True when the channel/output is active."""
        data = self.coordinator.data or {}
        if self._channel.startswith("A"):
            return bool(data.get("outputs", {}).get(self._channel, 0))
        sensor = data.get("sensors", {}).get(self._channel)
        if sensor is None:
            return None
        return bool(sensor.get("value"))
