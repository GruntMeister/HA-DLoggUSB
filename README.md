# D-LOGG USB — Home Assistant Integration

Home Assistant custom integration for the **Technische Alternative D-LOGG**
USB data logger (e.g. with a RESOL UVR1611 solar thermal controller).
It reads the current values over the DL-Bus via the serial USB interface.

## Features

- UI config flow: serial port, baud rate and polling interval
- **Freely configurable channel names**: every detected channel (T1–T16, A1–A13)
  gets a custom name and one of three value types in the UI:
  - **Temperature** (°C sensor)
  - **Power** (W sensor)
  - **Switch** (read-only switch mirroring a digital channel/output)
- Names and types can be changed later via the integration options
- Local polling, no cloud

## Installation

### HACS (recommended)

1. Add this repository as a **custom repository** (type: Integration) in HACS.
2. Install **D-LOGG USB** and restart Home Assistant.

### Manual

1. Copy `custom_components/dlogg/` into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.

## Setup

1. Go to **Settings → Devices & Services → Add Integration** and search for
   **D-LOGG USB**.
2. Enter the serial port of the D-LOGG USB adapter
   (Linux: e.g. `/dev/ttyUSB0`, Windows: e.g. `COM4`), the baud rate
   (default 115200) and the polling interval in seconds.
3. The integration detects the available channels. Assign each channel a
   **name** (e.g. "Hot water") and a **type** (Temperature / Power / Switch).
4. The channels appear as sensors/switches under a "D-LOGG" device.

## Notes

- The D-LOGG protocol is read-only, so switch entities reflect the current
  output state and cannot be toggled from Home Assistant.
- Requires `pyserial` (installed automatically via the manifest).

## Tests

Unit tests for the protocol parser live in `tests/`. They run with the
standard library only:

```bash
python3 -m unittest discover -s tests -v
```

To additionally cross-check the parser against the reference implementation
(D-LOGG-Dashboard-Solarthermie `app.py`) on raw data packets, set
`DLOGG_REFERENCE_APP` to the reference file:

```bash
DLOGG_REFERENCE_APP=/path/to/D-LOGG-Dashboard-Solarthermie/app.py \
    python3 -m unittest discover -s tests -v
```
