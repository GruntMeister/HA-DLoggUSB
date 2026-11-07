# D-LOGG USB — Home Assistant Integration

Home Assistant custom integration for the **Technische Alternative D-LOGG**
USB data logger (e.g. with a RESOL UVR1611 solar thermal controller).
It reads the current values over the DL-Bus via the serial USB interface.

## Features

- UI config flow: serial port, baud rate and polling interval
- **Freely configurable channel names**: every detected channel
  (`C1_T1..C1_T16`, `C1_A1..C1_A16`, `C2_…` for a second controller in 2DL mode)
  gets a custom name and one of three value types in the UI:
  - **Temperature** (°C sensor)
  - **Power** (W sensor)
  - **Switch** (read-only binary sensor mirroring a digital channel/output —
    the D-LOGG cannot be toggled, so it is not shown as an interactive slider)
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
   (Linux: e.g. `/dev/ttyUSB0`), the baud rate
   (default 115200) and the polling interval in seconds.
3. The integration detects the available channels. Assign each channel a
   **name** and a **type** (Temperature / Power / Switch).
4. The channels appear as sensors/switches under a "D-LOGG" device.

## Two controllers (2DL mode)

In 2DL mode the D-LOGG returns two controller blocks. Channels are namespaced
per controller: `C1_T1..C1_T16` / `C1_A1..C1_A16` for the first controller and
`C2_T1..C2_T16` / `C2_A1..C2_A16` for the second (sensors T1–T16, outputs
A1–A16 including the PWM outputs). A set of sensible default names for a
two-controller solar setup is pre-filled and can be changed freely in the
config flow or later via the integration options.

## Notes

- The D-LOGG protocol is read-only, so "switch" channels are exposed as
  binary sensors showing the current output state; they cannot be toggled
  from Home Assistant.
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
