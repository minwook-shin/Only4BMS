import pygame
import time
from only4bms.i18n import get as _t
from only4bms import i18n as _i18n
from .components import (
    make_bg_cache, draw_glass_panel, draw_outer_glow,
    draw_glow_text, draw_hint_bar,
    C_TEXT_ACCENT, C_TEXT_PRIMARY, C_TEXT_SECONDARY, C_TEXT_DIM,
    C_GLOW_CYAN, C_GLOW_PURPLE, C_BORDER_DIM, C_BORDER_ACCENT,
    C_GLASS_FILL, C_GLASS_HOVER, C_GLASS_SELECT,
    BASE_W, BASE_H,
)

# Legacy colour exports
COLOR_ACCENT      = C_GLOW_CYAN
COLOR_SELECTED_BG = ( 40,  50,  80, 225)
COLOR_HOVERED_BG  = ( 35,  35,  60, 160)
COLOR_TEXT_PRIMARY = C_TEXT_PRIMARY
COLOR_TEXT_SECONDARY = C_TEXT_SECONDARY
COLOR_PANEL_BG    = ( 15,  15,  25, 230)


class KeyConfigMenu:
    def __init__(self, settings, renderer, window):
        from pygame._sdl2.video import Texture
        self.settings = settings
        self.renderer = renderer
        self.window   = window
        self.w, self.h = window.size
        self.sx, self.sy = self.w / BASE_W, self.h / BASE_H

        self.screen  = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.texture = None
        self._bg     = make_bg_cache(self.w, self.h)
        self.clock   = pygame.time.Clock()

        self.title_font = _i18n.font("ui_title", self.sy, bold=True)
        self.font       = _i18n.font("ui_body",  self.sy)
        self.small_font = _i18n.font("ui_small", self.sy)

        self.selected_lane      = 0
        self.waiting_for_input  = False
        self.running            = True
        self._pulse_t           = 0.0  # for waiting animation

    def _s(self, v):
        return max(1, int(v * self.sy))

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        from pygame._sdl2.video import Texture
        last_tick = pygame.time.get_ticks()
        while self.running:
            now   = pygame.time.get_ticks()
            dt    = (now - last_tick) / 1000.0
            last_tick = now
            self._pulse_t += dt

            self._handle_events()
            self._draw()
            if not self.texture:
                self.texture = Texture.from_surface(self.renderer, self.screen)
            else:
                self.texture.update(self.screen)
            self.renderer.clear()
            self.renderer.blit(self.texture, pygame.Rect(0, 0, self.w, self.h))
            self.renderer.present()
            self.clock.tick(60)
        return self.settings

    # ── Events ────────────────────────────────────────────────────────────────

    def _handle_events(self):
        from ..main import refresh_joysticks
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                refresh_joysticks()
            elif event.type == pygame.KEYDOWN:
                if self.waiting_for_input:
                    self.settings["keys"][self.selected_lane] = event.key
                    self.waiting_for_input = False
                    self._save()
                else:
                    if   event.key == pygame.K_UP:
                        self.selected_lane = (self.selected_lane - 1) % 4
                    elif event.key == pygame.K_DOWN:
                        self.selected_lane = (self.selected_lane + 1) % 4
                    elif event.key == pygame.K_RETURN:
                        self.waiting_for_input = True
                    elif event.key in (pygame.K_ESCAPE, pygame.K_TAB):
                        self.running = False
            elif event.type == pygame.JOYBUTTONDOWN:
                if self.waiting_for_input:
                    self.settings["joystick_keys"][self.selected_lane] = f"BTN_{event.button}"
                    self.waiting_for_input = False
                    self._save()
                else:
                    if   event.button == 0:
                        self.waiting_for_input = True
                    elif event.button == 1:
                        self.running = False
            elif event.type == pygame.JOYHATMOTION:
                vx, vy = event.value
                if vx == 0 and vy == 0: continue
                if self.waiting_for_input:
                    dirs = {(0,1):"UP",(0,-1):"DOWN",(-1,0):"LEFT",(1,0):"RIGHT"}
                    d = dirs.get((vx, vy), "")
                    if d:
                        self.settings["joystick_keys"][self.selected_lane] = f"HAT_{event.hat}_{d}"
                        self.waiting_for_input = False
                        self._save()
                else:
                    if   vy ==  1: self.selected_lane = (self.selected_lane - 1) % 4
                    elif vy == -1: self.selected_lane = (self.selected_lane + 1) % 4
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._on_click(event.pos)

    def _on_click(self, pos):
        mx, my = pos
        for i, rect in enumerate(self._lane_rects()):
            if rect.collidepoint(mx, my):
                if self.selected_lane == i:
                    self.waiting_for_input = True
                else:
                    self.selected_lane = i
                break

    def _save(self):
        from ..main import save_settings
        save_settings(self.settings)

    def _lane_rects(self):
        row_h    = self._s(76)
        start_y  = self._s(148)
        margin   = self._s(80)
        content_w = self.w - margin * 2
        return [pygame.Rect(margin, start_y + i * row_h, content_w, row_h - self._s(10))
                for i in range(4)]

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self):
        mx, my = pygame.mouse.get_pos()
        self.screen.blit(self._bg, (0, 0))

        # ── Header ──
        draw_glow_text(self.screen, _t("key_config_title"), self.title_font,
                       C_TEXT_ACCENT, C_GLOW_CYAN,
                       (self._s(50), self._s(30)), glow_radius=4)

        # Joystick status pill
        joy_count = pygame.joystick.get_count()
        joy_col   = C_GLOW_CYAN if joy_count > 0 else (255, 80, 100)
        joy_txt   = self.small_font.render(
            _t("joystick_connected").format(n=joy_count), True, joy_col)
        self.screen.blit(joy_txt,
                         (self.w - joy_txt.get_width() - self._s(50), self._s(38)))

        help_surf = self.small_font.render(_t("key_help"), True, C_TEXT_DIM)
        self.screen.blit(help_surf, (self._s(50), self._s(86)))

        # Separator
        sep = pygame.Surface((self.w - self._s(100), 1), pygame.SRCALPHA)
        for x in range(sep.get_width()):
            t = 1.0 - abs(x - sep.get_width() / 2) / (sep.get_width() / 2 + 1)
            sep.set_at((x, 0), (*C_GLOW_CYAN, int(35 * t)))
        self.screen.blit(sep, (self._s(50), self._s(110)))

        # ── Lane rows ──
        import math as _math
        pulse = (_math.sin(self._pulse_t * 4.0) + 1) / 2   # for waiting animation

        for i, rect in enumerate(self._lane_rects()):
            is_sel  = (i == self.selected_lane)
            is_hov  = rect.collidepoint(mx, my) and not is_sel
            waiting = is_sel and self.waiting_for_input

            if is_sel:
                fill_col   = C_GLASS_SELECT
                border_col = (*C_GLOW_CYAN, 200) if not waiting else \
                             (*C_GLOW_PURPLE, int(140 + 115 * pulse))
                draw_outer_glow(self.screen, rect, C_GLOW_CYAN if not waiting else C_GLOW_PURPLE,
                                radius=10, passes=4, max_alpha=35)
            elif is_hov:
                fill_col   = C_GLASS_HOVER
                border_col = C_BORDER_DIM
            else:
                fill_col   = C_GLASS_FILL
                border_col = C_BORDER_DIM

            panel = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(panel, fill_col, (0, 0, *rect.size), border_radius=10)
            self.screen.blit(panel, rect.topleft)
            pygame.draw.rect(self.screen, border_col, rect, 1, border_radius=10)

            # Accent pip
            if is_sel:
                pip_h = rect.height - 16
                pygame.draw.rect(self.screen,
                                 C_GLOW_CYAN if not waiting else C_GLOW_PURPLE,
                                 pygame.Rect(rect.x + 4, rect.y + 8, 3, pip_h),
                                 border_radius=2)

            # Lane label
            lbl_col = C_TEXT_ACCENT if is_sel else C_TEXT_PRIMARY
            lbl     = self.font.render(_t("lane_n").format(n=i + 1), True, lbl_col)
            self.screen.blit(lbl, (rect.x + self._s(22),
                                   rect.centery - lbl.get_height() // 2))

            # Binding text
            if waiting:
                val_text = _t("waiting_input")
                val_col  = (*C_GLOW_PURPLE, int(180 + 75 * pulse))
            else:
                key_name = pygame.key.name(self.settings["keys"][i]).upper()
                raw_joy  = self.settings["joystick_keys"][i]
                if isinstance(raw_joy, str):
                    if   raw_joy.startswith("BTN_"):
                        joy_str = f"BTN {raw_joy.split('_')[1]}"
                    elif raw_joy.startswith("HAT_"):
                        parts   = raw_joy.split("_")
                        joy_str = f"D-PAD {parts[2]}"
                    else:
                        joy_str = raw_joy
                else:
                    joy_str = str(raw_joy)
                val_text = f"{_t('key_label')}: {key_name}   |   {_t('joy_label')}: {joy_str}"
                val_col  = C_TEXT_ACCENT if is_sel else C_TEXT_SECONDARY

            val_surf = self.font.render(val_text, True, val_col)
            self.screen.blit(val_surf,
                             (rect.right - val_surf.get_width() - self._s(22),
                              rect.centery - val_surf.get_height() // 2))

        # ── Hint bar ──
        draw_hint_bar(self.screen,
                      "↑ ↓  Select Lane    ENTER / Click  Rebind    ESC  Back",
                      self.small_font, self.h, self.w)
