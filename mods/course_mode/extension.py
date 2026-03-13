"""
CourseGameExtension
===================
Implements HP tracking, HP bar HUD, modifier badges, and wave-viz background
for course mode — all logic that used to live inside RhythmGame / GameRenderer.
"""

import math
import time

import pygame
from pygame._sdl2.video import Texture  # type: ignore

from only4bms.game.game_extension import GameExtension
from .i18n import t as _t


# ── HP constants (kept in sync with course_session.py) ──────────────────────
_MISS_DRAIN     = 8.0
_GOOD_DRAIN     = 2.0
_GREAT_REGEN    = 0.5
_PERFECT_REGEN  = 1.0


class _WaveLayer:
    def __init__(self, w, h, amp_ratio, freq, speed, phase, color):
        self.w = w
        self.h = h
        self.amp = h * amp_ratio
        self.freq = freq
        self.speed = speed
        self.phase = phase
        self.color = color

    def update(self, dt):
        self.phase += self.speed * dt

    def draw(self, renderer, cx, cy, half_w):
        steps = max(4, half_w // 2)
        pts = []
        for i in range(steps + 1):
            x = cx - half_w + i * (half_w * 2 // steps)
            angle = (i / steps) * self.freq * math.pi * 2 + self.phase
            y = int(cy + math.sin(angle) * self.amp)
            pts.append((x, y))
        if len(pts) >= 2:
            renderer.draw_color = self.color
            for j in range(len(pts) - 1):
                renderer.draw_line(pts[j], pts[j + 1])


class _WaveViz:
    def __init__(self, w, h):
        self._layers = [
            _WaveLayer(w, h, 0.08, 2.0, 0.6,  0.0, (0, 180, 255, 60)),
            _WaveLayer(w, h, 0.05, 3.5, 1.1,  1.0, (0, 255, 180, 45)),
            _WaveLayer(w, h, 0.12, 1.2, 0.35, 2.5, (60, 120, 255, 30)),
        ]
        self._last_t = time.perf_counter()

    def tick(self):
        now = time.perf_counter()
        dt = now - self._last_t
        self._last_t = now
        for L in self._layers:
            L.update(dt)

    def draw(self, renderer, cx, cy, half_w):
        for L in self._layers:
            L.draw(renderer, cx, cy, half_w)


class CourseGameExtension(GameExtension):
    """
    Attach to RhythmGame to enable course-mode HP system and HUD.

    Parameters
    ----------
    hp          : starting HP value
    hp_max      : maximum HP
    modifier    : list of modifier tuples from course_session._MODIFIERS, or None
    """

    def __init__(self, hp: float, hp_max: float, modifier=None):
        self.hp = hp
        self.hp_max = hp_max
        self.modifier = modifier or []
        self.failed = False
        self._wave = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def attach(self, game) -> None:
        super().attach(game)
        w, h = game.window.size
        self._wave = _WaveViz(w, h)
        # Font for the HUD — reuse host font system
        import only4bms.i18n as _i18n
        sy = h / 600.0
        self._font = _i18n.font("hud_normal", sy)
        self._small_font = _i18n.font("menu_small", sy)
        self._sy = sy
        self._width = w
        self._height = h

    # ------------------------------------------------------------------
    # Per-note hook — update HP
    # ------------------------------------------------------------------

    def on_judgment(self, key: str, lane: int, t_ms: float) -> None:
        drain = 0.0
        regen = 0.0

        if   key == "PERFECT": regen = _PERFECT_REGEN
        elif key == "GREAT":   regen = _GREAT_REGEN
        elif key == "GOOD":    drain = _GOOD_DRAIN
        elif key == "MISS":    drain = _MISS_DRAIN

        for mod in self.modifier:
            mod_key = mod[0]
            if   mod_key == "mod_hp_boost":       regen *= 1.5
            elif mod_key == "mod_hp_regen":        regen *= 2.0
            elif mod_key == "mod_hp_fragile":      drain *= 2.0
            elif mod_key == "mod_hp_drain":
                drain *= 1.5
                regen *= 0.5
            elif mod_key == "mod_perfectionist":
                if key != "PERFECT":
                    if key == "GREAT": drain += 1.5
                    elif key == "GOOD": drain += 2.0
                    elif key == "MISS": drain += 1.0

        self.hp = max(0.0, min(self.hp_max, self.hp + regen - drain))

    def should_abort(self) -> bool:
        if not self.failed and self.hp <= 0:
            self.failed = True
            return True
        return False

    # ------------------------------------------------------------------
    # Rendering — background wave viz
    # ------------------------------------------------------------------

    def draw_background(self, renderer, window) -> None:
        self._wave.tick()
        w, h = window.size
        self._wave.draw(renderer, w // 2, h // 2 + int(h * 0.1), w // 2 - 40)

    # ------------------------------------------------------------------
    # Rendering — HP bar + modifier badges overlay
    # ------------------------------------------------------------------

    def draw_overlay(self, renderer, window, game_state: dict, phase: str) -> None:
        if phase == "result" and self.failed:
            w, h = window.size
            sy = h / 600.0
            stamp_surf = self._font.render(_t("failed_stamp"), True, (255, 50, 50))
            stamp_tex = Texture.from_surface(renderer, stamp_surf)
            stamp_tex.alpha = 180
            sx = int(w / 800.0 * 100)
            renderer.blit(stamp_tex, pygame.Rect(
                w // 2 - stamp_tex.width // 2 + sx,
                h // 2 - stamp_tex.height // 2,
                stamp_tex.width, stamp_tex.height))
            return

        if phase != "playing":
            return

        w, h = window.size
        sy = h / 600.0

        def _s(v): return max(1, int(v * sy))

        # Lane bounds from game state
        lx = game_state.get("lane_x", [])
        ltw = game_state.get("lane_total_w", 0)
        if not lx:
            return

        hp_ratio = max(0.0, min(1.0, self.hp / (self.hp_max or 1)))
        bar_w = ltw
        bar_h = _s(8)
        bar_x = lx[0]
        bar_y = h - _s(46)

        # Background
        renderer.draw_color = (40, 10, 10, 200)
        renderer.fill_rect((bar_x, bar_y, bar_w, bar_h))

        # Fill
        fill_w = max(0, int(bar_w * hp_ratio))
        if fill_w:
            r_c = int(255 * (1.0 - hp_ratio))
            g_c = int(200 * hp_ratio)
            renderer.draw_color = (r_c, g_c, 40, 220)
            renderer.fill_rect((bar_x, bar_y, fill_w, bar_h))

        # Border
        border_col = (200, 80, 80, 180) if hp_ratio < 0.25 else (80, 200, 120, 160)
        renderer.draw_color = border_col
        renderer.draw_rect((bar_x, bar_y, bar_w, bar_h))

        # HP label
        hp_color = (255, 100, 100) if hp_ratio < 0.25 else (180, 230, 180)
        hp_surf = self._small_font.render(
            f"HP  {int(self.hp)}/{int(self.hp_max)}", True, hp_color)
        hp_tex = Texture.from_surface(renderer, hp_surf)
        hp_tex.alpha = 220
        renderer.blit(hp_tex, pygame.Rect(bar_x, bar_y - _s(18), hp_tex.width, hp_tex.height))

        # Modifier badges
        if self.modifier:
            y_m = _s(6)
            for mod in self.modifier:
                mod_key, is_buff, *_rest, desc_key = mod
                mod_text = _t(desc_key)
                prefix = ">> " if is_buff else "<< "
                mod_color = (130, 255, 180) if is_buff else (255, 120, 100)
                m_surf = self._small_font.render(prefix + mod_text, True, mod_color)
                m_tex = Texture.from_surface(renderer, m_surf)
                m_tex.alpha = 220
                renderer.blit(m_tex, pygame.Rect(lx[0], y_m, m_tex.width, m_tex.height))
                y_m += _s(18)

    # ------------------------------------------------------------------
    # Stats contribution
    # ------------------------------------------------------------------

    def get_extra_stats(self) -> dict:
        return {
            "failed": self.failed,
            "hp": self.hp,
            "must_win": False,
        }
