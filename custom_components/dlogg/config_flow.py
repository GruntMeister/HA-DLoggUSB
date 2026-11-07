"""Config flow for the D-LOGG USB integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow

if TYPE_CHECKING:
    # Only available on HA 2024.4+; annotations are strings, so this must
    # not be imported at runtime to keep the flow loadable on older versions.
    from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CHANNEL_TYPES,
    CONF_BAUDRATE,
    CONF_CHANNEL_NAME,
    CONF_CHANNEL_TYPE,
    CONF_CHANNELS,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    DEFAULT_BAUDRATE,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    TYPE_POWER,
    TYPE_SWITCH,
    TYPE_TEMPERATURE,
)
from .dlogg import KIND_DIGITAL, KIND_FLOW, KIND_RADIATION, detect_channels

_LOGGER = logging.getLogger(__name__)

BAUDRATES = [9600, 19200, 38400, 57600, 115200]


def _default_type(kind: str) -> str:
    """Pick a sensible default value type for a detected channel kind."""
    if kind in (KIND_FLOW, KIND_RADIATION):
        return TYPE_POWER
    if kind == KIND_DIGITAL:
        return TYPE_SWITCH
    return TYPE_TEMPERATURE


def _channel_schema(
    channel_kinds: dict[str, str],
    defaults: dict[str, dict[str, str]] | None = None,
) -> vol.Schema:
    """Build the form that maps each channel to a free name and a value type."""
    defaults = defaults or {}
    fields: dict[Any, Any] = {}
    for channel, kind in channel_kinds.items():
        name_default = channel
        type_default = _default_type(kind)
        if channel in defaults:
            name_default = defaults[channel].get(CONF_CHANNEL_NAME, channel)
            type_default = defaults[channel].get(CONF_CHANNEL_TYPE, type_default)
        fields[vol.Required(f"name_{channel}", default=name_default)] = str
        fields[vol.Required(f"type_{channel}", default=type_default)] = SelectSelector(
            SelectSelectorConfig(
                options=CHANNEL_TYPES,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="channel_type",
            )
        )
    return vol.Schema(fields)


def _extract_channels(user_input: dict[str, Any], channel_kinds: dict[str, str]) -> dict[str, dict[str, str]]:
    """Turn the submitted form fields into the stored channel configuration."""
    channels: dict[str, dict[str, str]] = {}
    for channel, kind in channel_kinds.items():
        channels[channel] = {
            CONF_CHANNEL_NAME: user_input.get(f"name_{channel}") or channel,
            CONF_CHANNEL_TYPE: user_input.get(f"type_{channel}") or _default_type(kind),
        }
    return channels


class DLoggConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow: connection first, then channel naming."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._port: str | None = None
        self._baudrate: int = DEFAULT_BAUDRATE
        self._scan_interval: int = DEFAULT_SCAN_INTERVAL
        self._channel_kinds: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the serial port and try to detect the channels."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._port = user_input[CONF_PORT]
            self._baudrate = user_input[CONF_BAUDRATE]
            self._scan_interval = user_input[CONF_SCAN_INTERVAL]
            try:
                self._channel_kinds = await self.hass.async_add_executor_job(
                    detect_channels, self._port, self._baudrate
                )
            except Exception:
                _LOGGER.exception("Cannot connect to D-LOGG on %s", self._port)
                errors["base"] = "cannot_connect"
            else:
                if not self._channel_kinds:
                    errors["base"] = "no_channels"
                else:
                    return await self.async_step_channels()

        schema = vol.Schema(
            {
                vol.Required(CONF_PORT, default=self._port or DEFAULT_PORT): str,
                vol.Required(CONF_BAUDRATE, default=self._baudrate): vol.All(
                    vol.Coerce(int), vol.In(BAUDRATES)
                ),
                vol.Required(CONF_SCAN_INTERVAL, default=self._scan_interval): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_channels(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user assign a name and a value type to every detected channel."""
        if user_input is not None:
            return self.async_create_entry(
                title=f"D-LOGG ({self._port})",
                data={
                    CONF_PORT: self._port,
                    CONF_BAUDRATE: self._baudrate,
                    CONF_SCAN_INTERVAL: self._scan_interval,
                    CONF_CHANNELS: _extract_channels(user_input, self._channel_kinds),
                },
            )
        defaults = {
            channel: {
                CONF_CHANNEL_NAME: channel,
                CONF_CHANNEL_TYPE: _default_type(kind),
            }
            for channel, kind in self._channel_kinds.items()
        }
        return self.async_show_form(
            step_id="channels",
            data_schema=_channel_schema(self._channel_kinds, defaults),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> DLoggOptionsFlow:
        """Return the options flow so names can be changed later."""
        return DLoggOptionsFlow()


class DLoggOptionsFlow(OptionsFlow):
    """Options flow to rename channels and change the polling interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the channel form pre-filled with the current configuration."""
        entry = self.config_entry
        channel_kinds = {
            channel: TYPE_SWITCH if channel.startswith("A") else TYPE_TEMPERATURE
            for channel in entry.data.get(CONF_CHANNELS, {})
        }
        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    CONF_CHANNELS: _extract_channels(user_input, channel_kinds),
                }
            )
        defaults = {
            channel: {
                CONF_CHANNEL_NAME: config.get(CONF_CHANNEL_NAME, channel),
                CONF_CHANNEL_TYPE: config.get(CONF_CHANNEL_TYPE, TYPE_TEMPERATURE),
            }
            for channel, config in entry.data.get(CONF_CHANNELS, {}).items()
        }
        # Merge already saved option values on top of the initial config
        for channel, config in entry.options.get(CONF_CHANNELS, {}).items():
            defaults.setdefault(channel, {}).update(config)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=entry.options.get(
                        CONF_SCAN_INTERVAL,
                        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ),
                ): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
                ),
                **_channel_schema(channel_kinds, defaults).schema,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
