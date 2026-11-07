"""Unit tests for the D-LOGG protocol client (custom_components/dlogg/dlogg.py).

The tests use raw serial data packets and cross-check the parser against the
reference implementation (D-LOGG-Dashboard-Solarthermie app.py). Point the
environment variable DLOGG_REFERENCE_APP to the reference app.py to enable
the cross-check tests; without it they are skipped and only the golden-value
tests run.

Run from the repository root:
    DLOGG_REFERENCE_APP=/path/to/reference/app.py python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import importlib.util
import math
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
DLOGG_PATH = REPO_ROOT / "custom_components" / "dlogg" / "dlogg.py"
REFERENCE_APP_PATH = os.environ.get("DLOGG_REFERENCE_APP", "")


def _ensure_serial_stub() -> None:
    """Provide a serial module stub when pyserial is not installed."""
    try:
        import serial  # noqa: F401
    except ImportError:
        stub = types.ModuleType("serial")

        class _Serial:  # pragma: no cover - placeholder
            pass

        stub.Serial = _Serial
        sys.modules["serial"] = stub


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_ensure_serial_stub()
dlogg = _load_module("dlogg_under_test", DLOGG_PATH)


def load_reference():
    """Load the reference app.py with flask/serial stubbed out."""
    if not REFERENCE_APP_PATH or not Path(REFERENCE_APP_PATH).is_file():
        return None
    flask = types.ModuleType("flask")

    class _Flask:
        def __init__(self, *args, **kwargs):
            pass

        def route(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    flask.Flask = _Flask
    flask.jsonify = lambda *args, **kwargs: None
    flask.render_template = lambda *args, **kwargs: None
    sys.modules.setdefault("flask", flask)
    _ensure_serial_stub()
    return _load_module("reference_app", Path(REFERENCE_APP_PATH))


# ---------------------------------------------------------------------------
# Helpers to craft raw UVR1611 data packets
# ---------------------------------------------------------------------------


def _set_raw(data: bytearray, index: int, low: int, high: int) -> None:
    data[2 * index] = low
    data[2 * index + 1] = high


def set_temp(data: bytearray, index: int, deci_celsius: int) -> None:
    """Encode a temperature channel (1/10 °C, 12-bit two's complement)."""
    raw = deci_celsius & 0xFFF
    high = ((raw >> 8) & 0x0F) | (0b010 << 4)
    if deci_celsius < 0:
        high |= 0x80
    _set_raw(data, index, raw & 0xFF, high)


def set_digital(data: bytearray, index: int, on: bool) -> None:
    _set_raw(data, index, 1 if on else 0, 0b001 << 4)


def set_flow(data: bytearray, index: int, raw12: int) -> None:
    high = ((raw12 >> 8) & 0x0F) | (0b011 << 4)
    _set_raw(data, index, raw12 & 0xFF, high)


def set_radiation(data: bytearray, index: int, raw12: int) -> None:
    high = ((raw12 >> 8) & 0x0F) | (0b110 << 4)
    _set_raw(data, index, raw12 & 0xFF, high)


def set_room_temp(data: bytearray, index: int, low: int, plus256: bool) -> None:
    high = (0b111 << 4) | (0x01 if plus256 else 0x00)
    _set_raw(data, index, low, high)


def make_block(
    temps: dict[int, int] | None = None,
    digitals: dict[int, bool] | None = None,
    flows: dict[int, int] | None = None,
    radiation: dict[int, int] | None = None,
    room_temps: dict[int, tuple[int, bool]] | None = None,
    outputs_byte1: int = 0,
    outputs_byte2: int = 0,
) -> bytes:
    """Build one 55-byte UVR1611 data block."""
    data = bytearray(55)
    for index, value in (temps or {}).items():
        set_temp(data, index, value)
    for index, on in (digitals or {}).items():
        set_digital(data, index, on)
    for index, raw in (flows or {}).items():
        set_flow(data, index, raw)
    for index, raw in (radiation or {}).items():
        set_radiation(data, index, raw)
    for index, (low, plus256) in (room_temps or {}).items():
        set_room_temp(data, index, low, plus256)
    data[32] = outputs_byte1
    data[33] = outputs_byte2
    return bytes(data)


def make_1dl_frame(block: bytes) -> bytes:
    """Wrap a block into a 57-byte 1DL frame (type + 55 data + checksum)."""
    return bytes([0x80]) + block + bytes([0x00])


def make_2dl_frame(block1: bytes, block2: bytes, type2: int = 0x80) -> bytes:
    """Wrap two blocks into a 113-byte 2DL frame."""
    return bytes([0x80]) + block1 + bytes([type2]) + block2 + bytes([0x00])


# A mixed packet exercising every sensor kind and the output bytes
MIXED_BLOCK = make_block(
    temps={0: 523, 1: -105, 15: 4095},  # T1=52.3, T2=-10.5, T16=409.5
    digitals={3: True, 4: False},  # T4 on, T5 off
    flows={5: 12},  # T6 = 48 l/h
    radiation={6: 350},  # T7 = 350 W/m²
    room_temps={7: (100, True), 8: (200, False)},  # T8=35.6, T9=20.0
    outputs_byte1=0b10100001,  # A1, A6, A8 on
    outputs_byte2=0b00011,  # A9, A10 on
)
MIXED_FRAME_1DL = make_1dl_frame(MIXED_BLOCK)


def _mine_as_reference(device: dict) -> dict:
    """Convert my device dict into the reference shape ({temps, outputs}).

    The reference only parses outputs A1..A13, so A14..A16 are dropped for
    the comparison (they are covered by the golden tests).
    """
    temps = {
        channel: sensor["value"]
        for channel, sensor in device["sensors"].items()
        if sensor["kind"] == "temp"
    }
    outputs = {
        channel: state
        for channel, state in device["outputs"].items()
        if int(channel[1:]) <= 13
    }
    return {"temps": temps, "outputs": outputs}


class TestDecodeAgainstReference(unittest.TestCase):
    """Exhaustively compare decode_sensor_value with the reference decoder."""

    @classmethod
    def setUpClass(cls):
        cls.reference = load_reference()

    def test_all_byte_pairs_match_reference(self):
        if self.reference is None:
            self.skipTest("DLOGG_REFERENCE_APP not set")
        for high in range(256):
            for low in range(256):
                ref_kind, ref_value = self.reference._decode_sensor_value(low, high)
                kind, value = dlogg.decode_sensor_value(low, high)
                self.assertEqual(kind, ref_kind, f"kind mismatch low={low} high={high}")
                if math.isnan(ref_value):
                    self.assertTrue(math.isnan(value), f"expected NaN low={low} high={high}")
                else:
                    self.assertEqual(value, ref_value, f"value mismatch low={low} high={high}")


class TestParseFramesAgainstReference(unittest.TestCase):
    """Compare full frame parsing with the reference parser on data packets."""

    @classmethod
    def setUpClass(cls):
        cls.reference = load_reference()

    def _assert_frames_equal(self, frame: bytes):
        if self.reference is None:
            self.skipTest("DLOGG_REFERENCE_APP not set")
        ref_devices = self.reference.parse_current_frame(frame)
        my_devices = [_mine_as_reference(d) for d in dlogg.parse_current_frame(frame)]
        ref_cmp = [{"temps": d["temps"], "outputs": d["outputs"]} for d in ref_devices]
        self.assertEqual(my_devices, ref_cmp)

    def test_mixed_1dl_packet(self):
        self._assert_frames_equal(MIXED_FRAME_1DL)

    def test_2dl_two_uvr1611_packet(self):
        block2 = make_block(temps={0: 101, 2: -1}, outputs_byte1=0xFF)
        self._assert_frames_equal(make_2dl_frame(MIXED_BLOCK, block2))

    def test_2dl_with_uvr61_3_second_device(self):
        other = make_block(temps={0: 999})
        self._assert_frames_equal(make_2dl_frame(MIXED_BLOCK, other, type2=0x90))

    def test_garbage_frame_yields_no_devices(self):
        self._assert_frames_equal(b"\x01\x02\x03")


class TestGoldenValues(unittest.TestCase):
    """Known-answer tests for the mixed packet (independent of the reference)."""

    @classmethod
    def setUpClass(cls):
        devices = dlogg.parse_current_frame(MIXED_FRAME_1DL)
        assert len(devices) == 1
        cls.device = devices[0]

    def test_temperatures(self):
        sensors = self.device["sensors"]
        self.assertEqual(sensors["T1"]["value"], 52.3)
        self.assertEqual(sensors["T2"]["value"], -10.5)
        self.assertEqual(sensors["T16"]["value"], 409.5)
        self.assertEqual(sensors["T8"]["value"], 35.6)  # room temp +256 special case
        self.assertEqual(sensors["T9"]["value"], 20.0)  # room temp normal

    def test_kinds(self):
        sensors = self.device["sensors"]
        self.assertEqual(sensors["T3"]["kind"], "unused")
        self.assertEqual(sensors["T4"]["kind"], "digital")
        self.assertEqual(sensors["T4"]["value"], 1.0)
        self.assertEqual(sensors["T5"]["kind"], "digital")
        self.assertEqual(sensors["T5"]["value"], 0.0)
        self.assertEqual(sensors["T6"]["kind"], "flow")
        self.assertEqual(sensors["T6"]["value"], 48.0)
        self.assertEqual(sensors["T7"]["kind"], "radiation")
        self.assertEqual(sensors["T7"]["value"], 350.0)

    def test_outputs(self):
        outputs = self.device["outputs"]
        self.assertEqual(len(outputs), 16)
        for channel in ("A1", "A6", "A8", "A9", "A10"):
            self.assertEqual(outputs[channel], 1, channel)
        for channel in ("A2", "A3", "A4", "A5", "A7", "A11", "A12", "A13", "A14", "A15", "A16"):
            self.assertEqual(outputs[channel], 0, channel)

    def test_outputs_a14_to_a16_from_high_bits(self):
        block = make_block(outputs_byte2=0b11000000)  # bits 6,7 -> A15, A16
        device = dlogg.parse_current_frame(make_1dl_frame(block))[0]
        self.assertEqual(device["outputs"]["A15"], 1)
        self.assertEqual(device["outputs"]["A16"], 1)
        self.assertEqual(device["outputs"]["A14"], 0)

    def test_2dl_frame_has_two_devices(self):
        block2 = make_block(temps={0: 101})
        frame = make_2dl_frame(MIXED_BLOCK, block2)
        devices = dlogg.parse_current_frame(frame)
        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0]["index"], 1)
        self.assertEqual(devices[1]["index"], 2)
        self.assertEqual(devices[1]["sensors"]["T1"]["value"], 10.1)


