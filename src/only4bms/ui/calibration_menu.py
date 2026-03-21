import pygame
import time
import math
import numpy as np
from only4bms.i18n import get as _t
from only4bms import i18n as _i18n
from .components import (
    make_bg_cache, draw_glass_panel, draw_glow_text, draw_hint_bar,
    draw_outer_glow,
    C_TEXT_ACCENT, C_TEXT_PRIMARY, C_TEXT_SECONDARY, C_TEXT_DIM,
    C_GLOW_CYAN, C_GLOW_PURPLE, C_BORDER_DIM,
    BASE_W, BASE_H,
)


class CalibrationMenu:
    def __init__(self, settings, renderer, window):
        from pygame._sdl2.video import Texture
        self.settings = settings
        self.renderer = renderer
        self.window   = window
        self.w, self.h = self.window.size
        self.sx, self.sy = self.w / BASE_W, self.h / BASE_H

        self.screen  = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.texture = None
        self._bg     = make_bg_cache(self.w, self.h)
        self.clock   = pygame.time.Clock()

        self.title_font = _i18n.font("ui_title", self.sy, bold=True)
        self.font       = _i18n.font("ui_body",  self.sy)
        self.small_font = _i18n.font("ui_small", self.sy)

        self.running        = True
        self.start_time     = time.perf_counter()
        self.beat_interval  = 1.0
        self.offsets        = []
        self.last_hit_diff  = 0
        self.last_hit_time  = 0
        self.message        = _t("tap_to_beat")

        self.click_sound = None
        try:
            sample_rate = 44100
            duration    = 0.05
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            tone = np.sin(440 * t * 2 * np.pi)
            fade = np.linspace(1, 0, len(tone))
            tone = (tone * fade * 32767).astype(np.int16)
            stereo = np.vstack((tone, tone)).T.copy(order="C")
            self.click_sound = pygame.sndarray.make_sound(stereo)
        except Exception:
            pass

    def _s(self, v):
        return max(1, int(v * self.sy))

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        from pygame._sdl2.video import Texture
        pygame.key.set_repeat(0)
        while self.running:
            t_now = time.perf_counter() - self.start_time
            if (t_now % self.beat_interval) < (1.0 / 60.0) and t_now > 0.1:
                if not hasattr(self, "_last_beep") or time.perf_counter() - self._last_beep > 0.5:
                    if self.click_sound:
                        self.click_sound.play()
                    self._last_beep = time.perf_counter()
            self._handle_events(t_now)
            self._draw(t_now)
            if not self.texture:
                self.texture = Texture.from_surface(self.renderer, self.screen)
            else:
                self.texture.update(self.screen)
            self.renderer.clear()
            self.renderer.blit(self.texture, pygame.Rect(0, 0, self.w, self.h))
            self.renderer.present()
            self.clock.tick(self.settings.get("fps", 60))
        return self.settings

    # ── Events ────────────────────────────────────────────────────────────────

    def _handle_events(self, t_now):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self.last_hit_time  = time.perf_counter()
                    nearest             = round(t_now / self.beat_interval) * self.beat_interval
                    diff_ms             = (t_now - nearest) * 1000.0
                    self.offsets.append(diff_ms)
                    self.last_hit_diff  = diff_ms
                    if len(self.offsets) > 20:
                        self.offsets.pop(0)
                    avg          = sum(self.offsets) / len(self.offsets)
                    self.message = _t("cal_last_avg").format(
                        last=f"{diff_ms:+.1f}ms", avg=f"{avg:+.1f}ms")
                elif event.key == pygame.K_y:
                    if self.offsets:
                        avg = sum(self.offsets) / len(self.offsets)
                        self.settings["judge_delay"] = round(
                            self.settings.get("judge_delay", 0) + avg, 1)
                        self.offsets = []
                        self.message = _t("applied_judge").format(val=f"{avg:+.1f}ms")
                elif event.key == pygame.K_v:
                    if self.offsets:
                        avg = sum(self.offsets) / len(self.offsets)
                        self.settings["visual_offset"] = int(
                            self.settings.get("visual_offset", 0) - avg)
                        self.offsets = []
                        self.message = _t("applied_visual").format(val=f"{-avg:+.1f}ms")
                elif event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                    self.running = False

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self, t_now):
        self.screen.blit(self._bg, (0, 0))

        # ── Header ──
        draw_glow_text(self.screen, _t("calibration_title"), self.title_font,
                       C_TEXT_ACCENT, C_GLOW_CYAN,
                       (self._s(50), self._s(30)), glow_radius=4)

        sep = pygame.Surface((self.w - self._s(100), 1), pygame.SRCALPHA)
        for x in range(sep.get_width()):
            t = 1.0 - abs(x - sep.get_width() / 2) / (sep.get_width() / 2 + 1)
            sep.set_at((x, 0), (*C_GLOW_CYAN, int(35 * t)))
        self.screen.blit(sep, (self._s(50), self._s(88)))

        # ── Metronome bar ──
        bar_w = self._s(520)
        bar_h = self._s(28)
        bx    = (self.w - bar_w) // 2
        by    = self.h // 2 - bar_h // 2

        bar_rect = pygame.Rect(bx, by, bar_w, bar_h)
        draw_glass_panel(self.screen, bar_rect, radius=bar_h // 2,
                         fill_alpha=14, highlight=False)

        # Oscillating indicator
        pos         = 0.5 + 0.5 * math.sin(t_now * math.pi)
        ind_x       = bx + int(pos * bar_w)
        ind_y       = by + bar_h // 2

        # Glow halo
        glow_r = self._s(22)
        glow   = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
        for r in range(glow_r, 0, -4):
            a = int(50 * (1.0 - r / glow_r))
            pygame.draw.circle(glow, (*C_GLOW_CYAN, a), (glow_r, glow_r), r)
        self.screen.blit(glow, (ind_x - glow_r, ind_y - glow_r))
        pygame.draw.circle(self.screen, C_GLOW_CYAN, (ind_x, ind_y), self._s(10))
        pygame.draw.circle(self.screen, (220, 245, 255),  (ind_x, ind_y), self._s(5))

        # Centre target line
        cx = self.w // 2
        pygame.draw.line(self.screen, (255, 255, 255, 180),
                         (cx, by - self._s(20)), (cx, by + bar_h + self._s(20)), 2)
        # Small tick labels
        lbl_neg = self.small_font.render("-500ms", True, C_TEXT_DIM)
        lbl_pos = self.small_font.render("+500ms", True, C_TEXT_DIM)
        self.screen.blit(lbl_neg, (bx, by + bar_h + self._s(6)))
        self.screen.blit(lbl_pos, (bx + bar_w - lbl_pos.get_width(),
                                   by + bar_h + self._s(6)))

        # ── Hit history dots ──
        for off in self.offsets:
            t_frac = off / 500.0
            ox     = cx + int(t_frac * (bar_w / 2))
            if bx <= ox <= bx + bar_w:
                pygame.draw.line(self.screen, (*C_GLOW_CYAN, 100),
                                 (ox, by + 3), (ox, by + bar_h - 3), 2)

        # ── Hit flash ──
        flash_age = time.perf_counter() - self.last_hit_time
        if flash_age < 0.18:
            alpha = int(255 * (1 - flash_age / 0.18))
            fl    = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            fl.fill((*C_GLOW_CYAN, alpha // 12))
            self.screen.blit(fl, (0, 0))

        # ── Stats ──
        msg_surf = self.font.render(self.message, True, C_TEXT_PRIMARY)
        self.screen.blit(msg_surf, msg_surf.get_rect(
            center=(self.w // 2, by + self._s(105))))

        avg_val  = (sum(self.offsets) / len(self.offsets)) if self.offsets else None
        avg_str  = f"{avg_val:+.1f}ms" if avg_val is not None else "N/A"
        avg_col  = C_GLOW_CYAN if avg_val is not None else C_TEXT_DIM
        avg_surf = self.small_font.render(f"{_t('avg_offset')}: {avg_str}", True, avg_col)
        self.screen.blit(avg_surf, avg_surf.get_rect(
            center=(self.w // 2, by + self._s(140))))

        # ── Hint bar ──
        draw_hint_bar(self.screen, _t("cal_hint"), self.small_font, self.h, self.w)
