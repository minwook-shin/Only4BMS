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
| `save_settings_fn` | `callable(settings)` | Persist settings to disk — call after opening `SettingsMenu` inside your mod |
| `challenge_manager` | `ChallengeManager` | Shared challenge manager — register challenges in `setup()`, pass to `RhythmGame` for in-game tracking |

Always use `.get()` so your mod works even if a key is absent:

```python
init_mixer_fn     = ctx.get("init_mixer_fn")
save_settings_fn  = ctx.get("save_settings_fn")
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
    mode='single',            # 'single' | 'ai_multi' | 'online_multi' (label only)
    renderer=renderer,
    window=window,
    note_mod='None',          # 'None' | 'Mirror' | 'Random'
    challenge_manager=challenge_manager,
    extension=my_extension,   # GameExtension subclass, or None
    num_lanes=4,              # number of playable lanes (default 4)
)
result = game.run()           # returns dict with 'action', plus get_stats() keys
```

> **Note:** `mode` is a label passed through to `get_stats()` for challenge
> conditions. All mode-specific behaviour (dual-player layout, AI engine,
> network sync) is now owned by the `extension`. `RhythmGame` itself has no
> mode-specific branches.

#### `num_lanes` — variable lane count

Pass `num_lanes=N` to run the game engine with N lanes instead of the default 4.
The renderer adapts automatically — lane background, dividers, and hit-zone
effects all scale to whatever value you provide.

```python
# 2-key mode: remap BMS notes to 2 lanes, then run with num_lanes=2
for note in notes:
    note['lane'] = 0 if note['lane'] < 2 else 1

game = RhythmGame(
    notes, ..., num_lanes=2,
    extension=my_two_lane_extension,
)
```

Key rules when using a non-default lane count:

- **Notes**: remap `note['lane']` values to `[0, num_lanes)` before passing to `RhythmGame`.
  Notes that land on the same `(time_ms, lane)` after remapping should be converted to
  `is_auto=True` so their keysounds still fire without requiring a key press.
- **Keys**: pass a `settings` dict whose `'keys'` list has `num_lanes` entries
  (or fewer — `handle_input` only iterates entries that exist).
- **Lane width**: override `game.lane_w`, `game.lane_total_w`, and `game.lane_x`
  inside `on_attach_init` to give each lane the width you want.
  The renderer reads lane width as `lx[1] - lx[0]` and adapts all note/effect sizes accordingly.

#### Secondary / alias keys (`key_aliases`)

`settings['key_aliases']` is a `dict[int, int]` that maps extra pygame key codes to lane
indices.  Use this to let multiple physical keys trigger the same lane — exactly how
`mods/two_key/` makes D an alias for F (lane 0) and K an alias for J (lane 1).

```python
# F (lane 0) and J (lane 1) are primary; D and K are aliases.
settings_copy['keys']        = [pygame.K_f, pygame.K_j]   # 2 primary keys
settings_copy['key_aliases'] = {pygame.K_d: 0,            # D → lane 0
                                 pygame.K_k: 1}            # K → lane 1
```

Release logic: a lane is released only when **all** keys for that lane
(primary + aliases) are up simultaneously, so long-note holding works
correctly no matter which combination of keys the player holds.

`key_aliases` is optional and defaults to `{}` — existing mods are unaffected.

See `mods/two_key/` for a complete reference implementation.

#### `get_stats()` return value

| Key | Type | Description |
|---|---|---|
| `action` | str | `'CLEAR'` \| `'RESTART'` \| `'QUIT'` |
| `mode` | str | Game mode label |
| `title` | str | Song title |
| `level` | str | Chart level |
| `judgments` | dict | `{PERFECT, GREAT, GOOD, MISS}` counts |
| `max_combo` | int | Maximum combo achieved |
| `accuracy` | float | EX accuracy % |
| `total_score` | int | EX score |
| `total_notes` | int | Total note count |
| `failed` | bool | True if extension aborted (e.g. HP zero) |
| `speed_changed` | bool | Player changed scroll speed mid-song |
| `first_note_miss` | bool | First note was missed |
| `has_ln` | bool | Chart contains long notes |
| `used_mod` | bool | Mirror or Random note mod was applied |
| `note_mod` | str | `'None'` \| `'Mirror'` \| `'Random'` |
| `newly_completed` | list | Challenge dicts completed this run |
| *extension keys* | any | Extra keys from `extension.get_extra_stats()` |

Common extension-provided keys: `'must_win'`, `'ai_accuracy'`, `'ai_paused'`, `'ai_restarted'`, `'failed'`, `'hp'`.

### GameExtension — in-game hooks

Subclass `GameExtension` to inject mod logic into the game loop without modifying `RhythmGame`.
Pass an instance as `extension=` when constructing `RhythmGame`.

All methods have default no-op implementations — only override what you need.

