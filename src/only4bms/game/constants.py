import pygame

# ── Judgment configuration (single source of truth) ──────────────────────
JUDGMENT_DEFS = {
    "PERFECT": {"threshold_ms": 40,  "color": (0, 255, 255), "display": "PERFECT!"},
    "GREAT":   {"threshold_ms": 100, "color": (0, 255, 0),   "display": "GREAT!"},
    "GOOD":    {"threshold_ms": 200, "color": (255, 255, 0),  "display": "GOOD"},
    "MISS":    {"threshold_ms": 200, "color": (255, 0, 0),    "display": "MISS"},
}
JUDGMENT_ORDER = ["PERFECT", "GREAT", "GOOD", "MISS"]

# ── Base (windowed) resolution ────────────────────────────────────────────
BASE_W, BASE_H = 800, 600
NUM_LANES = 4
LANE_W = 75
NOTE_H = 20
HIT_Y = 500
BG_COLOR = (20, 20, 20)
LANE_BG_ALPHA = 200
JUDGMENT_DISPLAY_MS = 500
SONG_END_PADDING_MS = 2000
EFFECT_EXPAND_SPEED = 2
EFFECT_FADE_SPEED = 15

# Hit zone pulse
HIT_ZONE_VISUAL_H = 30     # PERFECT zone visual height (px, before hw_mult)
GREAT_ZONE_VISUAL_H = 60   # GREAT zone visual height (px, before hw_mult)
HIT_ZONE_PULSE_PERIOD = 300.0
HIT_ZONE_ALPHA_MIN = 20
HIT_ZONE_ALPHA_RANGE = 50

# Loading screen
LOADING_BAR_W, LOADING_BAR_H = 500, 16

# Video extensions
VIDEO_EXTS = {'.mpg', '.mpeg', '.mp4', '.avi', '.wmv', '.mkv', '.webm'}
IMAGE_FALLBACK_EXTS = ['.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.bmp', '.BMP']

# ── Difficulty badge definitions ───────────────────────────────────────────
# Each entry: label (short), file keywords that map to it, badge bg color.
# To add a new difficulty tier, append an entry here — no other file changes needed.
DIFFICULTY_DEFS = [
    {"label": "BEG", "keywords": ["beginner", "7b", "5b"], "color": (130, 200, 130)},
    {"label": "NOR", "keywords": ["normal",   "7n", "5n"], "color": (100, 150, 255)},
    {"label": "HYP", "keywords": ["hyper",    "7h", "5h"], "color": (255, 200, 100)},
    {"label": "ANO", "keywords": ["another",  "7a", "5a"], "color": (255, 100, 100)},
    {"label": "INS", "keywords": ["insane",   "7i"],        "color": (200,  80, 255)},
]
DIFFICULTY_DEFAULT_COLOR = (60, 60, 80)

# ── Note type definitions ──────────────────────────────────────────────────
# Index corresponds to the integer stored in settings['note_type'].
# To add a new note shape, append its display name here and handle rendering
# in renderer._blit_note_head().
NOTE_TYPE_NAMES = ["Bar", "Circle"]
