"""Binary sensor platform for the D-LOGG USB integration.

Channels configured as "switch" are exposed as read-only binary sensors:
the D-LOGG protocol only reports the current output state, it cannot be
toggled, so the entity must not render as an interactive slider.
"""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    """Create one read-only binary sensor per channel configured as switch."""
    coordinator: DLoggCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        DLoggBinarySensor(coordinator, entry, channel, config)
        for channel, config in get_channel_config(entry).items()
        if config.get(CONF_CHANNEL_TYPE) == TYPE_SWITCH
    ]
    async_add_entities(entities)


class DLoggBinarySensor(CoordinatorEntity[DLoggCoordinator], BinarySensorEntity):
    """Read-only on/off state of a digital D-LOGG channel or output."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: DLoggCoordinator,
        entry: ConfigEntry,
        channel: str,
        config: dict[str, str],
    ) -> None:
        """Initialize the binary sensor."""
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
        if "_A" in self._channel:
            return bool(data.get("outputs", {}).get(self._channel, 0))
        sensor = data.get("sensors", {}).get(self._channel)
        if sensor is None:
            return None
        return bool(sensor.get("value"))
