"""Client for the Technische Alternative D-LOGG USB data logger.

The D-LOGG sits on the DL-Bus of a RESOL controller (e.g. UVR1611) and
exposes the current sensor and output values over a serial USB interface.
All methods are blocking and must be called from an executor.
"""

from __future__ import annotations

import math
import time
from typing import Any

try:
    import serial
except ImportError:
    # pyserial may be missing (e.g. failed requirement install). Keep the
    # module importable so the config flow still loads; the error is raised
    # when the port is actually opened.
    serial = None

# Protocol constants (DL-Bus / D-LOGG)
CMD_MODE = 0x81  # Query logger mode
CMD_CURRENT = 0xAB  # Request the current data frame
TYPE_UVR1611 = 0x80  # Device type byte of a UVR1611
MODE_1DL = 0xA8  # Logger in 1DL mode (57 byte frames)
MODE_2DL = 0xD1  # Logger in 2DL mode (113 byte frames)

# Sensor value kinds encoded in bits 4..6 of the high byte
KIND_UNUSED = "unused"
KIND_DIGITAL = "digital"
KIND_TEMP = "temp"
KIND_FLOW = "flow"
KIND_RADIATION = "radiation"
KIND_UNKNOWN = "unknown"


def decode_sensor_value(low: int, high: int) -> tuple[str, float]:
    """Decode one 2-byte sensor channel of a UVR1611 data block."""
    etype = (high >> 4) & 0b111
    raw12 = ((high & 0x0F) << 8) | low
    sign = (high & 0x80) != 0

    if etype == 0b000:
        return (KIND_UNUSED, math.nan)
    if etype == 0b001:
        # Digital level (off/on)
        return (KIND_DIGITAL, 1.0 if raw12 else 0.0)
    if etype == 0b010:
        # Temperature in 1/10 °C, 12-bit two's complement when negative
        value = -(((~raw12) & 0x0FFF) + 1) if sign else raw12
        return (KIND_TEMP, value / 10.0)
    if etype == 0b011:
        # Volume flow in steps of 4 l/h
        return (KIND_FLOW, raw12 * 4.0)
    if etype == 0b110:
        # Solar radiation in W/m²
        return (KIND_RADIATION, float(raw12))
    if etype == 0b111:
        # Room temperature special case: lowest high-byte bit adds 256/10
        if (high & 0x01) != 0:
            return (KIND_TEMP, (256 + low) / 10.0)
        return (KIND_TEMP, low / 10.0)
    return (KIND_UNKNOWN, math.nan)


def _parse_uvr1611_block(data: bytes, index: int) -> dict[str, Any]:
    """Parse the 55 data bytes of one UVR1611 block.

    Sensors T1..T16 (2 bytes each), outputs A1..A16 (bit masks in the
    two bytes after the sensor block). The index identifies the controller
    inside a 2DL frame (1 = C1, 2 = C2).
    """
    sensors: dict[str, dict[str, Any]] = {}
    for sensor_index in range(16):
        low = data[2 * sensor_index]
        high = data[2 * sensor_index + 1]
        kind, value = decode_sensor_value(low, high)
        sensors[f"T{sensor_index + 1}"] = {"kind": kind, "value": value}

    outputs: dict[str, int] = {}
    for bit in range(8):
        outputs[f"A{bit + 1}"] = (data[32] >> bit) & 1
    for bit in range(8):
        outputs[f"A{bit + 9}"] = (data[33] >> bit) & 1

    return {"index": index, "sensors": sensors, "outputs": outputs}


def parse_current_frame(buf: bytes) -> list[dict[str, Any]]:
    """Parse a raw current-data frame (1DL = 57 bytes, 2DL = 113 bytes)."""
    devices: list[dict[str, Any]] = []
    if len(buf) == 57 and buf[0] == TYPE_UVR1611:
        devices.append(_parse_uvr1611_block(buf[1:56], 1))
    elif len(buf) == 113:
        # 2DL frame: two device blocks of [type][55 data bytes]
        for block, offset in enumerate((0, 56), start=1):
            if buf[offset] == TYPE_UVR1611:
                try:
                    devices.append(_parse_uvr1611_block(buf[offset + 1 : offset + 56], block))
                except IndexError:
                    continue
    return devices


class DLoggClient:
    """Blocking serial client for the D-LOGG."""

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 2.0) -> None:
        """Initialize the client with the serial port and baud rate."""
        self._port = port
        self._baudrate = baudrate
        self._timeout = timeout

    def _open(self) -> "serial.Serial":
        if serial is None:
            raise RuntimeError("pyserial is not installed")
        return serial.Serial(port=self._port, baudrate=self._baudrate, timeout=self._timeout)

    def query_mode(self, ser: serial.Serial) -> int:
        """Ask the logger for its mode (1DL or 2DL)."""
        ser.reset_input_buffer()
        ser.write(bytes([CMD_MODE]))
        response = ser.read(1)
        if len(response) != 1:
            raise RuntimeError("No answer to mode query")
        return response[0]

    def request_current(self, ser: serial.Serial) -> bytes:
        """Request one current-data frame (57 or 113 bytes)."""
        ser.reset_input_buffer()
        ser.write(bytes([CMD_CURRENT]))
        time.sleep(0.05)
        buf = ser.read(200)
        if len(buf) in (57, 113):
            return buf
        # The D-LOGG occasionally sends the frame in two chunks
        buf += ser.read(200)
        if len(buf) >= 113:
            return buf[:113]
        if len(buf) >= 57:
            return buf[:57]
        raise RuntimeError(f"Invalid response frame (len={len(buf)})")

    def read(self) -> dict[str, Any]:
        """Read one snapshot and merge all devices into a single dict."""
        with self._open() as ser:
            self.query_mode(ser)
            frame = self.request_current(ser)
        devices = parse_current_frame(frame)
        if not devices:
            raise RuntimeError("No supported device found in frame")

        merged: dict[str, Any] = {"sensors": {}, "outputs": {}}
        for device in devices:
            prefix = f"C{device['index']}_"
            for channel, sensor in device["sensors"].items():
                merged["sensors"][prefix + channel] = sensor
            for channel, state in device["outputs"].items():
                merged["outputs"][prefix + channel] = state
        return merged


def detect_channels(port: str, baudrate: int = 115200) -> dict[str, str]:
    """Connect once and return the usable channels as {channel_id: kind}."""
    client = DLoggClient(port, baudrate)
    data = client.read()
    channels = {
        channel: sensor["kind"]
        for channel, sensor in data["sensors"].items()
        if sensor["kind"] != KIND_UNUSED
    }
    # Outputs A1..A16 are digital states
    channels.update({channel: KIND_DIGITAL for channel in data["outputs"]})
    return channels
