"""
TwoKeyExtension
===============
Horizontal-scrolling renderer for 2-Key Mode.

Screen layout
-------------
  ┌──────────────────────────────────────────────────────┐
  │ [HP bar]                                             │  ← top strip
  │                                                      │
  │ ╔══════════════════════════════════════════════════╗ │  ← rail 0 (F / D)
  │ ║  notes scroll  →→→→  ●  ████  ●  ████           ║ │
  │ ╚══════════════════════════════════════════════════╝ │
  │                   PERFECT  42 combo                  │  ← centre HUD
  │ ╔══════════════════════════════════════════════════╗ │  ← rail 1 (J / K)
  │ ║  notes scroll  →→→→  ●  ████  ●  ████           ║ │
  │ ╚══════════════════════════════════════════════════╝ │
  │                                                      │
  └──────────────────────────────────────────────────────┘

Hit zone (⊙) is on the LEFT side of each rail at x ≈ 15 % of screen width.
Notes come from the right and must be hit as they reach the ⊙ marker.

HP system
---------
  PERFECT +1.0   GREAT +0.5   GOOD −1.5   MISS −10.0
  Starts at 50 / 100.  Reaches 0 → FAIL (should_abort returns True).
"""

import math
import time

import pygame
from pygame._sdl2.video import Texture  # type: ignore

from only4bms.game.game_extension import GameExtension
from .i18n import t as _t

# ── HP constants ──────────────────────────────────────────────────────────────
HP_MAX   = 100.0
HP_START = 50.0
_HP_GAIN  = {"PERFECT": 1.0, "GREAT": 0.5}
_HP_DRAIN = {"GOOD": 1.5, "MISS": 10.0}
_HP_DANGER = 0.25   # ratio below which the bar pulses red

# ── Layout ratios (relative to window size) ───────────────────────────────────
_HIT_X_RATIO   = 0.15   # hit zone x position
_RAIL_0_Y      = 0.30   # rail 0 centre y
_RAIL_1_Y      = 0.70   # rail 1 centre y
_RAIL_H_RATIO  = 0.18   # rail height
_HP_H_RATIO    = 0.022  # HP bar height


def _hp_color(ratio: float) -> tuple:
    """Green → yellow → red gradient for the HP bar."""
    if ratio > 0.5:
        t = (ratio - 0.5) / 0.5
        return (int(255 + t * (80  - 255)),
                int(210 + t * (220 - 210)),
                int(50  + t * (100 - 50)))
    else:
        t = ratio / 0.5
        return (255, int(t * 210), int(t * 50))


