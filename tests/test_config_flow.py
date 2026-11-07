"""Tests for the config flow and options flow dialogs.

These run without a full Home Assistant install: if the real `homeassistant`
package is not importable, minimal stubs are installed so that
`custom_components/dlogg/config_flow.py` can be imported and its dialog steps
executed. This guards against regressions like undefined names in flow steps
(e.g. the options flow crashing with NameError).

Run from the repository root:
    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import asyncio
import importlib
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "custom_components"))


def _install_ha_stubs() -> None:
    """Install minimal homeassistant/voluptuous stubs when HA is not available."""
    try:
        import homeassistant  # noqa: F401
        import voluptuous  # noqa: F401
        return  # real HA present (e.g. inside a HA dev environment)
    except ImportError:
        pass

    ha = types.ModuleType("homeassistant")
    ha.__path__ = []
    sys.modules["homeassistant"] = ha

    const = types.ModuleType("homeassistant.const")
    class Platform:
        SENSOR = "sensor"
        BINARY_SENSOR = "binary_sensor"
    const.Platform = Platform
    sys.modules["homeassistant.const"] = const

    core = types.ModuleType("homeassistant.core")
    class HomeAssistant: pass
    core.HomeAssistant = HomeAssistant
    core.callback = lambda f: f
    sys.modules["homeassistant.core"] = core

    ce = types.ModuleType("homeassistant.config_entries")
    class ConfigEntry: pass
    class _Flow:
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__()
        def async_show_form(self, **kwargs):
            return {"type": "form", **kwargs}
        def async_create_entry(self, **kwargs):
            return {"type": "create_entry", **kwargs}
    class ConfigFlow(_Flow):
        def __init_subclass__(cls, domain=None, **kwargs):
            super().__init_subclass__(**kwargs)
            cls.domain = domain
    class OptionsFlow(_Flow):
        pass
    ce.ConfigEntry = ConfigEntry
    ce.ConfigFlow = ConfigFlow
    ce.OptionsFlow = OptionsFlow
    sys.modules["homeassistant.config_entries"] = ce

    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    sys.modules["homeassistant.helpers"] = helpers

    uc = types.ModuleType("homeassistant.helpers.update_coordinator")
    class UpdateFailed(Exception): pass
    class _Sub:
        def __class_getitem__(cls, item): return cls
    class DataUpdateCoordinator(_Sub):
        def __init__(self, *a, **k): pass
    uc.UpdateFailed = UpdateFailed
    uc.DataUpdateCoordinator = DataUpdateCoordinator
    sys.modules["homeassistant.helpers.update_coordinator"] = uc

    sel = types.ModuleType("homeassistant.helpers.selector")
    class SelectSelector:
        def __init__(self, config): self.config = config
    class SelectSelectorConfig:
        def __init__(self, **kwargs): self.kwargs = kwargs
    class SelectSelectorMode:
        DROPDOWN = "dropdown"
    sel.SelectSelector = SelectSelector
    sel.SelectSelectorConfig = SelectSelectorConfig
    sel.SelectSelectorMode = SelectSelectorMode
    sys.modules["homeassistant.helpers.selector"] = sel

    if "voluptuous" not in sys.modules:
        try:
            import voluptuous  # noqa: F401
        except ImportError:
            vol = types.ModuleType("voluptuous")
            class _Marker:
                def __init__(self, key, default=None):
                    self.key = key
                    self.schema = key
                    self.default = default
            class _Schema:
                def __init__(self, schema): self.schema = schema
            vol.Required = lambda k, default=None: _Marker(k, default)
            vol.Optional = lambda k, default=None: _Marker(k, default)
            vol.Schema = lambda s: _Schema(s)
            vol.Coerce = lambda t: t
            vol.In = lambda c: c
            vol.All = lambda *a: a[0] if a else None
            vol.Range = type("Range", (), {"__init__": lambda self, min=None, max=None: None})
            sys.modules["voluptuous"] = vol

    serial = types.ModuleType("serial")
    class _Serial: pass
    serial.Serial = _Serial
    sys.modules.setdefault("serial", serial)


_install_ha_stubs()

import dlogg.config_flow as cf  # noqa: E402
from dlogg.const import (  # noqa: E402
    CONF_CHANNEL_NAME,
    CONF_CHANNEL_TYPE,
    TYPE_DISABLED,
    TYPE_TEMPERATURE,
)


def _schema_fields(schema) -> dict:
    """Return {field_key: default} from a (stub or real) voluptuous schema."""
    fields = {}
    for key, _validator in schema.schema.items():
        field = getattr(key, "key", None) or getattr(key, "schema", key)
        fields[field] = getattr(key, "default", None)
    return fields


CHANNEL_KINDS = {
    "C1_S1": "temp",
    "C1_S2": "temp",
    "C1_S3": "unused",
    "C1_A1": "digital",
    "C1_A2": "digital",
    "C2_S1": "temp",
    "C2_A1": "digital",
}


class TestChannelHelpers(unittest.TestCase):
    """Pure helpers of the config flow."""

    def test_extract_channels_defaults_to_disabled(self):
        user_input = {
            "name_C1_S1": "Collector",
            "type_C1_S1": TYPE_TEMPERATURE,
            # C1_S2 submitted without a type -> must fall back to disabled
            "name_C1_S2": "C1_S2",
        }
        channels = cf._extract_channels(user_input, CHANNEL_KINDS)
        self.assertEqual(channels["C1_S1"][CONF_CHANNEL_TYPE], TYPE_TEMPERATURE)
        self.assertEqual(channels["C1_S1"][CONF_CHANNEL_NAME], "Collector")
        self.assertEqual(channels["C1_S2"][CONF_CHANNEL_TYPE], TYPE_DISABLED)
        self.assertEqual(channels["C1_A1"][CONF_CHANNEL_TYPE], TYPE_DISABLED)
        self.assertEqual(set(channels), set(CHANNEL_KINDS))

    def test_channel_schema_lists_all_channels_with_disabled_default(self):
        schema = cf._channel_schema(CHANNEL_KINDS)
        fields = _schema_fields(schema)
        for channel in CHANNEL_KINDS:
            self.assertIn(f"name_{channel}", fields)
            self.assertEqual(fields[f"type_{channel}"], TYPE_DISABLED)
        # pre-filled default names come from DEFAULT_CHANNEL_NAMES
        self.assertEqual(fields["name_C1_S1"], "Outdoor temperature")
        self.assertEqual(fields["name_C1_A1"], "WE1 charging pump")
        self.assertEqual(fields["name_C2_S1"], "C2_S1")  # no preset -> channel id


class TestChannelsStep(unittest.TestCase):
    """The 'channels' step of the config flow must render and create an entry."""

    def _make_flow(self):
        flow = cf.DLoggConfigFlow()
        flow._port = "/dev/ttyUSB0"
        flow._baudrate = 115200
        flow._scan_interval = 30
        flow._channel_kinds = dict(CHANNEL_KINDS)
        return flow

    def test_channels_step_shows_form(self):
        flow = self._make_flow()
        result = asyncio.run(flow.async_step_channels(None))
        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "channels")
        fields = _schema_fields(result["data_schema"])
        self.assertEqual(len([f for f in fields if f.startswith("type_")]), len(CHANNEL_KINDS))

    def test_channels_step_shows_warning_on_error(self):
        # Broken internal state must surface as a form warning, not a crash
        flow = self._make_flow()
        flow._channel_kinds = None
        result = asyncio.run(flow.async_step_channels(None))
        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"], {"base": "unknown"})
        self.assertIn("error", result["description_placeholders"])

    def test_channels_step_submit_creates_entry(self):
        flow = self._make_flow()
        user_input = {
            f"name_{ch}": ch for ch in CHANNEL_KINDS
        } | {f"type_{ch}": TYPE_DISABLED for ch in CHANNEL_KINDS}
        user_input["type_C1_S1"] = TYPE_TEMPERATURE
        result = asyncio.run(flow.async_step_channels(user_input))
        self.assertEqual(result["type"], "create_entry")
        channels = result["data"]["channels"]
        self.assertEqual(channels["C1_S1"][CONF_CHANNEL_TYPE], TYPE_TEMPERATURE)
        self.assertTrue(all(
            c[CONF_CHANNEL_TYPE] == TYPE_DISABLED for ch, c in channels.items() if ch != "C1_S1"
        ))


class TestOptionsFlow(unittest.TestCase):
    """Regression tests: the options dialog ('Konfigurieren') must not crash."""

    def _make_entry(self):
        return SimpleNamespace(
            data={"channels": {ch: {"name": ch, "type": TYPE_DISABLED} for ch in CHANNEL_KINDS}},
            options={},
        )

    def test_options_init_shows_form_without_nameerror(self):
        flow = cf.DLoggOptionsFlow()
        flow.config_entry = self._make_entry()
        result = asyncio.run(flow.async_step_init(None))
        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "init")
        fields = _schema_fields(result["data_schema"])
        for channel in CHANNEL_KINDS:
            self.assertIn(f"name_{channel}", fields)
            self.assertIn(f"type_{channel}", fields)
            self.assertEqual(fields[f"type_{channel}"], TYPE_DISABLED)

    def test_options_init_keeps_saved_names(self):
        entry = self._make_entry()
        entry.options = {"channels": {"C1_S1": {"name": "Collector", "type": TYPE_TEMPERATURE}}}
        flow = cf.DLoggOptionsFlow()
        flow.config_entry = entry
        result = asyncio.run(flow.async_step_init(None))
        fields = _schema_fields(result["data_schema"])
        self.assertEqual(fields["name_C1_S1"], "Collector")
        self.assertEqual(fields["type_C1_S1"], TYPE_TEMPERATURE)

    def test_options_init_shows_warning_on_error(self):
        # Regression: the options dialog crashed with NameError before; now the
        # exception must appear as a warning inside the dialog.
        flow = cf.DLoggOptionsFlow()
        flow.config_entry = SimpleNamespace(data={"channels": None}, options={})
        result = asyncio.run(flow.async_step_init(None))
        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "init")
        self.assertEqual(result["errors"], {"base": "unknown"})
        self.assertTrue(result["description_placeholders"]["error"])

    def test_options_submit_updates_channels(self):
        flow = cf.DLoggOptionsFlow()
        flow.config_entry = self._make_entry()
        user_input = {"scan_interval": 60}
        user_input.update({f"name_{ch}": ch for ch in CHANNEL_KINDS})
        user_input.update({f"type_{ch}": TYPE_DISABLED for ch in CHANNEL_KINDS})
        user_input["type_C2_A1"] = "switch"
        result = asyncio.run(flow.async_step_init(user_input))
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"]["scan_interval"], 60)
        self.assertEqual(result["data"]["channels"]["C2_A1"][CONF_CHANNEL_TYPE], "switch")
        self.assertEqual(result["data"]["channels"]["C1_S1"][CONF_CHANNEL_TYPE], TYPE_DISABLED)


if __name__ == "__main__":
    unittest.main()
