# Only4BMS Mod Development Guide

This guide explains how to create a mod for **Only4BMS**.
Mods live in the `mods/` folder at the project root and are loaded automatically at startup.

---

## Quick Start

1. Create a folder inside `mods/` — the folder name becomes your mod's default ID.
2. Create `__init__.py` inside that folder with the required fields.
3. Launch Only4BMS — your mod's button will appear in the main menu.

```
mods/
└── my_mod/
    └── __init__.py      ← entry point; add sub-modules as needed
```

---

## `__init__.py` — Full Interface

```python
# ── Metadata (all optional, but recommended) ────────────────────────────────
MOD_ID          = "my_mod"                      # unique, no spaces
MOD_NAME        = "My Mod"                      # static fallback shown in menu
MOD_DESCRIPTION = "A short one-line description."
MOD_VERSION     = "1.0.0"                       # semver recommended


# ── Localised display name (optional) ───────────────────────────────────────
def get_display_name() -> str:
    """Return the menu label in the current language.
    Called every frame so the name stays live when the user switches language.
    If absent, MOD_NAME is used as a static fallback."""
    from .i18n import t as _t
    return _t("menu_my_mod")


# ── One-time setup (optional) ────────────────────────────────────────────────
def setup(ctx: dict) -> None:
    """Called once at startup, after the shared host context is ready.
    Use this to register challenges, i18n strings, or other one-time work.
    ctx contains the same keys as **ctx in run() — see below."""
    import only4bms.i18n as _i18n
    from only4bms.game.challenge import ChallengeManager

    # Register mod-local i18n strings into the host (for challenge menu etc.)
    from .i18n import _STRINGS
    for lang, strings in _STRINGS.items():
        _i18n.register_strings(lang, {k: v for k, v in strings.items()
                                      if k.startswith("ch_")})

    # Register mod challenges
    cm: ChallengeManager = ctx.get("challenge_manager")
    if cm:
        cm.register_challenges([
            {"id": "my_challenge", "condition": {"mode": "my_mode"}},
        ])


# ── Entry point (required) ───────────────────────────────────────────────────
def run(settings, renderer, window, **ctx):
    """Called when the player clicks your mod's menu button."""
    ...
```

> Only `run` is mandatory.

---

## `run()` Parameters

### `settings` — `dict`

The player's current settings. Read-only; do not persist changes without consent.

| Key | Type | Description |
|---|---|---|
| `fps` | int | Target frame rate |
| `speed` | float | Note scroll speed (0.1 – 5.0) |
| `volume` | float | Master volume (0.0 – 1.0) |
| `keys` | list[int] | pygame key codes for lanes D F J K |
| `joystick_keys` | list[str] | Joystick bindings |
| `fullscreen` | int | 1 = fullscreen |
| `language` | str/int | Current language |
| `hit_window_mult` | float | Judgment window multiplier |
| `judge_delay` | float | Extra input delay in ms |
| `note_type` | int | 0 = bar, 1 = circle |

### `renderer` — `pygame._sdl2.video.Renderer`

The shared SDL2 renderer.
Draw your scene to a `pygame.Surface`, convert it to a `Texture`, and blit it each frame:

```python
from pygame._sdl2.video import Texture

surf = pygame.Surface((w, h))
# ... draw to surf ...
tex = Texture.from_surface(renderer, surf)
renderer.clear()
renderer.blit(tex, pygame.Rect(0, 0, w, h))
renderer.present()
```

### `window` — `pygame._sdl2.video.Window`

The SDL2 window. Read `window.size` to get the current resolution.
You can call `window.set_fullscreen(True/False)` if your mod needs to switch modes.

### `**ctx` — host context

| Key | Type | Description |
|---|---|---|
| `init_mixer_fn` | `callable(settings)` | Re-initialise the audio mixer with current settings |
| `challenge_manager` | `ChallengeManager` | Shared challenge manager — register challenges in `setup()`, pass to `RhythmGame` for in-game tracking |

Always use `.get()` so your mod works even if a key is absent:

```python
init_mixer_fn     = ctx.get("init_mixer_fn")
challenge_manager = ctx.get("challenge_manager")
```

---

## Host APIs

Your mod runs in the same Python process as the game — host modules are directly importable.

### BMS Parser