class _FakeSerial:
    """Fake serial port replaying queued response chunks."""

    def __init__(self, port=None, baudrate=None, timeout=None):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.written: list[bytes] = []
        self.responses: list[bytes] = []
        self.closed = False

    def reset_input_buffer(self):
        pass

    def write(self, data: bytes):
        self.written.append(bytes(data))

    def read(self, size: int) -> bytes:
        if not self.responses:
            return b""
        chunk = self.responses.pop(0)
        return chunk[:size]

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class TestClient(unittest.TestCase):
    """Test DLoggClient.read and detect_channels with a fake serial port."""

    def _run_client(self, responses: list[bytes], func):
        fake = _FakeSerial()
        fake.responses = list(responses)
        with mock.patch.object(dlogg.serial, "Serial", lambda **kwargs: fake):
            return func(), fake

    def test_read_merges_frame(self):
        result, fake = self._run_client(
            [bytes([0xA8]), MIXED_FRAME_1DL],
            lambda: dlogg.DLoggClient("/dev/ttyUSB0", 115200).read(),
        )
        self.assertEqual(result["sensors"]["C1_T1"]["value"], 52.3)
        self.assertEqual(result["outputs"]["C1_A1"], 1)
        # Mode query then current-data request were sent
        self.assertEqual(fake.written, [bytes([0x81]), bytes([0xAB])])
        self.assertTrue(fake.closed)

    def test_read_handles_split_frame(self):
        # D-LOGG sometimes delivers the frame in two chunks
        split = [MIXED_FRAME_1DL[:30], MIXED_FRAME_1DL[30:]]
        result, _ = self._run_client(
            [bytes([0xD1])] + split,
            lambda: dlogg.DLoggClient("/dev/ttyUSB0").read(),
        )
        self.assertEqual(result["sensors"]["C1_T1"]["value"], 52.3)

    def test_read_2dl_prefixes_controllers(self):
        block2 = make_block(temps={0: 101}, outputs_byte1=0x01)
        frame = make_2dl_frame(MIXED_BLOCK, block2)
        result, _ = self._run_client(
            [bytes([0xD1]), frame],
            lambda: dlogg.DLoggClient("/dev/ttyUSB0").read(),
        )
        self.assertEqual(result["sensors"]["C1_T1"]["value"], 52.3)
        self.assertEqual(result["sensors"]["C2_T1"]["value"], 10.1)
        self.assertEqual(result["outputs"]["C2_A1"], 1)

    def test_read_rejects_invalid_frame(self):
        with self.assertRaises(RuntimeError):
            self._run_client(
                [bytes([0xA8]), b"\x80\x01\x02"],
                lambda: dlogg.DLoggClient("/dev/ttyUSB0").read(),
            )

    def test_detect_channels_returns_kinds(self):
        channels, _ = self._run_client(
            [bytes([0xA8]), MIXED_FRAME_1DL],
            lambda: dlogg.detect_channels("/dev/ttyUSB0", 115200),
        )
        self.assertEqual(channels["C1_T1"], "temp")
        self.assertEqual(channels["C1_T4"], "digital")
        self.assertEqual(channels["C1_T6"], "flow")
        self.assertEqual(channels["C1_T7"], "radiation")
        self.assertNotIn("C1_T3", channels)  # unused channels are not offered
        self.assertEqual(channels["C1_A1"], "digital")
        self.assertEqual(len([c for c in channels if "_A" in c]), 16)


class TestDefaultChannelNames(unittest.TestCase):
    """The pre-filled names for the two-controller setup must exist."""

    def test_controller_names_present(self):
        const = _load_module("dlogg_const_test", REPO_ROOT / "custom_components" / "dlogg" / "const.py")
        names = const.DEFAULT_CHANNEL_NAMES
        self.assertEqual(names["C1_T1"], "Outdoor temperature")
        self.assertEqual(names["C1_T13"], "SOL solar irradiation")
        self.assertEqual(names["C1_A1"], "WE1 charging pump")
        self.assertEqual(names["C1_A14"], "P2 - PWM WA1 heating pump")
        self.assertEqual(names["C2_T14"], "WE2 operating temperature")
        self.assertEqual(names["C2_A1"], "WE2 charging pump")
        self.assertEqual(names["C2_A16"], "P6 - PWM WA2 heating pump")


if __name__ == "__main__":
    unittest.main()
