"""
Configuration and constants for the Gesture-Controlled Snake Game.
"""
import os

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HIGHSCORE_FILE = os.path.join(BASE_DIR, "highscore.json")
HAND_LANDMARKER_MODEL = os.path.join(BASE_DIR, "hand_landmarker.task")

# Window Dimensions (Split-Screen UI: Left = Game Board, Right = Webcam & HUD)
WINDOW_WIDTH = 1120
WINDOW_HEIGHT = 720
FPS = 60

# Game Board Dimensions
BOARD_X = 30
BOARD_Y = 80
BOARD_WIDTH = 640
BOARD_HEIGHT = 600
GRID_SIZE = 20
GRID_COLS = BOARD_WIDTH // GRID_SIZE   # 32 columns
GRID_ROWS = BOARD_HEIGHT // GRID_SIZE  # 30 rows

# Side Panel (Webcam + Gesture HUD + Scoreboard)
PANEL_X = BOARD_X + BOARD_WIDTH + 25   # 695
PANEL_Y = 30
PANEL_WIDTH = WINDOW_WIDTH - PANEL_X - 25  # 400
PANEL_HEIGHT = WINDOW_HEIGHT - 60

# Webcam Preview Size inside Side Panel
CAM_WIDTH = 360
CAM_HEIGHT = 270

# Difficulty Settings (Snake moves per second)
DIFFICULTY_LEVELS = {
    "EASY": {
        "label": "Easy",
        "speed": 6.5,       # Grid cells per second
        "score_mult": 10,
        "color": (46, 213, 115),
    },
    "MEDIUM": {
        "label": "Medium",
        "speed": 9.5,
        "score_mult": 15,
        "color": (255, 165, 2),
    },
    "HARD": {
        "label": "Hard",
        "speed": 13.5,
        "score_mult": 25,
        "color": (255, 71, 87),
    },
}

DEFAULT_DIFFICULTY = "MEDIUM"

# Modern Dark Cyberpunk / Neon Theme Colors (R, G, B)
COLOR_BG = (13, 17, 23)              # Deep dark blue-black
COLOR_BOARD_BG = (20, 26, 36)        # Slightly lighter board background
COLOR_GRID_LINE = (28, 36, 48)       # Subtle grid lines
COLOR_PANEL_BG = (22, 29, 41)        # Card/panel background
COLOR_PANEL_BORDER = (48, 62, 85)    # Subtle border

# Snake Colors
COLOR_SNAKE_HEAD = (0, 245, 212)     # Bright Cyan-Mint
COLOR_SNAKE_BODY = (0, 187, 158)     # Teal body
COLOR_SNAKE_TAIL = (0, 125, 115)     # Darker teal tail
COLOR_SNAKE_OUTLINE = (10, 40, 45)

# Food Colors
COLOR_FOOD = (255, 71, 87)           # Vibrant Coral Red
COLOR_FOOD_GLOW = (255, 120, 135)
COLOR_GOLDEN_FOOD = (255, 215, 0)    # Bonus food

# UI Accent & Text Colors
COLOR_TEXT_PRIMARY = (240, 246, 252)
COLOR_TEXT_SECONDARY = (139, 148, 158)
COLOR_ACCENT = (88, 166, 255)        # Electric Blue
COLOR_SUCCESS = (46, 213, 115)       # Neon Green
COLOR_WARNING = (255, 165, 2)        # Amber
COLOR_DANGER = (255, 71, 87)         # Crimson

# Gesture Constants
GESTURE_NONE = "NONE"
GESTURE_UP = "UP"
GESTURE_DOWN = "DOWN"
GESTURE_LEFT = "LEFT"
GESTURE_RIGHT = "RIGHT"
GESTURE_TWO_PALMS = "TWO_PALMS"
GESTURE_OPEN_PALM = "OPEN_PALM"

# Direction Vectors
DIR_UP = (0, -1)
DIR_DOWN = (0, 1)
DIR_LEFT = (-1, 0)
DIR_RIGHT = (1, 0)

OPPOSITE_DIRECTIONS = {
    DIR_UP: DIR_DOWN,
    DIR_DOWN: DIR_UP,
    DIR_LEFT: DIR_RIGHT,
    DIR_RIGHT: DIR_LEFT,
}

GESTURE_TO_DIR = {
    GESTURE_UP: DIR_UP,
    GESTURE_DOWN: DIR_DOWN,
    GESTURE_LEFT: DIR_LEFT,
    GESTURE_RIGHT: DIR_RIGHT,
}

# Hand Tracking & Calibration Settings
NEUTRAL_ZONE_RADIUS = 0.075          # Smaller deadzone for quicker response
SWIPE_DELTA_THRESHOLD = 0.042        # Instant directional turn when hand moves by this delta
TWO_PALMS_COOLDOWN_SEC = 0.9         # Cooldown between 2-hand open palm pause/resume toggles
TWO_PALMS_HOLD_SEC = 0.15            # Brief hold time to confirm 2 open palms
PALM_HOLD_SEC = 0.35                 # Hold time for open palm action to start/restart

