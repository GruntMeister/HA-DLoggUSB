"""Sensor platform for the D-LOGG USB integration (temperature and power channels)."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_channel_config
from .const import (
    CONF_CHANNEL_NAME,
    CONF_PORT,
    CONF_CHANNEL_TYPE,
    DOMAIN,
    TYPE_POWER,
    TYPE_TEMPERATURE,
)
from .coordinator import DLoggCoordinator

SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    TYPE_TEMPERATURE: SensorEntityDescription(
        key=TYPE_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TYPE_POWER: SensorEntityDescription(
        key=TYPE_POWER,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one sensor per channel configured as temperature or power."""
    coordinator: DLoggCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        DLoggSensor(coordinator, entry, channel, config)
        for channel, config in get_channel_config(entry).items()
        if config.get(CONF_CHANNEL_TYPE) in SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)


class DLoggSensor(CoordinatorEntity[DLoggCoordinator], SensorEntity):
    """A temperature or power value read from a D-LOGG channel."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: DLoggCoordinator,
        entry: ConfigEntry,
        channel: str,
        config: dict[str, str],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._channel = channel
        self.entity_description = SENSOR_DESCRIPTIONS[config[CONF_CHANNEL_TYPE]]
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
    def native_value(self) -> float | None:
        """Return the current value of the channel, or None when unused/invalid."""
        data = self.coordinator.data or {}
        sensor = data.get("sensors", {}).get(self._channel)
        if sensor is None:
            return None
        value = sensor.get("value")
        if value is None or value != value:  # NaN check
            return None
        return value
