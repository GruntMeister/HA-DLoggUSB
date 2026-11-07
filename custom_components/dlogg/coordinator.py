"""Data update coordinator for the D-LOGG USB integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .dlogg import DLoggClient

_LOGGER = logging.getLogger(__name__)


class DLoggCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the D-LOGG over USB serial and share the parsed values with the entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: DLoggClient,
        scan_interval: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.entry = entry
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest values from the D-LOGG (blocking serial I/O in executor)."""
        try:
            return await self.hass.async_add_executor_job(self.client.read)
        except Exception as err:
            raise UpdateFailed(f"Error reading from D-LOGG: {err}") from err
