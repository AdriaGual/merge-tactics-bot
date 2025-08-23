"""
Constants and configuration values for the Merge Tactics bot.
Centralizes all magic numbers and configuration parameters.
"""

# Debug settings
DEBUG_MODE = False
DEBUG_SAVE_IMAGES = False

# Image processing settings
THRESHOLD = 0.8
MIN_DISTANCE = 40
ELIXIR_CACHE_DURATION = 1.0

# GUI settings
IMG_SIZE = (60, 60)
MARGIN = 20
COLS = 5
LOG_HEIGHT = 200
INFO_PANEL_WIDTH = 300
BUTTONS_OFFSET = 400

# Bot timing settings
BOT_LOOP_DELAY = 0.5
ERROR_DELAY = 0.2
ACTION_DELAY = 0.1
BATTLE_WAIT = 0.5
PURCHASE_DELAY = 0.4
OPTIMIZATION_DELAY = 0.5

# Template matching thresholds
ELIXIR_MATCH_THRESHOLD = -0.7
BENCH_EMPTY_THRESHOLD = 0.13

# Purchase limits
MAX_PURCHASE_ATTEMPTS = 4
MAX_CHEAP_UNIT_COST = 5
MIN_ELIXIR_FOR_CHEAP_UNITS = 3

# Logging settings
MAX_LOG_ENTRIES = 20

# Cache settings
POSITION_CACHE_SIZE = 1000  # Maximum entries in position cache
