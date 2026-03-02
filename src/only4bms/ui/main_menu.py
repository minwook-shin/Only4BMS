import pygame
import sys
from only4bms.i18n import get as _t, FONT_NAME
from only4bms import i18n as _i18n

# ── Base (windowed) resolution ────────────────────────────────────────────
BASE_W, BASE_H = 800, 600

# ── Colors & Aesthetics ──────────────────────────────────────────────────
COLOR_ACCENT = (0, 255, 200)       # Cyan/Neon
COLOR_TEXT_PRIMARY = (255, 255, 255)
COLOR_TEXT_SECONDARY = (180, 180, 200)
COLOR_PANEL_BG = (15, 15, 25, 230)
COLOR_SELECTED_BG = (40, 50, 80, 225)
COLOR_HOVERED_BG = (35, 35, 60, 160)

class MainMenu:
    def __init__(self, settings, renderer, window):
        from pygame._sdl2.video import Texture
        self.settings = settings
        self.renderer = renderer
        self.window = window

        self.w, self.h = self.window.size
        self.sx, self.sy = self.w / BASE_W, self.h / BASE_H

        self.screen = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.texture = None

        pygame.display.set_caption("Only4BMS - Main Menu")
        self.clock = pygame.time.Clock()
        self.title_font = _i18n.font("menu_title", self.sy, bold=True)
        self.font = _i18n.font("menu_option", self.sy * 0.85)  # slightly smaller
        self.small_font = _i18n.font("menu_small", self.sy)

        self.options = [
            (lambda: _t("menu_single"), "SINGLE"),
            (lambda: _t("menu_course"), "COURSE"),
            (lambda: _t("menu_ai_multi"), "AI_MULTI"),
            (lambda: _t("menu_challenge"), "CHALLENGE"),
            (lambda: _t("menu_settings"), "SETTINGS"),
            (lambda: _t("menu_quit"), "QUIT")
        ]
        self.selected_index = 0
        self.running = True
        self.action = "QUIT"
        
        # Overlays
        self.show_quit_confirm = False
        self._quit_buttons = []

        # Input debouncing: Ignore ENTER/SPACE until released if already pressed
        self.ignore_confirm = pygame.key.get_pressed()[pygame.K_RETURN] or \
                              pygame.key.get_pressed()[pygame.K_SPACE]

        # Background Animation (Gameplay-authentic 4-lanes)
        import random
        self.bg_notes = []
        # Synchronize speed with game settings (pixels per frame in base-coords)
        fps = self.settings.get('fps', 60)
        self.bg_speed = self.settings.get('speed', 1.0) * (1000.0 / fps)
        
        for _ in range(8): # Manageable pool of notes
            self.bg_notes.append({
                'lane': random.randint(0, 3),
                'y': random.uniform(-400, 0),
                'hit': False
            })
        self.bg_judgments = [] # List of {lane, timer} for hit effects

        # Version handling
        def get_version():
            # 1. Try pyproject.toml in project root for development
            try:
                import tomllib
                import os
                curr_dir = os.path.dirname(os.path.abspath(__file__))
                for _ in range(5):
                    toml_path = os.path.join(curr_dir, "pyproject.toml")
                    if os.path.exists(toml_path):
                        with open(toml_path, "rb") as f:
                            data = tomllib.load(f)
                            return f"v{data['project']['version']}"
                    parent = os.path.dirname(curr_dir)
                    if parent == curr_dir: break
                    curr_dir = parent
            except Exception:
                pass
            # 2. Try installed package metadata
            try:
                from importlib.metadata import version
                return f"v{version('only4bms')}"
            except Exception:
                pass
            return "OSS version" # Final fallback
        self.version_str = get_version()

    def _s(self, v):
        return max(1, int(v * self.sy))

    def _cx(self, surface):
        return (self.w - surface.get_width()) // 2

    def run(self):
        from pygame._sdl2.video import Texture
        pygame.key.set_repeat(300, 50)
        # Clear events that accumulated during initialization/transition
        pygame.event.clear()
        
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

            self.clock.tick(self.settings.get('fps', 60))

        pygame.key.set_repeat(0)
        return self.action

    def _handle_events(self):
        from ..main import refresh_joysticks
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.action = "QUIT"
                self.running = False
            elif event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                refresh_joysticks()
            elif event.type == pygame.KEYUP:
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.ignore_confirm = False
            elif event.type == pygame.KEYDOWN:
                if self.show_quit_confirm:
                    if event.key == pygame.K_RETURN:
                        self.action = "QUIT"
                        self.running = False
                    elif event.key == pygame.K_ESCAPE:
                        self.show_quit_confirm = False
                    continue

                if event.key == pygame.K_UP:
                    self.selected_index = (self.selected_index - 1) % len(self.options)
                elif event.key == pygame.K_DOWN:
                    self.selected_index = (self.selected_index + 1) % len(self.options)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if not self.ignore_confirm:
                        action = self.options[self.selected_index][1]
                        if action == "QUIT":
                            self.show_quit_confirm = True
                        else:
                            self.action = action
                            self.running = False
                elif event.key == pygame.K_ESCAPE:
                    self.show_quit_confirm = True
            elif event.type == pygame.JOYBUTTONDOWN:
                if self.show_quit_confirm:
                    if event.button == 0: # A (Confirm)
                        self.action = "QUIT"
                        self.running = False
                    elif event.button == 1: # B (Back)
                        self.show_quit_confirm = False
                    continue
                
                if event.button == 0: # A
                    action = self.options[self.selected_index][1]
                    if action == "QUIT":
                        self.show_quit_confirm = True
                    else:
                        self.action = action
                        self.running = False
                elif event.button == 1: # B
                    self.show_quit_confirm = True
            elif event.type == pygame.JOYHATMOTION:
                if self.show_quit_confirm: continue
                vx, vy = event.value
                if vy == 1: # Up
                    self.selected_index = (self.selected_index - 1) % len(self.options)
                elif vy == -1: # Down
                    self.selected_index = (self.selected_index + 1) % len(self.options)
            elif event.type == pygame.MOUSEMOTION:
                if self.show_quit_confirm: continue
                mx, my = event.pos
                self._update_hover(mx, my)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if self.show_quit_confirm:
                    self._handle_quit_click(mx, my)
                    continue
                if self._update_hover(mx, my):
                    action = self.options[self.selected_index][1]
                    if action == "QUIT":
                        self.show_quit_confirm = True
                    else:
                        self.action = action
                        self.running = False

    def _update_hover(self, mx, my):
        if self.show_quit_confirm: return False
        # Center panel logic matching _draw
        panel_w, panel_h = self._s(400), self._s(390)
        start_y = (self.h - panel_h) // 2 + self._s(20)
        spacing = self._s(70)
        for i, (_, _act) in enumerate(self.options):
            rect = pygame.Rect((self.w - panel_w) // 2, start_y + i * spacing, panel_w, self._s(60))
            if rect.collidepoint(mx, my):
                self.selected_index = i
                return True
        return False

    def _handle_quit_click(self, mx, my):
        for rect, action in self._quit_buttons:
            if rect.collidepoint(mx, my):
                if action == "YES":
                    self.action = "QUIT"
                    self.running = False
                else:
                    self.show_quit_confirm = False

    def _draw_overlay(self, alpha=230):
        overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, alpha))
        self.screen.blit(overlay, (0, 0))

    def _draw_quit_confirm(self):
        self._draw_overlay(230)
        mx, my = pygame.mouse.get_pos()
        cx, cy = self.w // 2, self.h // 2

        # Glass Panel for Modal
        mw, mh = self._s(400), self._s(220)
        mx_rect, my_rect = cx - mw // 2, cy - mh // 2
        pygame.draw.rect(self.screen, COLOR_PANEL_BG, (mx_rect, my_rect, mw, mh), border_radius=10)
        pygame.draw.rect(self.screen, COLOR_ACCENT, (mx_rect, my_rect, mw, mh), 2, border_radius=10)

        msg = self.font.render(_t("quit_confirm"), True, COLOR_TEXT_PRIMARY)
        self.screen.blit(msg, msg.get_rect(center=(cx, cy - self._s(40))))

        self._quit_buttons = []
        labels = [(_t("yes"), "YES"), (_t("no"), "NO")]
        bx = cx - self._s(110)
        for label, action in labels:
            btn_rect = pygame.Rect(bx, cy + self._s(20), self._s(100), self._s(50))
            hovered = btn_rect.collidepoint(mx, my)
            
            if hovered:
                pygame.draw.rect(self.screen, COLOR_SELECTED_BG, btn_rect, border_radius=5)
                pygame.draw.rect(self.screen, COLOR_ACCENT, btn_rect, 1, border_radius=5)
                color = COLOR_ACCENT
            else:
                pygame.draw.rect(self.screen, COLOR_HOVERED_BG, btn_rect, border_radius=5)
                color = COLOR_TEXT_SECONDARY
                
            surf = self.font.render(label, True, color)
            self.screen.blit(surf, surf.get_rect(center=btn_rect.center))
            self._quit_buttons.append((btn_rect, action))
            bx += self._s(120)

    def _draw(self):
        # 1. Dark Gradient Background
        for y in range(self.h):
            grad = 1.0 - (y / self.h)
            c = [int(25 * grad), int(25 * grad), int(45 * grad + 25)]
            pygame.draw.line(self.screen, c, (0, y), (self.w, y))

        # 1.5. Subtle 4-lane Background Animation
        self._draw_bg_animation()

        # 2. Main Title (Centered Top) — rendered LAST so always on top
        title_surf = self.title_font.render("Only4BMS", True, COLOR_ACCENT)
        title_y = self._s(55)
        self.screen.blit(title_surf, (self._cx(title_surf), title_y))
        
        # 3. Center Menu Panel (Glassmorphism) — starts below title
        panel_w, panel_h = self._s(400), self._s(390)
        title_bottom = title_y + title_surf.get_height() + self._s(18)
        py = title_bottom
        px = (self.w - panel_w) // 2
        
        # Panel Background
        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill(COLOR_PANEL_BG)
        self.screen.blit(panel_surf, (px, py))
        pygame.draw.rect(self.screen, COLOR_ACCENT, (px, py, panel_w, panel_h), 2)

        # 4. Menu Options
        mx, my = pygame.mouse.get_pos()
        item_spacing = self._s(58)
        opt_start_y = py + self._s(15)
        
        for i, (label_fn, _) in enumerate(self.options):
            item_rect = pygame.Rect(px + self._s(10), opt_start_y + i * item_spacing, panel_w - self._s(20), self._s(50))
            
            # Hover/Select Highlight
            if i == self.selected_index:
                pygame.draw.rect(self.screen, COLOR_SELECTED_BG, item_rect)
                pygame.draw.rect(self.screen, COLOR_ACCENT, item_rect, 1)
                txt_color = COLOR_ACCENT
            elif item_rect.collidepoint(mx, my):
                pygame.draw.rect(self.screen, COLOR_HOVERED_BG, item_rect)
                txt_color = COLOR_TEXT_PRIMARY
            else:
                txt_color = COLOR_TEXT_SECONDARY
                
            label_surf = self.font.render(label_fn(), True, txt_color)
            ly = item_rect.centery - label_surf.get_height() // 2
            self.screen.blit(label_surf, (self._cx(label_surf), ly))
            
        # 5. Bottom Copyright & Version
        copy_surf = self.small_font.render("© 2026 Only4BMS", True, (100, 100, 120))
        self.screen.blit(copy_surf, (self._cx(copy_surf), self.h - self._s(40)))

        version_surf = self.small_font.render(self.version_str, True, (100, 100, 120))
        self.screen.blit(version_surf, (self.w - version_surf.get_width() - self._s(20), self.h - self._s(40)))

        if self.show_quit_confirm:
            self._draw_quit_confirm()

    def _update_bg_animation(self):
        """Move notes down and recycle them."""
        import random
        import time
        hit_y = 500 # BASE_H constant from game
        now = pygame.time.get_ticks()

        for note in self.bg_notes:
            note['y'] += self.bg_speed
            
            # Simulate Hit when reaching hit_y
            if not note['hit'] and note['y'] >= hit_y:
                note['hit'] = True
                self.bg_judgments.append({'lane': note['lane'], 'timer': now})
                # Clean up old judgments
                if len(self.bg_judgments) > 10: self.bg_judgments.pop(0)

            if note['y'] > BASE_H + 50:
                note['y'] = random.uniform(-400, -50)
                note['lane'] = random.randint(0, 3)
                note['hit'] = False

    def _draw_bg_animation(self):
        self._update_bg_animation()
        now = pygame.time.get_ticks()
        
        lane_w = self._s(75) # Authentic LANE_W
        total_w = lane_w * 4
        start_x = (self.w - total_w) // 2
        hit_y_scaled = self._s(500) # Authentic HIT_Y
        
        # 1. Lane BG and Lines (Subtle)
        line_color = (COLOR_ACCENT[0], COLOR_ACCENT[1], COLOR_ACCENT[2], 8)
        bg_color = (30, 30, 40, 6)
        pygame.draw.rect(self.screen, bg_color, (start_x, 0, total_w, self.h))
        for i in range(5):
            lx = start_x + i * lane_w
            pygame.draw.line(self.screen, line_color, (lx, 0), (lx, self.h), 1)

        # 2. Judgment Line (Pulsing Red)
        import math
        pulse = (math.sin(now / 300.0) + 1) / 2
        hit_alpha = int(25 + pulse * 25)
        pygame.draw.rect(self.screen, (255, 40, 40, hit_alpha), (start_x, hit_y_scaled - self._s(15), total_w, self._s(30)))
        pygame.draw.rect(self.screen, (255, 100, 100, hit_alpha + 20), (start_x, hit_y_scaled - self._s(15), total_w, self._s(30)), 1)

        # 3. Hit Effects (Flashes and PERFECT!)
        for j in self.bg_judgments[:]:
            elapsed = now - j['timer']
            if elapsed > 500:
                self.bg_judgments.remove(j)
                continue
            
            # Flash
            flash_alpha = int(40 * (1.0 - elapsed / 500.0))
            fx = start_x + j['lane'] * lane_w
            pygame.draw.rect(self.screen, (255, 255, 255, flash_alpha), (fx, 0, lane_w, hit_y_scaled))
            
            # PERFECT! Text with bounce
            t = elapsed / 200.0
            scale = 1.0
            if t < 1.0: scale = 1.4 - 0.4 * (1 - (1 - t)**2)
            
            msg_surf = self.small_font.render(_t("judgment_perfect"), True, (0, 255, 255))
            if scale != 1.0:
                mw, mh = msg_surf.get_size()
                msg_surf = pygame.transform.smoothscale(msg_surf, (int(mw * scale), int(mh * scale)))
            
            msg_rect = msg_surf.get_rect(center=(start_x + total_w // 2, self.h // 2 - self._s(80)))
            msg_surf.set_alpha(int(100 * (1.0 - elapsed / 500.0)))
            self.screen.blit(msg_surf, msg_rect)

        # 4. Falling Notes (Authentic Styling)
        note_alpha = 40
        note_h = self._s(20)
        for note in self.bg_notes:
            if note['hit']: continue
            nx = start_x + note['lane'] * lane_w + self._s(2)
            ny = int(note['y'] * self.sy)
            nw = lane_w - self._s(4)
            
            if ny + note_h < 0 or ny > self.h: continue

            # Core Note (Cyan)
            pygame.draw.rect(self.screen, (0, 255, 255, note_alpha), (nx, ny, nw, note_h - 2), border_radius=2)
            # Gloss (White Top)
            pygame.draw.rect(self.screen, (255, 255, 255, int(note_alpha * 0.5)), (nx, ny, nw, 2))
            # Bottom Shadow
            pygame.draw.rect(self.screen, (0, 0, 0, int(note_alpha * 0.7)), (nx, ny + note_h - 4, nw, 4))