```python
from only4bms.game.game_extension import GameExtension

class MyExtension(GameExtension):

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def attach(self, game) -> None:
        """Called at the end of RhythmGame.__init__.
        Store game reference and pre-load resources (fonts, textures, etc.)."""
        super().attach(game)   # sets self._game = game
        w, h = game.window.size

    def on_attach_init(self, game) -> None:
        """Called immediately after attach().
        Use this to set up mode-specific state directly on the game object:
        dual lane layouts, opponent engines, judgment dicts, network connections.
        Anything that needs to live on `game` and depends on the extension."""

    # ── Input event hooks ────────────────────────────────────────────────────

    def on_pause(self) -> None:
        """Called when the player pauses (ESC / TAB).
        Use this to record pause events for challenge tracking, etc."""

    def on_restart(self) -> None:
        """Called when the player hits R (quick restart), before needs_restart
        is set. Use this to run challenge checks or record restart state."""

    # ── Per-note / per-frame hooks ───────────────────────────────────────────

    def on_judgment(self, key: str, lane: int, t_ms: float) -> None:
        """Called after every note judgment.
        key: 'PERFECT' | 'GREAT' | 'GOOD' | 'MISS'"""

    def on_tick(self, sim_time_ms: float) -> None:
        """Called once per render frame while the song is playing.
        Use for network polling, AI inference loops, time-based effects."""

    def should_abort(self) -> bool:
        """Return True to immediately end the song (transitions to RESULT)."""
        return False

    # ── Rendering hooks ──────────────────────────────────────────────────────

    def draw_background(self, renderer, window) -> None:
        """Draw behind BGA / note field (called after renderer.clear())."""

    def get_opponent_ln_effects(self, game, frame_count: int) -> list:
        """Return extra effect dicts for opponent held-LN rendering.
        Each dict: {'lane': int, 'radius': int, 'color': tuple, 'alpha': int,
                    'note_type': int}
        Opponent lane indices should be offset by NUM_LANES.
        Default: [] (no opponent LN effects)."""
        return []

    def get_all_lanes(self, game) -> list:
        """Return the full lane-position list used for hit-effect rendering.
        Single-player: return game.lane_x  (default).
        Dual-player:   return game.p1_lane_x + game.p2_lane_x."""
        return game.lane_x

    def get_p1_lane_x(self, game) -> list:
        """Return the lane_x list to use for the P1 draw state.
        Single-player: game.lane_x  (default).
        Dual-player:   game.p1_lane_x."""
        return game.lane_x

    def get_p1_draw_extras(self, game) -> dict:
        """Extra keys merged into the P1 draw-state dict passed to the renderer.
        Dual-player extensions inject ai_judgments and ai_hit_history here.
        Default: {} (no extras)."""
        return {}

    def draw_mid_hud(self, renderer, window, t: float, game,
                     p1_ratio: float, max_ex: int,
                     gy: int, gw: int, gh: int, ga: int) -> None:
        """Draw the performance gauge(s) and any opponent panel.
        Called inside _draw() after P1 effects are rendered.

        Default: single-player EX gauge to the left of the lane column.
        Dual-player extensions override this to draw both gauges + opponent
        note field + score bar.

        Parameters:
          p1_ratio  player EX ratio in [0, 1]
          max_ex    maximum possible EX score
          gy/gw/gh  gauge top-y, width, height in screen pixels
          ga        gauge alpha (fades to 0 after last note passes)"""
        gx = game.lane_x[0] - gw - game.game_renderer._sx(10)
        game.game_renderer.draw_vertical_gauge(gx, gy, gw, gh, p1_ratio, (0, 255, 255), ga)

    def draw_overlay(self, renderer, window, game_state: dict, phase: str) -> None:
        """Draw on top of the entire game frame (before renderer.present()).
        phase: 'playing' | 'paused' | 'result'"""

    # ── Stats contribution ───────────────────────────────────────────────────

    def get_extra_stats(self) -> dict:
        """Extra fields merged into RhythmGame.get_stats().
        Also passed to challenge_manager.check_challenges().
        Common keys: 'failed', 'must_win', 'ai_accuracy', 'ai_paused',
                     'ai_restarted', 'hp'."""
        return {}
```

#### Lane layout via `on_attach_init`

Use `on_attach_init` to override the lane geometry that `RhythmGame.__init__`
sets up.  Write directly onto `game`:

**2-key wide-lane layout** (as used by `mods/two_key/`):

```python
def on_attach_init(self, game) -> None:
    new_lane_w        = game.lane_w * 2        # double width per lane
    game.lane_total_w = new_lane_w * 2         # 2 lanes
    start_x           = (game.width - game.lane_total_w) // 2
    game.lane_x       = [start_x, start_x + new_lane_w]
    game.lane_w       = new_lane_w             # effects use this value
```

