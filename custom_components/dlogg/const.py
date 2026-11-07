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