```python
from only4bms.core.bms_parser import BMSParser

parser = BMSParser("/path/to/song.bms")
notes, bgms, bgas, bmp_map, visual_timing_map, measures = parser.parse()
# parser.title, parser.artist, parser.bpm, parser.playlevel, ...
```

### RhythmGame — core game engine

```python
from only4bms.game.rhythm_game import RhythmGame
from only4bms.game.game_extension import GameExtension  # optional

game = RhythmGame(
    notes, bgms, bgas, parser.wav_map, bmp_map,
    parser.title, settings,
    visual_timing_map=visual_timing_map,
    measures=measures,
    mode='single',            # 'single' | 'ai_multi' | 'online_multi'
    renderer=renderer,
    window=window,
    ai_difficulty='normal',   # 'normal' | 'hard'
    note_mod='None',          # 'None' | 'MIRROR' | 'RANDOM'
    challenge_manager=challenge_manager,
    extension=my_extension,   # GameExtension subclass, or None
)
result = game.run()           # returns dict with 'action', 'score', etc.
```

### GameExtension — in-game hooks

Subclass `GameExtension` to inject mod logic into the game loop without modifying `RhythmGame`.
Pass an instance as `extension=` when constructing `RhythmGame`.

```python
from only4bms.game.game_extension import GameExtension

class MyExtension(GameExtension):
    def attach(self, game) -> None:
        """Called at the end of RhythmGame.__init__.
        Store game reference and pre-load resources here."""
        super().attach(game)   # sets self._game = game
        w, h = game.window.size
        # load fonts, textures, etc.

    def on_judgment(self, key: str, lane: int, t_ms: float) -> None:
        """Called after every note judgment.
        key: 'PERFECT' | 'GREAT' | 'GOOD' | 'MISS'"""

    def on_tick(self, sim_time_ms: float) -> None:
        """Called once per render frame while the song is playing."""

    def should_abort(self) -> bool:
        """Return True to immediately end the song (transitions to RESULT).
        pygame.mixer.stop() is called automatically."""
        return False

    def draw_background(self, renderer, window) -> None:
        """Draw behind BGA / note field (called before draw_bga)."""

    def draw_overlay(self, renderer, window, game_state: dict, phase: str) -> None:
        """Draw on top of the entire game frame.
        phase: 'playing' | 'paused' | 'result'"""

    def get_extra_stats(self) -> dict:
        """Extra fields merged into RhythmGame.get_stats() and passed to
        challenge_manager.check_challenges()."""
        return {}
```

`game_state` dict passed to `draw_overlay`:

| Key | Type | Description |
|---|---|---|
| `lane_x` | list[int] | Left pixel edge of each lane |
| `lane_total_w` | int | Total width of the lane area |
| `judgments` | dict | `{PERFECT, GREAT, GOOD, MISS}` counts |
| `combo` | int | Current combo |
| `score` | int | Current score |
| `total_notes` | int | Total notes in chart |
| `mode` | str | Game mode string |

### ChallengeManager — achievements

```python
from only4bms.game.challenge import ChallengeManager

# Register mod challenges (call this in setup(), not in run())
cm.register_challenges([
    {"id": "my_clear", "condition": {"mode": "my_mode"}},
    {"id": "my_perfect", "hidden": True,
     "condition": {"mode": "my_mode", "require_all_perfect": True}},
])

# Check challenges after gameplay
newly_done = cm.check_challenges({
    "mode": "my_mode",
    "failed": False,
    "accuracy": 95.0,
    # ... any stat fields your condition uses
})
```

Supported condition keys — see [`src/only4bms/game/challenge.py`](../src/only4bms/game/challenge.py) for the full list:
`min_level`, `mode`, `must_clear`, `min_accuracy`, `max_accuracy`, `min_combo`, `max_misses`, `require_full_combo`, `require_all_perfect`, `min_hp`, `min_difficulty`, `min_consecutive_courses`, `difficulty_exact`, `proceed_to_next`, `has_ln`, `used_mod`, …

### i18n — internationalisation

```python
import only4bms.i18n as _i18n

# Get current language code ('en', 'ko', 'ja', ...)
lang = _i18n.get_language()

# Get a host string (shared UI labels)
label = _i18n.get("menu_single")

# Load a font scaled to the current window height
font = _i18n.font("menu_option", sy)        # sy = h / 600.0
bold_font = _i18n.font("hud_bold", sy, bold=True)

# Register mod-local strings so host UI (e.g. challenge menu) can find them
_i18n.register_strings("en", {"ch_my_challenge_title": "My Challenge",
                               "ch_my_challenge_desc":  "Do the thing."})
```

