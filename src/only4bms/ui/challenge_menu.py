import pygame
import math
import time
from only4bms.i18n import get as _t
from only4bms import i18n as _i18n
from ..game.challenge import ChallengeManager
from .components import (
    make_bg_cache, draw_glass_panel, draw_outer_glow,
    draw_glow_text, draw_hint_bar, draw_scrollbar,
    C_TEXT_PRIMARY, C_TEXT_SECONDARY, C_TEXT_DIM,
    C_GLOW_CYAN, C_GLOW_PURPLE,
    C_GLASS_FILL, C_GLASS_HOVER, C_GLASS_SELECT,
    C_BORDER_DIM, BASE_W, BASE_H,
)

# Gold palette (challenge-specific)
C_GOLD        = (255, 210,  50)
C_GOLD_DIM    = (180, 145,  30)
C_GOLD_GLOW   = (255, 200,   0)
C_GREEN_OK    = (  0, 230,  90)

_VISIBLE_COUNT = 5
_ROW_H_BASE    = 82


class ChallengeMenu:
    def __init__(self, settings, renderer, window, challenge_manager=None):
        self.settings = settings
        self.renderer = renderer
        self.window   = window
        self.w, self.h = window.size
        self.sx, self.sy = self.w / BASE_W, self.h / BASE_H

        self.screen = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self._bg    = make_bg_cache(self.w, self.h)

        self.font       = _i18n.font("menu_option", self.sy)
        self.title_font = _i18n.font("menu_title",  self.sy, bold=True)
        self.small_font = _i18n.font("menu_small",  self.sy)
        self.desc_font  = _i18n.font("menu_small",  self.sy)

        self.manager = challenge_manager if challenge_manager is not None else ChallengeManager()
        self._rebuild_options()
        self.selected_index = 0
        self.scroll_offset  = 0
        self.running        = True

    # ── Data helpers ─────────────────────────────────────────────────────────

    def _rebuild_options(self):
        self.regular_challenges = self.manager.get_visible_challenges()
        self.hidden_challenges  = self.manager.get_hidden_challenges()
        self.show_hidden        = self.manager.all_regular_completed()
        self._any_hidden_early  = (
            any(c["id"] in self.manager.completed_ids for c in self.hidden_challenges)
            and not self.show_hidden
        )
        if self.show_hidden or self._any_hidden_early:
            self.options = self.regular_challenges + self.hidden_challenges
        else:
            self.options = self.regular_challenges[:]

    def _s(self, v):
        return max(1, int(v * self.sy))

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        from pygame._sdl2.video import Texture
        clock   = pygame.time.Clock()
        texture = None
        pygame.key.set_repeat(300, 50)

        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if   event.key == pygame.K_UP:
                        self.selected_index = (self.selected_index - 1) % len(self.options)
                    elif event.key == pygame.K_DOWN:
                        self.selected_index = (self.selected_index + 1) % len(self.options)
                    elif event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                        self.running = False
                elif event.type == pygame.JOYHATMOTION:
                    vx, vy = event.value
                    if   vy ==  1: self.selected_index = (self.selected_index - 1) % len(self.options)
                    elif vy == -1: self.selected_index = (self.selected_index + 1) % len(self.options)
                elif event.type == pygame.JOYBUTTONDOWN:
                    if event.button == 1:
                        self.running = False

            # Auto-scroll
            if self.selected_index < self.scroll_offset:
                self.scroll_offset = self.selected_index
            elif self.selected_index >= self.scroll_offset + _VISIBLE_COUNT:
                self.scroll_offset = self.selected_index - _VISIBLE_COUNT + 1

            self._draw()

            if not texture:
                texture = Texture.from_surface(self.renderer, self.screen)
            else:
                texture.update(self.screen)
            self.renderer.clear()
            self.renderer.blit(texture, pygame.Rect(0, 0, self.w, self.h))
            self.renderer.present()
            clock.tick(60)

        pygame.key.set_repeat(0)

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self):
        t_now = time.time()
        shimmer = (math.sin(t_now * 3.0) + 1) / 2

        self.screen.blit(self._bg, (0, 0))

        # ── Title ──
        draw_glow_text(self.screen, _t("menu_challenge"), self.title_font,
                       C_GOLD, C_GOLD_GLOW,
                       (self.w // 2, self._s(32)), anchor="center", glow_radius=5)

        # Accent line under title
        lw = self._s(240)
        lx = (self.w - lw) // 2
        ly = self._s(88)
        for x in range(lw):
            t = 1.0 - abs(x - lw / 2) / (lw / 2 + 1)
            self.screen.set_at((lx + x, ly), (*C_GOLD_GLOW, int(80 * t)))

        # ── Main panel ──
        panel_w = self._s(620)
        panel_h = self._s(438)
        px      = (self.w - panel_w) // 2
        py      = self._s(100)
        panel_rect = pygame.Rect(px, py, panel_w, panel_h)
        draw_glass_panel(self.screen, panel_rect,
                         border_color=(*C_GOLD_GLOW, 90),
                         radius=14, fill_alpha=10)

        row_h   = self._s(_ROW_H_BASE)
        pad_top = self._s(12)

        for i in range(_VISIBLE_COUNT):
            idx = i + self.scroll_offset
            if idx >= len(self.options):
                break

            ch          = self.options[idx]
            is_completed = ch["id"] in self.manager.completed_ids
            is_hidden    = ch.get("hidden", False)
            is_sel       = (idx == self.selected_index)
            is_early     = is_hidden and is_completed and not self.show_hidden

            rect = pygame.Rect(px + self._s(10),
                               py + pad_top + i * row_h,
                               panel_w - self._s(20),
                               row_h - self._s(8))

            # ── Row background ──
            if is_hidden and not is_early:
                # Shimmering gold bg
                gold_a = int(55 + 25 * shimmer)
                bg     = pygame.Surface(rect.size, pygame.SRCALPHA)
                pygame.draw.rect(bg, (120, 85, 5, gold_a), (0, 0, *rect.size), border_radius=10)
                self.screen.blit(bg, rect.topleft)
                border_col = (*C_GOLD, int(160 + 80 * shimmer))
                if is_sel:
                    draw_outer_glow(self.screen, rect, C_GOLD, radius=10, passes=4, max_alpha=45)
                pygame.draw.rect(self.screen, border_col, rect, 2 if is_sel else 1, border_radius=10)
            else:
                accent = C_GREEN_OK if is_completed else C_GOLD_GLOW
                if is_sel:
                    fill   = (*C_GOLD_GLOW, 22) if not is_completed else (*C_GREEN_OK, 18)
                    border = (*accent, 200)
                    draw_outer_glow(self.screen, rect, accent, radius=10, passes=4, max_alpha=35)
                elif not is_early:
                    fill   = C_GLASS_HOVER if is_sel else C_GLASS_FILL
                    border = C_BORDER_DIM
                else:
                    fill   = C_GLASS_FILL
                    border = (*C_BORDER_DIM[:3], 18)

                bg = pygame.Surface(rect.size, pygame.SRCALPHA)
                pygame.draw.rect(bg, fill, (0, 0, *rect.size), border_radius=10)
                self.screen.blit(bg, rect.topleft)
                pygame.draw.rect(self.screen, border, rect, 1, border_radius=10)

                # Selected pip
                if is_sel:
                    pip_h = rect.height - 16
                    pygame.draw.rect(self.screen, accent,
                                     pygame.Rect(rect.x + 4, rect.y + 8, 3, pip_h),
                                     border_radius=2)

            # ── HIDDEN label ──
            if is_hidden:
                lbl_col = (80, 80, 100) if is_early else C_GOLD
                lbl     = self.small_font.render(_t("challenge_hidden_label"), True, lbl_col)
                self.screen.blit(lbl, (rect.x + self._s(18), rect.y + self._s(2)))
                title_y_off = self._s(18)
                desc_y_off  = self._s(50)
            else:
                title_y_off = self._s(8)
                desc_y_off  = self._s(44)

            # ── Title ──
            title_key = f"ch_{ch['id']}_title"
            if   is_early:       title_col = (70, 70, 90)
            elif is_hidden and is_completed: title_col = C_GOLD
            elif is_completed:   title_col = C_GREEN_OK
            else:                title_col = C_TEXT_PRIMARY
            title_surf = self.font.render(_t(title_key), True, title_col)
            self.screen.blit(title_surf, (rect.x + self._s(18), rect.y + title_y_off))

            # ── Description ──
            desc_key = f"ch_{ch['id']}_desc"
            if   is_early:     desc_col = (55, 55, 75)
            elif is_hidden:    desc_col = (200, 175, 90)
            else:              desc_col = C_TEXT_SECONDARY
            desc_surf = self.desc_font.render(_t(desc_key), True, desc_col)
            self.screen.blit(desc_surf, (rect.x + self._s(22), rect.y + desc_y_off))

            # ── Status badge ──
            if is_hidden:
                if is_early:
                    badge_txt = "???"
                    badge_col = (70, 70, 90)
                elif is_completed:
                    badge_txt = _t("challenge_completed")
                    badge_col = (int(255 - 30 * shimmer), int(215 - 15 * shimmer), 0)
                else:
                    badge_txt = _t("challenge_locked")
                    badge_col = C_GOLD_DIM
            else:
                badge_txt = _t("challenge_completed") if is_completed else _t("challenge_locked")
                badge_col = C_GREEN_OK if is_completed else C_TEXT_SECONDARY

            badge = self.small_font.render(badge_txt, True, badge_col)
            self.screen.blit(badge, (rect.right - badge.get_width() - self._s(18),
                                     rect.centery - badge.get_height() // 2))

        # ── Scrollbar ──
        if len(self.options) > _VISIBLE_COUNT:
            sb_x = px + panel_w - self._s(8)
            sb_y = py + pad_top
            sb_h = _VISIBLE_COUNT * row_h
            r0   = self.scroll_offset / len(self.options)
            r1   = min(1.0, (self.scroll_offset + _VISIBLE_COUNT) / len(self.options))
            draw_scrollbar(self.screen, sb_x, sb_y, sb_h, r0, r1)

        # ── Progress bar ──
        total     = len(self.regular_challenges)
        completed = sum(1 for c in self.regular_challenges if c["id"] in self.manager.completed_ids)
        ratio     = completed / total if total > 0 else 0

        bar_w = self._s(360)
        bar_h = self._s(8)
        bx    = (self.w - bar_w) // 2
        by    = py + panel_h + self._s(16)

        # Track
        track = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
        track.fill((60, 55, 70, 120))
        self.screen.blit(track, (bx, by))
        pygame.draw.rect(self.screen, (*C_BORDER_DIM[:3], 40),
                         pygame.Rect(bx, by, bar_w, bar_h), 1, border_radius=4)

        # Fill
        if ratio > 0:
            fill_w   = max(bar_h, int(bar_w * ratio))
            fill_col = C_GREEN_OK if ratio == 1.0 else C_GOLD_GLOW
            pygame.draw.rect(self.screen, fill_col,
                             pygame.Rect(bx, by, fill_w, bar_h), border_radius=4)

        # Progress label
        prog_txt  = f"{completed} / {total}  ({int(ratio * 100)}%)"
        prog_surf = self.desc_font.render(prog_txt, True, C_TEXT_SECONDARY)
        self.screen.blit(prog_surf, (bx + bar_w + self._s(12), by - self._s(2)))

        # All-clear banner
        if ratio == 1.0:
            bounce_y   = int(math.sin(t_now * 5) * 4)
            clear_surf = self.small_font.render(_t("challenge_all_cleared"), True, C_GREEN_OK)
            cx = bx - clear_surf.get_width() - self._s(14)
            self.screen.blit(clear_surf, (cx, by - self._s(2) + bounce_y))

        # ── Hint bar ──
        draw_hint_bar(self.screen, "↑ ↓  Navigate    ESC  Back",
                      self.small_font, self.h, self.w)