The renderer reads lane width as `lx[1] - lx[0]` and the hit-effect system
reads `game.lane_w`, so updating both is sufficient — no renderer subclassing
needed.

**Dual-player layout** (e.g. `AiMultiExtension`, `OnlineGameExtension`):

```python
def on_attach_init(self, game) -> None:
    w, h = game.width, game.height
    p1_start = w // 4 - game.lane_total_w // 2
    game.p1_lane_x = [p1_start + i * game.lane_w for i in range(NUM_LANES)]
    p2_start = (w * 3) // 4 - game.lane_total_w // 2
    game.p2_lane_x = [p2_start + i * game.lane_w for i in range(NUM_LANES)]
    game.lane_x = game.p1_lane_x   # redirect default to P1 column

    # Create opponent engine, judgment state, network connection, etc.
    game.ai_judgments = {k: 0 for k in JUDGMENT_ORDER}
    game.ai_combo = 0
    game.ai_hit_history = []
    ...
```

For dual-player, also override `get_all_lanes`, `get_p1_lane_x`, `get_p1_draw_extras`,
and `draw_mid_hud` to render the full dual-player HUD.

#### `game_state` dict passed to `draw_overlay` (phase `'playing'`)

| Key | Type | Description |
|---|---|---|
| `lane_x` | list[int] | Left pixel edge of each P1 lane |
| `lane_total_w` | int | Total width of the lane area |
| `judgments` | dict | `{PERFECT, GREAT, GOOD, MISS}` counts |
| `combo` | int | Current combo |
| `judgment_text` | str | Localised judgment label |
| `judgment_key` | str | Raw judgment key |
| `hit_history` | list | `[(t_ms, err_ms, key), ...]` |
| `speed` | float | Current scroll speed |
| `is_ai` | bool | Always False for P1 state |

During phase `'result'`, `game_state` is the full `get_stats()` dict (see below).

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
| `ai_multi/` | Local AI opponent — `AiMultiExtension` (dual layout, 120 Hz inference, opponent HUD). Model files live here for easy user replacement. |
| `course_mode/` | Roguelike HP training mode — `CourseSession` + `CourseGameExtension` + `setup()` for challenge registration |
| `online_multiplay/` | Socket.IO 1v1 multiplayer — `MultiplayerMenu` + `OnlineGameExtension` |
| `two_key/` | 2-key mode — merges 4-lane BMS charts into 2 wide lanes, HP drain system. Reference for `num_lanes` + lane geometry override. |

Reading `extension.py` in each mod is the best way to see how to wire the full interface together.

### ai_multi — dual-player vs AI

`mods/ai_multi/` is the reference implementation for a fully self-contained mod that:
- Owns its own song selection loop (via `SongSelectMenu`)
- Bundles replaceable AI models (`model_normal.zip`, `model_hard.zip`)
- Drives an AI opponent at 120 Hz via a local `GameExtension`

```python
# mods/ai_multi/extension.py
from only4bms.game.game_extension import GameExtension

class AiMultiExtension(GameExtension):
    ...
```

Users who want to swap the AI model simply replace `model_normal.zip` or `model_hard.zip`
in `mods/ai_multi/` with a new `stable_baselines3` PPO model trained on `RhythmEnv`
(see `src/only4bms/ai/train.py`).

The `save_settings_fn` context key is now available to mods that open a settings menu:

```python
def run(settings, renderer, window, **ctx):
    save_settings_fn = ctx.get("save_settings_fn")   # callable(settings) -> None
    ...
    if action == "SETTINGS":
        SettingsMenu(settings, ...).run()
        if save_settings_fn:
            save_settings_fn(settings)
```

---

## UI Design System

All built-in screens use a shared glassmorphism design system in `only4bms.ui.components`.
Mods should use the same system so they blend visually with the host UI.

### Import

```python
from only4bms.ui.components import (
    make_bg_cache, draw_glass_panel, draw_outer_glow,
    draw_glow_text, draw_hint_bar, draw_scrollbar,
    draw_pill_button, draw_modal, draw_modal_button,
    draw_row, draw_category,
    # Colour palette
    C_TEXT_PRIMARY, C_TEXT_SECONDARY, C_TEXT_DIM,
    C_GLOW_CYAN, C_GLOW_PURPLE, C_BORDER_DIM,
    C_GLASS_FILL, C_GLASS_HOVER,
    BASE_W, BASE_H,
)
```

### Colour Palette

