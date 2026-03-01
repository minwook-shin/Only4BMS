import pygame
import time
from only4bms.i18n import get as _t, FONT_NAME
from only4bms import i18n as _i18n

# ── Colors & Aesthetics ──────────────────────────────────────────────────
COLOR_ACCENT = (0, 255, 200)
COLOR_SELECTED_BG = (40, 50, 80, 225)
COLOR_HOVERED_BG = (35, 35, 60, 160)
COLOR_TEXT_PRIMARY = (255, 255, 255)
COLOR_TEXT_SECONDARY = (180, 180, 200)
COLOR_PANEL_BG = (15, 15, 25, 230)

BASE_W, BASE_H = 800, 600

class KeyConfigMenu:
    def __init__(self, settings, renderer, window):
        from pygame._sdl2.video import Texture
        self.settings = settings
        self.renderer = renderer
        self.window = window
        self.w, self.h = window.size
        self.sx, self.sy = self.w / BASE_W, self.h / BASE_H

        self.screen = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.texture = None
        self.clock = pygame.time.Clock()

        self.title_font = _i18n.font("ui_title", self.sy, bold=True)
        self.font = _i18n.font("ui_body", self.sy)
        self.small_font = _i18n.font("ui_small", self.sy)

        self.selected_lane = 0
        self.waiting_for_input = False
        self.running = True

    def _s(self, v):
        return max(1, int(v * self.sy))

    def run(self):
        from pygame._sdl2.video import Texture
        while self.running:
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

    def _handle_events(self):
        from ..main import refresh_joysticks
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                refresh_joysticks()
            elif event.type == pygame.KEYDOWN:
                if self.waiting_for_input:
                    self.settings['keys'][self.selected_lane] = event.key
                    self.waiting_for_input = False
                    self._save()
                else:
                    if event.key == pygame.K_UP:
                        self.selected_lane = (self.selected_lane - 1) % 4
                    elif event.key == pygame.K_DOWN:
                        self.selected_lane = (self.selected_lane + 1) % 4
                    elif event.key == pygame.K_RETURN:
                        self.waiting_for_input = True
                    elif event.key in (pygame.K_ESCAPE, pygame.K_TAB):
                        self.running = False
            elif event.type == pygame.JOYBUTTONDOWN:
                if self.waiting_for_input:
                    self.settings['joystick_keys'][self.selected_lane] = f"BTN_{event.button}"
                    self.waiting_for_input = False
                    self._save()
                else:
                    if event.button == 0: # A
                        self.waiting_for_input = True
                    elif event.button == 1: # B
                        self.running = False
            elif event.type == pygame.JOYHATMOTION:
                vx, vy = event.value
                if vx == 0 and vy == 0: continue
                
                if self.waiting_for_input:
                    dir_str = ""
                    if vy == 1: dir_str = "UP"
                    elif vy == -1: dir_str = "DOWN"
                    elif vx == -1: dir_str = "LEFT"
                    elif vx == 1: dir_str = "RIGHT"
                    
                    if dir_str:
                        self.settings['joystick_keys'][self.selected_lane] = f"HAT_{event.hat}_{dir_str}"
                        self.waiting_for_input = False
                        self._save()
                else:
                    if vy == 1: # Up
                        self.selected_lane = (self.selected_lane - 1) % 4
                    elif vy == -1: # Down
                        self.selected_lane = (self.selected_lane + 1) % 4
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._on_click(event.pos)

    def _on_click(self, pos):
        mx, my = pos
        row_h = self._s(80)
        start_y = self._s(150)
        margin_l = self._s(100)
        content_w = self.w - margin_l * 2

        for i in range(4):
            rect = pygame.Rect(margin_l, start_y + i * row_h, content_w, row_h - 10)
            if rect.collidepoint(mx, my):
                if self.selected_lane == i:
                    self.waiting_for_input = True
                else:
                    self.selected_lane = i
                break

    def _save(self):
        from ..main import save_settings
        save_settings(self.settings)

    def _draw(self):
        # Background
        for y in range(self.h):
            grad = 1.0 - (y / self.h)
            c = [int(20 * grad), int(20 * grad), int(40 * grad + 20)]
            pygame.draw.line(self.screen, c, (0, y), (self.w, y))

        # Header
        title = self.title_font.render(_t("key_config_title"), True, COLOR_ACCENT)
        self.screen.blit(title, (self._s(50), self._s(40)))

        help_text = _t("key_help")
        help_surf = self.small_font.render(help_text, True, COLOR_TEXT_SECONDARY)
        self.screen.blit(help_surf, (self._s(50), self._s(95)))

        # Connection Status
        joy_count = pygame.joystick.get_count()
        joy_text = _t("joystick_connected").format(n=joy_count)
        joy_color = COLOR_ACCENT if joy_count > 0 else (255, 100, 100)
        joy_surf = self.small_font.render(joy_text, True, joy_color)
        self.screen.blit(joy_surf, (self.w - joy_surf.get_width() - self._s(50), self._s(95)))

        row_h = self._s(80)
        start_y = self._s(150)
        margin_l = self._s(100)
        content_w = self.w - margin_l * 2

        for i in range(4):
            rect = pygame.Rect(margin_l, start_y + i * row_h, content_w, row_h - 10)
            is_selected = (self.selected_lane == i)
            
            bg_color = COLOR_SELECTED_BG if is_selected else COLOR_PANEL_BG
            pygame.draw.rect(self.screen, bg_color, rect, border_radius=10)
            if is_selected:
                pygame.draw.rect(self.screen, COLOR_ACCENT, rect, 2, border_radius=10)

            # Lane Label
            label = self.font.render(_t("lane_n").format(n=i+1), True, COLOR_TEXT_PRIMARY)
            self.screen.blit(label, (rect.x + 20, rect.y + rect.h // 2 - label.get_height() // 2))

            # Bindings
            if is_selected and self.waiting_for_input:
                val_text = _t("waiting_input")
                val_color = COLOR_ACCENT
            else:
                key_name = pygame.key.name(self.settings['keys'][i]).upper()
                raw_joy = self.settings['joystick_keys'][i]
                
                # Format Joystick Display Name
                joy_display = str(raw_joy)
                if isinstance(raw_joy, str):
                    if raw_joy.startswith("BTN_"):
                        joy_display = f"BTN {raw_joy.split('_')[1]}"
                    elif raw_joy.startswith("HAT_"):
                        parts = raw_joy.split("_")
                        joy_display = f"D-PAD {parts[2]}"
                
                val_text = f"Key: {key_name}  |  Joy: {joy_display}"
                val_color = COLOR_TEXT_PRIMARY

            val_surf = self.font.render(val_text, True, val_color)
            self.screen.blit(val_surf, (rect.right - val_surf.get_width() - 20, rect.y + rect.h // 2 - val_surf.get_height() // 2))
