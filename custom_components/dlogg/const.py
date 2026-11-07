"""Constants for the D-LOGG USB integration."""

DOMAIN = "dlogg"

# Config keys defined locally: some CONF_* constants were removed from
# homeassistant.const in newer HA versions (e.g. CONF_BAUDRATE).
CONF_PORT = "port"
CONF_BAUDRATE = "baudrate"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUDRATE = 115200
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 3600

CONF_CHANNELS = "channels"
CONF_CHANNEL_NAME = "name"
CONF_CHANNEL_TYPE = "type"

TYPE_TEMPERATURE = "temperature"
TYPE_POWER = "power"
TYPE_SWITCH = "switch"
CHANNEL_TYPES = [TYPE_TEMPERATURE, TYPE_POWER, TYPE_SWITCH]

# Pre-filled channel names for a 2DL setup with two controllers (C1, C2).
# Channel ids are namespaced per controller: C1_T1..C1_T16, C1_A1..C1_A16,
# C2_T1..C2_T16, C2_A1..C2_A16. Names can be changed freely in the UI.
DEFAULT_CHANNEL_NAMES: dict[str, str] = {
    # Controller C1 - inputs
    "C1_T1": "Outdoor temperature",
    "C1_T2": "Tank 1 coupling",
    "C1_T3": "Tank 1 top",
    "C1_T4": "Tank 1 reserve 1",
    "C1_T5": "Tank 1 reserve 2",
    "C1_T6": "Tank 1 charging line",
    "C1_T7": "WE1 operating temperature",
    "C1_T8": "WA1 room temperature",
    "C1_T9": "WE1 return temperature",
    "C1_T10": "WA1 flow temperature",
    "C1_T11": "WA1 return temperature",
    "C1_T12": "SOL solar tank temperature",
    "C1_T13": "SOL solar irradiation",
    "C1_T14": "Reserve",
    "C1_T15": "Reserve",
    "C1_T16": "Reserve",
    # Controller C1 - outputs
    "C1_A1": "WE1 charging pump",
    "C1_A2": "SOL primary pump",
    "C1_A3": "SOL enable valve",
    "C1_A4": "WE1 enable",
    "C1_A5": "WA1 heating pump",
    "C1_A6": "SOL secondary circuit pump",
    "C1_A7": "WE1 mixer open",
    "C1_A8": "WE1 mixer close",
    "C1_A9": "WA1 mixer open",
    "C1_A10": "WA1 mixer close",
    "C1_A13": "P1 - PWM WE1 charging pump",
    "C1_A14": "P2 - PWM WA1 heating pump",
    # Controller C2 - inputs (a UVR1611 block provides T1..T16 per controller)
    "C2_T14": "WE2 operating temperature",
    "C2_T15": "WA2 room temperature",
    "C2_T16": "WE2 return temperature",
    # Controller C2 - outputs
    "C2_A1": "WE2 charging pump",
    "C2_A3": "WE2 charging pump (2)",
    "C2_A5": "WA2 heating pump",
    "C2_A7": "WE2 mixer open",
    "C2_A8": "WE2 mixer close",
    "C2_A9": "WA2 mixer open",
    "C2_A10": "WA2 mixer close",
    "C2_A15": "P5 - PWM WE2 charging pump",
    "C2_A16": "P6 - PWM WA2 heating pump",
}