| Token | RGB | Usage |
|---|---|---|
| `C_GLOW_CYAN` | `(0, 212, 255)` | Primary accent — titles, selected rows, active inputs |
| `C_GLOW_PURPLE` | `(180, 80, 255)` | Secondary accent — modals, waiting state |
| `C_TEXT_PRIMARY` | `(232, 240, 255)` | Main readable text |
| `C_TEXT_SECONDARY` | `(140, 155, 195)` | Subtitles, labels, inactive values |
| `C_TEXT_DIM` | `(70, 85, 125)` | Hints, disabled items |
| `C_GLASS_FILL` | `(255,255,255, 12)` | Default glass panel fill (SRCALPHA) |
| `C_GLASS_HOVER` | `(255,255,255, 22)` | Hovered row fill |
| `C_BORDER_DIM` | `(255,255,255, 32)` | Unselected border |

### Minimum Mod Screen Template

```python
import pygame
import time
from only4bms import i18n as _i18n
from only4bms.ui.components import (
    make_bg_cache, draw_glass_panel, draw_glow_text, draw_hint_bar,
    C_GLOW_CYAN, C_TEXT_PRIMARY, C_TEXT_SECONDARY, BASE_W, BASE_H,
)

class MyModMenu:
    def __init__(self, settings, renderer, window):
        self.settings = settings
        self.renderer = renderer
        self.window   = window
        self.w, self.h = window.size
        self.sx, self.sy = self.w / BASE_W, self.h / BASE_H

        self.screen = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self._bg    = make_bg_cache(self.w, self.h)   # pre-rendered once

        self.title_font = _i18n.font("menu_title",  self.sy, bold=True)
        self.body_font  = _i18n.font("ui_body",     self.sy)
        self.small_font = _i18n.font("menu_small",  self.sy)

        self.running = True

    def _s(self, v): return max(1, int(v * self.sy))

    def run(self):
        from pygame._sdl2.video import Texture
        clock   = pygame.time.Clock()
        texture = None

        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False

            self._draw()

            if not texture:
                texture = Texture.from_surface(self.renderer, self.screen)
            else:
                texture.update(self.screen)
            self.renderer.clear()
            self.renderer.blit(texture, pygame.Rect(0, 0, self.w, self.h))
            self.renderer.present()
            clock.tick(60)

    def _draw(self):
        # 1. Background
        self.screen.blit(self._bg, (0, 0))

        # 2. Title with glow
        draw_glow_text(self.screen, "My Mod", self.title_font,
                       C_GLOW_CYAN, C_GLOW_CYAN,
                       (self.w // 2, self._s(32)), anchor="center", glow_radius=4)

        # 3. Content panel
        panel_w, panel_h = self._s(500), self._s(300)
        panel = pygame.Rect((self.w - panel_w) // 2, self._s(110), panel_w, panel_h)
        draw_glass_panel(self.screen, panel,
                         border_color=(*C_GLOW_CYAN, 70), radius=14, fill_alpha=10)

        # 4. Content inside panel
        msg = self.body_font.render("Hello from my mod!", True, C_TEXT_PRIMARY)
        self.screen.blit(msg, msg.get_rect(center=panel.center))

        # 5. Hint bar (always last)
        draw_hint_bar(self.screen, "ESC  Back", self.small_font, self.h, self.w)
```

### Common Components

#### `draw_glass_panel(surf, rect, border_color, radius, fill_alpha)`
Renders a frosted-glass card. Use `border_color=(*C_GLOW_CYAN, 70)` for cyan-themed panels,
`(*C_GLOW_PURPLE, 70)` for purple-themed ones.

#### `draw_outer_glow(surf, rect, color, radius, passes, max_alpha)`
Soft glow halo around a selected / focused element. Typical: `passes=4, max_alpha=32`.

#### `draw_glow_text(surf, text, font, color, glow_color, pos, anchor, glow_radius)`
Layered glow effect for titles and important labels.
`anchor` can be `'topleft'` (default), `'center'`, `'topright'`, `'midleft'`.

#### `draw_hint_bar(surf, text, font, y_bottom, w)`
Full-width translucent strip at the bottom of the screen. Always call last in `_draw()`.

#### `draw_pill_button(surf, rect, label, font, hovered, accent)`
Small rounded button. Use for toolbar / nav buttons. Pass `hovered=rect.collidepoint(mx, my)`.

#### `draw_scrollbar(surf, x, y, h, ratio_start, ratio_end)`
3px slim scrollbar. Compute ratios from `scroll_offset / total` and `(scroll_offset + visible) / total`.

#### `draw_modal(surf, rect, title, title_font, radius, accent)` → `div_y`
Dark glass modal dialog with title and divider. Returns `div_y` so you can place body content below.
Combine with `draw_modal_button` for confirm dialogs.

### Font Size Keys (`only4bms.i18n.font(key, scale)`)

| Key | Base px | Typical use |
|---|---|---|
| `"menu_title"` | 76 | Screen titles |
| `"menu_option"` | 36 | List item titles |
| `"menu_small"` | 20 | Labels, hints |
| `"ui_title"` | 38 | Panel headers |
| `"ui_body"` | 27 | Body text, option values |
| `"ui_small"` | 18 | Secondary labels |
