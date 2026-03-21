import pygame
import time
from only4bms.i18n import get as _host_t
from only4bms import i18n as _i18n
from .i18n import t as _t
from only4bms.ui.components import (
    make_bg_cache, draw_glass_panel, draw_outer_glow,
    draw_glow_text, draw_hint_bar,
    C_TEXT_PRIMARY, C_TEXT_SECONDARY, C_TEXT_DIM,
    C_GLOW_CYAN, C_GLASS_FILL, C_BORDER_DIM, BASE_W, BASE_H,
)

_ROW_H_BASE = 82


class CourseMenu:
    def __init__(self, settings, renderer, window):
        self.settings = settings
        self.renderer = renderer
        self.window = window
        self.w, self.h = window.size
        self.sx, self.sy = self.w / BASE_W, self.h / BASE_H

        self.screen = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self._bg    = make_bg_cache(self.w, self.h)

        self.font       = _i18n.font("menu_option", self.sy)
        self.title_font = _i18n.font("menu_title",  self.sy, bold=True)
        self.small_font = _i18n.font("menu_small",  self.sy)
        self.desc_font  = _i18n.font("menu_small",  self.sy)

        self.options = [
            (lambda: _t("course_beg_title"), lambda: _t("course_beg_desc"), "BEGINNER",     30000),
            (lambda: _t("course_int_title"), lambda: _t("course_int_desc"), "INTERMEDIATE", 30000),
            (lambda: _t("course_adv_title"), lambda: _t("course_adv_desc"), "ADVANCED",     30000),
            (lambda: _t("course_ord_title"), lambda: _t("course_ord_desc"), "ORDEAL",       30000),
        ]
        self.selected_index = 0
        self.running = True
        self.result  = None

    def _s(self, v): return max(1, int(v * self.sy))

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        from pygame._sdl2.video import Texture
        clock   = pygame.time.Clock()
        texture = None
        pygame.key.set_repeat(300, 50)

        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.result = ("QUIT", None, None)
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        self.selected_index = (self.selected_index - 1) % len(self.options)
                    elif event.key == pygame.K_DOWN:
                        self.selected_index = (self.selected_index + 1) % len(self.options)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        opt = self.options[self.selected_index]
                        self.result = ("QUIT", None, None) if opt[2] is None else ("START", opt[2], opt[3])
                        self.running = False
                    elif event.key == pygame.K_ESCAPE:
                        self.result = ("QUIT", None, None)
                        self.running = False
                elif event.type == pygame.JOYHATMOTION:
                    vx, vy = event.value
                    if   vy ==  1: self.selected_index = (self.selected_index - 1) % len(self.options)
                    elif vy == -1: self.selected_index = (self.selected_index + 1) % len(self.options)
                elif event.type == pygame.JOYBUTTONDOWN:
                    if event.button == 0:
                        opt = self.options[self.selected_index]
                        self.result = ("QUIT", None, None) if opt[2] is None else ("START", opt[2], opt[3])
                        self.running = False
                    elif event.button == 1:
                        self.result = ("QUIT", None, None)
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

        pygame.key.set_repeat(0)
        return self.result

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self):
        self.screen.blit(self._bg, (0, 0))

        # ── Title ──
        draw_glow_text(self.screen, _t("menu_course"), self.title_font,
                       C_GLOW_CYAN, C_GLOW_CYAN,
                       (self.w // 2, self._s(32)), anchor="center", glow_radius=4)

        # Accent line
        lw = self._s(200)
        lx = (self.w - lw) // 2
        ly = self._s(88)
        for x in range(lw):
            t = 1.0 - abs(x - lw / 2) / (lw / 2 + 1)
            self.screen.set_at((lx + x, ly), (*C_GLOW_CYAN, int(60 * t)))

        # ── Panel ──
        panel_w = self._s(540)
        panel_h = self._s(370)
        px      = (self.w - panel_w) // 2
        py      = self._s(106)
        draw_glass_panel(self.screen, pygame.Rect(px, py, panel_w, panel_h),
                         border_color=(*C_GLOW_CYAN, 70), radius=14, fill_alpha=10)

        row_h   = self._s(_ROW_H_BASE)
        pad_top = self._s(12)

        for i, opt in enumerate(self.options):
            is_sel = (i == self.selected_index)
            rect   = pygame.Rect(px + self._s(10),
                                 py + pad_top + i * row_h,
                                 panel_w - self._s(20),
                                 row_h - self._s(8))

            if is_sel:
                fill   = (*C_GLOW_CYAN, 18)
                border = (*C_GLOW_CYAN, 200)
                draw_outer_glow(self.screen, rect, C_GLOW_CYAN, radius=10, passes=4, max_alpha=32)
            else:
                fill   = C_GLASS_FILL
                border = C_BORDER_DIM

            bg = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(bg, fill, (0, 0, *rect.size), border_radius=10)
            self.screen.blit(bg, rect.topleft)
            pygame.draw.rect(self.screen, border, rect, 1, border_radius=10)

            if is_sel:
                pip_h = rect.height - 16
                pygame.draw.rect(self.screen, C_GLOW_CYAN,
                                 pygame.Rect(rect.x + 4, rect.y + 8, 3, pip_h),
                                 border_radius=2)

            # Title
            title_col = C_GLOW_CYAN if is_sel else C_TEXT_PRIMARY
            self.screen.blit(self.font.render(opt[0](), True, title_col),
                             (rect.x + self._s(18), rect.y + self._s(8)))

            # Description
            desc_text = opt[1]()
            max_w = panel_w - self._s(70)
            if self.desc_font.size(desc_text)[0] > max_w:
                while self.desc_font.size(desc_text + "...")[0] > max_w and len(desc_text) > 5:
                    desc_text = desc_text[:-1]
                desc_text += "..."
            desc_col = C_TEXT_SECONDARY if is_sel else C_TEXT_DIM
            self.screen.blit(self.desc_font.render(desc_text, True, desc_col),
                             (rect.x + self._s(22), rect.y + self._s(44)))

        # ── Hint bar ──
        draw_hint_bar(self.screen, _t("course_back_hint"), self.small_font, self.h, self.w)