class TwoKeyExtension(GameExtension):
    """
    Attached to RhythmGame(num_lanes=2, ...) by TwoKeySession.

    Rendering strategy
    ------------------
    draw_background : no-op   (BGA is disabled via show_bga=0 in session settings)
    draw_mid_hud    : no-op   (EX gauge skipped; HP bar is the live indicator)
    draw_overlay    : draws the ENTIRE frame (background + rails + notes + HUD)
                      covering whatever the base renderer drew underneath.
    """

    def __init__(self) -> None:
        self.hp = HP_START
        self._failed = False

        # Rendering state
        self._surf: pygame.Surface | None = None
        self._tex:  Texture | None        = None
        self._w = self._h = 0

        # Pre-computed layout values (set in attach)
        self._hit_x    = 0
        self._rail_cy  = [0, 0]
        self._rail_h   = 0
        self._note_h   = 0   # visual height of a note on the rail
        self._note_w   = 0   # visual width (travel direction) for bar-type notes

        # Per-frame time (updated by on_tick)
        self._current_ms = 0.0

        # Font references (loaded in attach)
        self._font_j     = None
        self._font_combo = None
        self._font_small = None
        self._font_big   = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def attach(self, game) -> None:
        super().attach(game)
        import only4bms.i18n as _i18n

        w, h = game.window.size
        self._w, self._h = w, h
        self._surf = pygame.Surface((w, h), pygame.SRCALPHA)

        sy = h / 600.0
        self._font_j     = _i18n.font("hud_normal", sy)
        self._font_combo = _i18n.font("hud_bold",   sy, bold=True)
        self._font_small = _i18n.font("menu_small",  sy)
        self._font_big   = _i18n.font("menu_title",  sy, bold=True)

        self._hit_x   = int(w * _HIT_X_RATIO)
        self._rail_cy = [int(h * _RAIL_0_Y), int(h * _RAIL_1_Y)]
        self._rail_h  = int(h * _RAIL_H_RATIO)
        self._note_h  = int(self._rail_h * 0.55)
        self._note_w  = max(8, int(self._note_h * 1.4))

    def on_attach_init(self, game) -> None:
        # No lane-geometry changes needed: we draw everything ourselves.
        pass

    # ------------------------------------------------------------------
    # Per-frame timing hook
    # ------------------------------------------------------------------

    def on_tick(self, sim_time_ms: float) -> None:
        self._current_ms = sim_time_ms

    # ------------------------------------------------------------------
    # HP tracking
    # ------------------------------------------------------------------

    def on_judgment(self, key: str, lane: int, t_ms: float) -> None:
        if self._failed:
            return
        if key in _HP_GAIN:
            self.hp = min(HP_MAX, self.hp + _HP_GAIN[key])
        elif key in _HP_DRAIN:
            self.hp = max(0.0, self.hp - _HP_DRAIN[key])
        if self.hp <= 0.0:
            self._failed = True

    def should_abort(self) -> bool:
        return self._failed

    # ------------------------------------------------------------------
    # Rendering hooks — base game rendering is suppressed by draw_overlay
    # ------------------------------------------------------------------

    def draw_background(self, renderer, window) -> None:
        pass  # BGA disabled; clear() already left the screen black

    def draw_mid_hud(self, renderer, window, t, game,
                     p1_ratio, max_ex, gy, gw, gh, ga) -> None:
        pass  # HP bar shown in draw_overlay instead

    def draw_overlay(self, renderer, window, game_state: dict, phase: str) -> None:
        if phase == "result":
            return  # base renderer handles the result screen

        surf = self._surf
        surf.fill((8, 8, 20, 255))  # solid dark background — covers vertical rendering

        lane_pressed = game_state.get("lane_pressed", []) if game_state else []

        self._draw_rails(surf, lane_pressed)
        if game_state:
            self._draw_notes(surf, game_state)
        self._draw_hit_zone(surf, lane_pressed, game_state)
        self._draw_hp_bar(surf)
        if game_state:
            self._draw_hud(surf, game_state)
        if phase == "paused":
            self._draw_pause_overlay(surf)
        if self._failed:
            self._draw_fail_splash(surf)

        if self._tex is None:
            self._tex = Texture.from_surface(renderer, surf)
        else:
            self._tex.update(surf)
        renderer.blit(self._tex, pygame.Rect(0, 0, self._w, self._h))

    # ------------------------------------------------------------------
    # Internal draw helpers
    # ------------------------------------------------------------------

    def _draw_rails(self, surf: pygame.Surface, lane_pressed: list) -> None:
        for lane in range(2):
            cy = self._rail_cy[lane]
            ry = cy - self._rail_h // 2
            pressed = lane < len(lane_pressed) and lane_pressed[lane]

            # Rail background
            bg = (50, 70, 120, 200) if pressed else (18, 18, 42, 200)
            pygame.draw.rect(surf, bg, (0, ry, self._w, self._rail_h))

            # Horizontal edge glow lines (top and bottom of rail)
            for dy, alpha in ((0, 55), (1, 110), (2, 55)):
                pygame.draw.line(surf, (0, 180, 255, alpha),
                                 (0, ry + dy), (self._w, ry + dy))
                pygame.draw.line(surf, (0, 180, 255, alpha),
                                 (0, ry + self._rail_h - dy),
                                 (self._w, ry + self._rail_h - dy))

            # Pressed key: soft blue glow gradient near hit zone
            if pressed:
                gw = self._hit_x + int(self._w * 0.12)
                gsurf = pygame.Surface((gw, self._rail_h), pygame.SRCALPHA)
                steps = max(1, gw // 4)
                for xi in range(steps + 1):
                    x = xi * 4
                    if x >= gw:
                        break
                    a = int(40 * (1 - x / gw))
                    pygame.draw.line(gsurf, (80, 160, 255, a),
                                     (x, 0), (x, self._rail_h))
                surf.blit(gsurf, (0, ry))

    def _draw_notes(self, surf: pygame.Surface, gs: dict) -> None:
        notes     = gs.get("notes", [])
        note_idx  = gs.get("note_idx", 0)
        held_lns  = gs.get("held_lns", [])
        cvt       = gs.get("current_visual_time", 0)
        spd       = gs.get("speed", 1.0)
        note_type = gs.get("note_type", 0)
        COLOR     = (0, 255, 255)
        nh, nw    = self._note_h, self._note_w
        hit_x     = self._hit_x

        # 1. Held LNs — drawn anchored at hit_x and extending rightward
        held_ids: set[int] = set()
        for note in held_lns:
            if note is None:
                continue
            held_ids.add(id(note))
            lane = note["lane"]
            if lane >= 2:
                continue
            cy = self._rail_cy[lane]
            v_end = note.get("visual_end_time_ms",
                              note.get("end_time_ms", note["time_ms"]))
            end_x = hit_x + int((v_end - cvt) * spd)
            if end_x > hit_x:
                bw = min(end_x - hit_x, self._w - hit_x)
                self._draw_ln_body(surf, hit_x, cy, bw, nh, COLOR, 255)
            self._blit_note_head(surf, hit_x, cy, nh, nw, COLOR, note_type, 255)

        # 2. Upcoming / visible notes
        for i in range(note_idx, len(notes)):
            note = notes[i]
            if "hit" in note and id(note) not in held_ids:
                continue
            if "miss" in note:
                continue
            lane = note["lane"]
            if lane >= 2:
                continue
            vt = note.get("visual_time_ms", note["time_ms"])
            td = vt - cvt
            nx = hit_x + int(td * spd)
            if nx > self._w + nw:
                break           # all further notes are even more to the right
            if nx < -(nw * 2):
                continue        # already well past hit zone
            cy    = self._rail_cy[lane]
            is_auto = note.get("is_auto", False)
            alpha = 80 if is_auto else 255

            if note.get("is_ln"):
                v_end = note.get("visual_end_time_ms",
                                  note.get("end_time_ms", note["time_ms"]))
                end_x = hit_x + int((v_end - cvt) * spd)
                ox    = max(nx, 0)
                bw    = max(0, min(end_x, self._w) - ox)
                if bw > 0:
                    self._draw_ln_body(surf, ox, cy, bw, nh, COLOR, alpha)

            if 0 <= nx <= self._w:
                self._blit_note_head(surf, nx, cy, nh, nw, COLOR, note_type, alpha)

    def _draw_ln_body(self, surf: pygame.Surface,
                      x: int, cy: int, bw: int, nh: int,
                      color: tuple, alpha: int) -> None:
        bsurf = pygame.Surface((bw, nh), pygame.SRCALPHA)
        bsurf.fill((*color, int(95 * alpha / 255)))
        # Bright centre stripe
        pygame.draw.line(bsurf, (*color, int(185 * alpha / 255)),
                         (0, nh // 2), (bw, nh // 2), 2)
        surf.blit(bsurf, (x, cy - nh // 2))

    def _blit_note_head(self, surf: pygame.Surface,
                        nx: int, cy: int, nh: int, nw: int,
                        color: tuple, note_type: int, alpha: int) -> None:
        if note_type == 0:  # ── Bar ──────────────────────────────────────────
            rect = pygame.Rect(nx - nw // 2, cy - nh // 2, nw, nh)
            # Outer glow
            gs = pygame.Surface((nw + 12, nh + 12), pygame.SRCALPHA)
            pygame.draw.rect(gs, (*color, int(32 * alpha / 255)),
                             (0, 0, nw + 12, nh + 12), border_radius=5)
            surf.blit(gs, (rect.x - 6, rect.y - 6))
            # Body
            bright = tuple(min(255, int(c * 1.15)) for c in color)
            pygame.draw.rect(surf, (*bright, alpha), rect, border_radius=3)
            # White top rim
            pygame.draw.line(surf,
                             (255, 255, 255, int(190 * alpha / 255)),
                             (rect.x, rect.y + 1),
                             (rect.right - 1, rect.y + 1))
        else:               # ── Circle ───────────────────────────────────────
            r = nh // 2
            pygame.draw.circle(surf, (*color, int(32 * alpha / 255)), (nx, cy), r + 7)
            pygame.draw.circle(surf, (*color, int(65 * alpha / 255)), (nx, cy), r + 4)
            pygame.draw.circle(surf, (*color, alpha), (nx, cy), r)
            pygame.draw.circle(surf,
                               (255, 255, 255, int(175 * alpha / 255)),
                               (nx - r // 3, cy - r // 3), max(1, r // 3))

    def _draw_hit_zone(self, surf: pygame.Surface,
                       lane_pressed: list, gs: dict | None) -> None:
        hx = self._hit_x

        # Red glow halo around the hit line
        for off, a in ((-4, 10), (-3, 20), (-2, 40), (-1, 70),
                       (1, 185), (2, 130), (3, 60), (4, 20)):
            pygame.draw.line(surf, (255, 55, 55, a),
                             (hx + off, 0), (hx + off, self._h))
        # Main hit lines
        pygame.draw.line(surf, (255, 65, 65, 220),  (hx,     0), (hx,     self._h))
        pygame.draw.line(surf, (255, 100, 100, 160), (hx + 1, 0), (hx + 1, self._h))

        j_timer = gs.get("judgment_timer", 0)  if gs else 0
        j_color = gs.get("judgment_color", (255, 255, 255)) if gs else (255, 255, 255)
        age_ms  = self._current_ms - j_timer

        for lane in range(2):
            cy      = self._rail_cy[lane]
            pressed = lane < len(lane_pressed) and lane_pressed[lane]
            r       = int(self._rail_h * 0.32)

            # Judgment flash ring
            if 0 <= age_ms < 250:
                fa = int(170 * (1 - age_ms / 250))
                pygame.draw.circle(surf, (*j_color, fa), (hx, cy), r + 14)

            # Background fill
            pygame.draw.circle(surf, (0, 0, 0, 130), (hx, cy), r)
            # Outer ring
            ring_c = (255, 195, 50, 220) if pressed else (255, 65, 65, 190)
            pygame.draw.circle(surf, ring_c, (hx, cy), r, max(2, r // 5))
            # Inner highlight when pressed
            if pressed:
                pygame.draw.circle(surf, (255, 195, 50, 55),
                                   (hx, cy), r - max(2, r // 5))

    def _draw_hp_bar(self, surf: pygame.Surface) -> None:
        bh    = max(6, int(self._h * _HP_H_RATIO))
        ratio = self.hp / HP_MAX

        # Background strip
        pygame.draw.rect(surf, (14, 14, 28, 230), (0, 0, self._w, bh + 4))
        # Filled portion
        fw = max(0, int(self._w * ratio))
        if fw > 0:
            pygame.draw.rect(surf, (*_hp_color(ratio), 225), (0, 2, fw, bh))
        # Low-HP pulse
        if ratio < _HP_DANGER:
            pa = int(50 + 85 * (math.sin(time.perf_counter() * 8) + 1) / 2)
            pygame.draw.rect(surf, (255, 25, 25, pa), (0, 0, self._w, bh + 4))
        # Border
        pygame.draw.rect(surf, (255, 255, 255, 28), (0, 2, self._w, bh), 1)

    def _draw_hud(self, surf: pygame.Surface, gs: dict) -> None:
        j_text  = gs.get("judgment_text", "")
        j_color = gs.get("judgment_color", (255, 255, 255))
        j_timer = gs.get("judgment_timer", 0)
        combo   = gs.get("combo", 0)
        c_timer = gs.get("combo_timer", 0)
        cx      = self._w // 2
        mid_y   = self._h // 2

        # Judgment text — vertically centred between the two rails
        if j_text and self._current_ms - j_timer < 500:
            age = self._current_ms - j_timer
            a   = int(max(0, 255 * (1 - age / 500)))
            if a > 0:
                ts = self._font_j.render(j_text, True, j_color)
                ts.set_alpha(a)
                surf.blit(ts, (cx - ts.get_width() // 2,
                               mid_y - ts.get_height() // 2))

        # Combo counter just below the judgment text
        if combo > 0 and self._current_ms - c_timer < 500:
            age = self._current_ms - c_timer
            a   = int(max(0, 255 * (1 - age / 500)))
            if a > 0:
                ts = self._font_combo.render(str(combo), True, (255, 255, 255))
                ts.set_alpha(a)
                surf.blit(ts, (cx - ts.get_width() // 2,
                               mid_y + self._font_j.get_height() // 2 + 6))

        # Speed indicator — bottom-left corner
        spd = gs.get("speed", 1.0) / (self._h / 600.0)
        ts  = self._font_small.render(f"SPD {spd:.1f}", True, (130, 130, 150))
        ts.set_alpha(170)
        surf.blit(ts, (8, self._h - ts.get_height() - 8))

    def _draw_pause_overlay(self, surf: pygame.Surface) -> None:
        import only4bms.i18n as _hi
        ov = pygame.Surface((self._w, self._h), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 155))
        surf.blit(ov, (0, 0))
        ts = self._font_big.render(_hi.get("paused"), True, (255, 255, 255))
        surf.blit(ts, (self._w // 2 - ts.get_width() // 2,
                       self._h // 2 - ts.get_height() // 2 - 28))
        hint = self._font_small.render(_hi.get("resume_hint"), True, (180, 255, 180))
        surf.blit(hint, (self._w // 2 - hint.get_width() // 2,
                         self._h // 2 + 20))

    def _draw_fail_splash(self, surf: pygame.Surface) -> None:
        ov = pygame.Surface((self._w, self._h), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        surf.blit(ov, (0, 0))
        ts = self._font_big.render(_t("two_key_fail"), True, (255, 50, 50))
        surf.blit(ts, (self._w // 2 - ts.get_width() // 2,
                       self._h // 2 - ts.get_height() // 2))

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_extra_stats(self) -> dict:
        return {"failed": self._failed, "hp": self.hp}