**Recommended pattern** — keep mod strings in a local `i18n.py`:

```python
# mods/my_mod/i18n.py
_STRINGS = {
    "en": {"menu_my_mod": "My Mod", "ch_my_challenge_title": "My Challenge", ...},
    "ko": {"menu_my_mod": "나의 모드", ...},
}

def t(key: str, **kwargs) -> str:
    from only4bms.i18n import get_language
    lang = get_language()
    table = _STRINGS.get(lang, _STRINGS["en"])
    s = table.get(key) or _STRINGS["en"].get(key, key)
    return s.format(**kwargs) if kwargs else s
```

Then in `__init__.py`:
```python
from .i18n import t as _t
label = _t("menu_my_mod")          # live localisation
```

### Paths

```python
from only4bms import paths

paths.BASE_PATH   # directory containing the executable (or project root in dev)
paths.DATA_PATH   # writable user data directory (settings, BMS files)
paths.SONG_DIR    # BMS files directory  (= DATA_PATH/bms)
paths.MODS_DIR    # mods/ directory      (= BASE_PATH/mods)
paths.AI_DIR      # built-in AI models
```

---

## Rendering Your Own UI

```python
import pygame
from pygame._sdl2.video import Texture

def run(settings, renderer, window, **ctx):
    w, h = window.size
    clock = pygame.time.Clock()
    screen = pygame.Surface((w, h), pygame.SRCALPHA)
    texture = None

    pygame.key.set_repeat(300, 50)
    pygame.event.clear()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        screen.fill((10, 10, 20))
        # ... pygame.draw calls, font renders, etc. ...

        if texture is None:
            texture = Texture.from_surface(renderer, screen)
        else:
            texture.update(screen)

        renderer.clear()
        renderer.blit(texture, pygame.Rect(0, 0, w, h))
        renderer.present()
        clock.tick(settings.get("fps", 60))

    pygame.key.set_repeat(0)
```

---

## Sub-modules

```
mods/
└── my_mod/
    ├── __init__.py      ← MOD_* constants, get_display_name(), setup(), run()
    ├── i18n.py          ← mod-local translations (_STRINGS + t())
    ├── menu.py          ← custom menu / HUD
    ├── session.py       ← mod-specific gameplay
    └── extension.py     ← GameExtension subclass
```

Import with relative imports inside the package:

```python
from .menu import MyModMenu
from .extension import MyExtension
```

---

## Minimal Example

```python
# mods/hello_world/__init__.py
import pygame
from pygame._sdl2.video import Texture

MOD_ID          = "hello_world"
MOD_NAME        = "Hello World"
MOD_DESCRIPTION = "Displays a greeting and returns to the menu."
MOD_VERSION     = "0.1.0"


def run(settings, renderer, window, **ctx):
    w, h = window.size
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, int(h * 0.08))
    screen = pygame.Surface((w, h))
    texture = None

    pygame.event.clear()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type in (pygame.QUIT, pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                running = False

        screen.fill((10, 5, 30))
        msg = font.render("Hello from my mod!  (press any key)", True, (0, 255, 200))
        screen.blit(msg, msg.get_rect(center=(w // 2, h // 2)))

        if texture is None:
            texture = Texture.from_surface(renderer, screen)
        else:
            texture.update(screen)

        renderer.clear()
        renderer.blit(texture, pygame.Rect(0, 0, w, h))
        renderer.present()
        clock.tick(settings.get("fps", 60))
```

---

## Packaging & Distribution

A mod is just a folder — zip it and share:

```
my_mod.zip
└── my_mod/
    ├── __init__.py
    └── ...
```

Users extract it into the `mods/` directory next to the Only4BMS executable (or project root in development).

---

## Built-in Mods (Reference Implementations)

| Folder | Description |
|---|---|
| `course_mode/` | Roguelike HP training mode — `CourseSession` + `CourseGameExtension` + `setup()` for challenge registration |
| `online_multiplay/` | Socket.IO 1v1 multiplayer — `MultiplayerMenu` + `OnlineGameExtension` |

Reading their `__init__.py` and `extension.py` is the best way to see how to wire the full interface together.
