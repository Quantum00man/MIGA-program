from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
APP_DIR = BASE_DIR / "app"
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"

STATE_FILE_PATH = DATA_DIR / "controller_state.json"

APP_TITLE = "MIGA Hardware Controller"
APP_VERSION = "1.0.0"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8050

SESSION_COOKIE_NAME = "hardware_controller_session"
SESSION_TTL_SEC = 12 * 60 * 60
PASSWORD_ITERATIONS = 200_000
DEFAULT_PASSWORD = "miga"

NETWORK_TIMEOUT_SEC = 3.0
EDFA_DEFAULT_PORT = 23
EDFA_COMMAND_DELAY_SEC = 1.0
EDFA_CHANNEL_KEYS = ("edfa0", "edfa1", "edfa2", "edfa3")
EDFA_DEFAULT_POWERS = {
    "edfa0": "3",
    "edfa1": "2.4",
    "edfa2": "3",
    "edfa3": "3",
}

PSU_DEFAULT_PORT = 9221
PSU_CHANNELS = ("1", "2")

LASER_LOCK_DEFAULT_PORT = 23
LASER_LOCK_OUTPUT_LINES = 120

WEEKDAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
DEFAULT_WEEKDAYS = [0, 1, 2, 3, 4]

SCHEDULER_INTERVAL_SEC = 1.0
MAX_EVENT_LOG = 300

LATEX_MANUAL_PATH = DOCS_DIR / "hardware_controller_manual.tex"
