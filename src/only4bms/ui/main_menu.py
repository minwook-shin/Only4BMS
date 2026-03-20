import pygame
import sys
from only4bms.i18n import get as _t, FONT_NAME
from only4bms import i18n as _i18n

# ── Base (windowed) resolution ────────────────────────────────────────────
BASE_W, BASE_H = 800, 600

# ── Colors & Aesthetics ──────────────────────────────────────────────────
COLOR_ACCENT = (0, 255, 200)       # Cyan/Neon
COLOR_MOD_ACCENT = (180, 120, 255) # Purple — mod entries stand out subtly
COLOR_TEXT_PRIMARY = (255, 255, 255)
COLOR_TEXT_SECONDARY = (180, 180, 200)
COLOR_PANEL_BG = (15, 15, 25, 230)
COLOR_SELECTED_BG = (40, 50, 80, 225)
COLOR_HOVERED_BG = (35, 35, 60, 160)
COLOR_MOD_SELECTED_BG = (50, 30, 80, 225)
COLOR_MOD_HOVERED_BG  = (40, 25, 65, 160)

# ── Layout constants (in BASE coords, scaled by sy) ──────────────────────
_ITEM_SPACING_BASE = 56   # px per menu item at 1x scale
_ITEM_H_BASE       = 48   # item hit-box height
_PANEL_W_BASE      = 400
_PANEL_PAD_TOP     = 14   # inner top padding
_PANEL_PAD_BOT     = 10   # inner bottom padding
_TITLE_Y_BASE      = 55
_TITLE_MARGIN      = 18   # gap between title bottom and panel top


class MainMenu:
    def __init__(self, settings, renderer, window, mods=None):
        """
        Parameters
        ----------
        mods : list[ModInfo] | None
            Discovered mods from mod_loader.discover_mods().
            Shown in a popup overlay when the player selects MODS.
        """
        from pygame._sdl2.video import Texture
        self.settings = settings
        self.renderer = renderer
        self.window = window
        self.mods = mods or []

        self.w, self.h = self.window.size
        self.sx, self.sy = self.w / BASE_W, self.h / BASE_H

        self.screen = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.texture = None

        pygame.display.set_caption("Only4BMS - Main Menu")
        self.clock = pygame.time.Clock()
        self.title_font = _i18n.font("menu_title", self.sy, bold=True)
        self.font = _i18n.font("menu_option", self.sy * 0.85)
        self.small_font = _i18n.font("menu_small", self.sy)

        # ── Build options list ──────────────────────────────────────────
        self.options = [
            (lambda: _t("menu_single"), "SINGLE"),
        ]
        self.is_mod = [False]

        if self.mods:
            self.options.append((lambda: _t("menu_mods"), "MODS"))
            self.is_mod.append(True)

        self.options += [
            (lambda: _t("menu_challenge"), "CHALLENGE"),
            (lambda: _t("menu_settings"), "SETTINGS"),
            (lambda: _t("menu_quit"), "QUIT"),
        ]
        self.is_mod += [False, False, False]

        self.selected_index = 0
        self.running = True
        self.action = "QUIT"

        # Overlays
        self.show_quit_confirm = False
        self._quit_buttons = []

        # Mods popup
        self.show_mods_popup = False
        self.mods_popup_index = 0
        self._mod_item_rects = []

        # Input debouncing
        self.ignore_confirm = (pygame.key.get_pressed()[pygame.K_RETURN] or
                               pygame.key.get_pressed()[pygame.K_SPACE])

        # Background Animation
        import random
        self.bg_notes = []
        fps = self.settings.get('fps', 60)
        self.bg_speed = self.settings.get('speed', 1.0) * (1000.0 / fps)
        for _ in range(8):
            self.bg_notes.append({
                'lane': random.randint(0, 3),
                'y': random.uniform(-400, 0),
                'hit': False
            })
        self.bg_judgments = []

        # Version
        self.version_str = self._detect_version()

    # ── Helpers ──────────────────────────────────────────────────────────

    def _s(self, v):
        return max(1, int(v * self.sy))

    def _cx(self, surface):
        return (self.w - surface.get_width()) // 2

    def _detect_version(self):
        try:
            import tomllib, os
            curr_dir = os.path.dirname(os.path.abspath(__file__))
            for _ in range(5):
                toml_path = os.path.join(curr_dir, "pyproject.toml")
                if os.path.exists(toml_path):
                    with open(toml_path, "rb") as f:
                        data = tomllib.load(f)
                        return f"v{data['project']['version']}"
                parent = os.path.dirname(curr_dir)
                if parent == curr_dir:
                    break
                curr_dir = parent
        except Exception:
            pass
        try:
            from importlib.metadata import version
            return f"v{version('only4bms')}"
        except Exception:
            pass
        return "OSS version"

    def _layout(self):
        """
        Compute consistent panel geometry used by both _draw and _update_hover.

        Returns
        -------
        (px, py, panel_w, panel_h, item_spacing, opt_start_y)
        All values are already scaled (pixels on the actual window).
        """
        n = len(self.options)

        # Approximate title height to find where the panel starts
        # menu_title font size is 76 base units (see i18n.py FONT_SIZES)
        title_h_approx = self._s(76)
        title_bottom = self._s(_TITLE_Y_BASE) + title_h_approx + self._s(_TITLE_MARGIN)

        available_h = self.h - title_bottom - self._s(50)  # reserve footer
        # Shrink spacing if many items, min 40px
        item_spacing = max(self._s(40), min(self._s(_ITEM_SPACING_BASE),
                                            (available_h - self._s(_PANEL_PAD_TOP + _PANEL_PAD_BOT)) // n))

        panel_w = self._s(_PANEL_W_BASE)
        panel_h = self._s(_PANEL_PAD_TOP) + n * item_spacing + self._s(_PANEL_PAD_BOT)
        px = (self.w - panel_w) // 2
        py = title_bottom
        opt_start_y = py + self._s(_PANEL_PAD_TOP)

        return px, py, panel_w, panel_h, item_spacing, opt_start_y

    # ── Main loop ─────────────────────────────────────────────────────────

    def run(self):
        from pygame._sdl2.video import Texture
        pygame.key.set_repeat(300, 50)
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

    # ── Event handling ────────────────────────────────────────────────────

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
                if self.show_mods_popup:
                    self._handle_mods_popup_key(event.key)
                    continue

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
                        self._activate(self.options[self.selected_index][1])
                elif event.key == pygame.K_ESCAPE:
                    self.show_quit_confirm = True

            elif event.type == pygame.JOYBUTTONDOWN:
                if self.show_mods_popup:
                    if event.button == 0:
                        self._launch_mod(self.mods_popup_index)
                    elif event.button == 1:
                        self.show_mods_popup = False
                    continue

                if self.show_quit_confirm:
                    if event.button == 0:
                        self.action = "QUIT"
                        self.running = False
                    elif event.button == 1:
                        self.show_quit_confirm = False
                    continue
                if event.button == 0:
                    self._activate(self.options[self.selected_index][1])
                elif event.button == 1:
                    self.show_quit_confirm = True

            elif event.type == pygame.JOYHATMOTION:
                if self.show_mods_popup:
                    vx, vy = event.value
                    if vy == 1:
                        self.mods_popup_index = (self.mods_popup_index - 1) % len(self.mods)
                    elif vy == -1:
                        self.mods_popup_index = (self.mods_popup_index + 1) % len(self.mods)
                    continue
                if self.show_quit_confirm:
                    continue
                vx, vy = event.value
                if vy == 1:
                    self.selected_index = (self.selected_index - 1) % len(self.options)
                elif vy == -1:
                    self.selected_index = (self.selected_index + 1) % len(self.options)

            elif event.type == pygame.MOUSEMOTION:
                if self.show_mods_popup:
                    self._update_mods_hover(*event.pos)
                    continue
                if self.show_quit_confirm:
                    continue
                self._update_hover(*event.pos)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if self.show_mods_popup:
                    self._handle_mods_popup_click(mx, my)
                    continue
                if self.show_quit_confirm:
                    self._handle_quit_click(mx, my)
                    continue
                if self._update_hover(mx, my):
                    self._activate(self.options[self.selected_index][1])

    def _handle_mods_popup_key(self, key):
        if key == pygame.K_ESCAPE:
            self.show_mods_popup = False
        elif key == pygame.K_UP:
            self.mods_popup_index = (self.mods_popup_index - 1) % len(self.mods)
        elif key == pygame.K_DOWN:
            self.mods_popup_index = (self.mods_popup_index + 1) % len(self.mods)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self._launch_mod(self.mods_popup_index)

    def _handle_mods_popup_click(self, mx, my):
        # Click outside popup closes it
        popup_rect = self._mods_popup_rect()
        if not popup_rect.collidepoint(mx, my):
            self.show_mods_popup = False
            return
        for i, rect in enumerate(self._mod_item_rects):
            if rect.collidepoint(mx, my):
                if self.mods_popup_index == i:
                    self._launch_mod(i)
                else:
                    self.mods_popup_index = i
                return

    def _update_mods_hover(self, mx, my):
        for i, rect in enumerate(self._mod_item_rects):
            if rect.collidepoint(mx, my):
                self.mods_popup_index = i
                return

    def _launch_mod(self, index):
        self.action = self.mods[index].action
        self.running = False

    def _activate(self, action):
        if action == "QUIT":
            self.show_quit_confirm = True
        elif action == "MODS":
            self.mods_popup_index = 0
            self.show_mods_popup = True
        else:
            self.action = action
            self.running = False

    def _update_hover(self, mx, my):
        """Return True if mouse is over any option (and update selected_index)."""
        if self.show_quit_confirm:
            return False
        px, py, panel_w, panel_h, item_spacing, opt_start_y = self._layout()
        item_h = self._s(_ITEM_H_BASE)
        for i in range(len(self.options)):
            rect = pygame.Rect(px, opt_start_y + i * item_spacing, panel_w, item_h)
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

    # ── Drawing ───────────────────────────────────────────────────────────

    def _draw_overlay(self, alpha=230):
        overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, alpha))
        self.screen.blit(overlay, (0, 0))

    def _draw_quit_confirm(self):
        self._draw_overlay(230)
        mx, my = pygame.mouse.get_pos()
        cx, cy = self.w // 2, self.h // 2

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

    def _mods_popup_rect(self):
        popup_w = self._s(440)
        popup_h = self._s(80 + max(len(self.mods), 1) * 54 + 52)
        popup_x = (self.w - popup_w) // 2
        popup_y = (self.h - popup_h) // 2
        return pygame.Rect(popup_x, popup_y, popup_w, popup_h)

    def _draw_mods_popup(self):
        self._draw_overlay(180)
        mx, my = pygame.mouse.get_pos()

        popup_rect = self._mods_popup_rect()
        px, py, pw, ph = popup_rect.x, popup_rect.y, popup_rect.width, popup_rect.height

        # Panel background
        panel_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel_surf.fill(COLOR_PANEL_BG)
        self.screen.blit(panel_surf, (px, py))
        pygame.draw.rect(self.screen, COLOR_MOD_ACCENT, (px, py, pw, ph), 2, border_radius=10)

        # Title bar
        title_surf = self.font.render(_t("menu_mods"), True, COLOR_MOD_ACCENT)
        self.screen.blit(title_surf, title_surf.get_rect(centerx=px + pw // 2, top=py + self._s(14)))

        # Divider
        div_y = py + self._s(46)
        pygame.draw.line(self.screen, (80, 50, 120), (px + self._s(16), div_y), (px + pw - self._s(16), div_y), 1)

        # Mod list items
        item_h = self._s(48)
        item_spacing = self._s(54)
        list_top = div_y + self._s(8)
        self._mod_item_rects = []

        for i, mod in enumerate(self.mods):
            name_fn = mod.name_fn if mod.name_fn else (lambda n=mod.name: n)
            item_rect = pygame.Rect(px + self._s(12), list_top + i * item_spacing,
                                    pw - self._s(24), item_h)
            self._mod_item_rects.append(item_rect)

            if i == self.mods_popup_index:
                pygame.draw.rect(self.screen, COLOR_MOD_SELECTED_BG, item_rect, border_radius=6)
                pygame.draw.rect(self.screen, COLOR_MOD_ACCENT, item_rect, 1, border_radius=6)
                txt_color = COLOR_MOD_ACCENT
            elif item_rect.collidepoint(mx, my):
                pygame.draw.rect(self.screen, COLOR_MOD_HOVERED_BG, item_rect, border_radius=6)
                txt_color = COLOR_TEXT_PRIMARY
            else:
                txt_color = COLOR_TEXT_SECONDARY

            label_surf = self.font.render(name_fn(), True, txt_color)
            self.screen.blit(label_surf, label_surf.get_rect(
                centery=item_rect.centery,
                centerx=item_rect.centerx,
            ))

        # Hint text at bottom (small, dim)
        hint_text = _t("mods_popup_hint")
        hint_surf = self.small_font.render(hint_text, True, (80, 60, 110))
        hint_y = py + ph - self._s(30)
        pygame.draw.line(self.screen, (50, 35, 75),
                         (px + self._s(16), hint_y - self._s(6)),
                         (px + pw - self._s(16), hint_y - self._s(6)), 1)
        self.screen.blit(hint_surf, hint_surf.get_rect(centerx=px + pw // 2, top=hint_y))

    def _draw(self):
        # 1. Dark gradient background
        for y in range(self.h):
            grad = 1.0 - (y / self.h)
            c = [int(25 * grad), int(25 * grad), int(45 * grad + 25)]
            pygame.draw.line(self.screen, c, (0, y), (self.w, y))

        # 2. Subtle lane animation
        self._draw_bg_animation()

        # 3. Title
        title_surf = self.title_font.render("Only4BMS", True, COLOR_ACCENT)
        title_y = self._s(_TITLE_Y_BASE)
        self.screen.blit(title_surf, (self._cx(title_surf), title_y))

        # 4. Menu panel
        px, py, panel_w, panel_h, item_spacing, opt_start_y = self._layout()

        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill(COLOR_PANEL_BG)
        self.screen.blit(panel_surf, (px, py))
        border_color = COLOR_ACCENT
        pygame.draw.rect(self.screen, border_color, (px, py, panel_w, panel_h), 2)

        # 5. Options
        mx, my = pygame.mouse.get_pos()
        item_h = self._s(_ITEM_H_BASE)

        for i, (label_fn, _) in enumerate(self.options):
            is_mod_entry = self.is_mod[i]
            item_rect = pygame.Rect(
                px + self._s(10),
                opt_start_y + i * item_spacing,
                panel_w - self._s(20),
                item_h,
            )

            accent = COLOR_MOD_ACCENT if is_mod_entry else COLOR_ACCENT

            if i == self.selected_index:
                bg = COLOR_MOD_SELECTED_BG if is_mod_entry else COLOR_SELECTED_BG
                pygame.draw.rect(self.screen, bg, item_rect)
                pygame.draw.rect(self.screen, accent, item_rect, 1)
                txt_color = accent
            elif item_rect.collidepoint(mx, my):
                bg = COLOR_MOD_HOVERED_BG if is_mod_entry else COLOR_HOVERED_BG
                pygame.draw.rect(self.screen, bg, item_rect)
                txt_color = COLOR_TEXT_PRIMARY
            else:
                txt_color = COLOR_TEXT_SECONDARY

            label_surf = self.font.render(label_fn(), True, txt_color)
            ly = item_rect.centery - label_surf.get_height() // 2
            self.screen.blit(label_surf, (self._cx(label_surf), ly))

        # 6. Footer
        copy_surf = self.small_font.render("© 2026 Only4BMS", True, (100, 100, 120))
        self.screen.blit(copy_surf, (self._cx(copy_surf), self.h - self._s(40)))
        version_surf = self.small_font.render(self.version_str, True, (100, 100, 120))
        self.screen.blit(version_surf, (self.w - version_surf.get_width() - self._s(20), self.h - self._s(40)))

        if self.show_quit_confirm:
            self._draw_quit_confirm()
        elif self.show_mods_popup:
            self._draw_mods_popup()

    # ── Background animation ──────────────────────────────────────────────

    def _update_bg_animation(self):
        import random
        hit_y = 500
        now = pygame.time.get_ticks()
        for note in self.bg_notes:
            note['y'] += self.bg_speed
            if not note['hit'] and note['y'] >= hit_y:
                note['hit'] = True
                self.bg_judgments.append({'lane': note['lane'], 'timer': now})
                if len(self.bg_judgments) > 10:
                    self.bg_judgments.pop(0)
            if note['y'] > BASE_H + 50:
                note['y'] = random.uniform(-400, -50)
                note['lane'] = random.randint(0, 3)
                note['hit'] = False

    def _draw_bg_animation(self):
        self._update_bg_animation()
        now = pygame.time.get_ticks()

        lane_w = self._s(75)
        total_w = lane_w * 4
        start_x = (self.w - total_w) // 2
        hit_y_scaled = self._s(500)

        line_color = (COLOR_ACCENT[0], COLOR_ACCENT[1], COLOR_ACCENT[2], 8)
        bg_color = (30, 30, 40, 6)
        pygame.draw.rect(self.screen, bg_color, (start_x, 0, total_w, self.h))
        for i in range(5):
            lx = start_x + i * lane_w
            pygame.draw.line(self.screen, line_color, (lx, 0), (lx, self.h), 1)

        import math
        pulse = (math.sin(now / 300.0) + 1) / 2
        hit_alpha = int(25 + pulse * 25)
        pygame.draw.rect(self.screen, (255, 40, 40, hit_alpha),
                         (start_x, hit_y_scaled - self._s(15), total_w, self._s(30)))
        pygame.draw.rect(self.screen, (255, 100, 100, hit_alpha + 20),
                         (start_x, hit_y_scaled - self._s(15), total_w, self._s(30)), 1)

        for j in self.bg_judgments[:]:
            elapsed = now - j['timer']
            if elapsed > 500:
                self.bg_judgments.remove(j)
                continue
            flash_alpha = int(40 * (1.0 - elapsed / 500.0))
            fx = start_x + j['lane'] * lane_w
            pygame.draw.rect(self.screen, (255, 255, 255, flash_alpha),
                             (fx, 0, lane_w, hit_y_scaled))
            t = elapsed / 200.0
            scale = 1.0
            if t < 1.0:
                scale = 1.4 - 0.4 * (1 - (1 - t) ** 2)
            msg_surf = self.small_font.render(_t("judgment_perfect"), True, (0, 255, 255))
            if scale != 1.0:
                mw, mh = msg_surf.get_size()
                msg_surf = pygame.transform.smoothscale(msg_surf,
                                                        (int(mw * scale), int(mh * scale)))
            msg_rect = msg_surf.get_rect(center=(start_x + total_w // 2,
                                                  self.h // 2 - self._s(80)))
            msg_surf.set_alpha(int(100 * (1.0 - elapsed / 500.0)))
            self.screen.blit(msg_surf, msg_rect)

        note_alpha = 40
        note_h = self._s(20)
        for note in self.bg_notes:
            if note['hit']:
                continue
            nx = start_x + note['lane'] * lane_w + self._s(2)
            ny = int(note['y'] * self.sy)
            nw = lane_w - self._s(4)
            if ny + note_h < 0 or ny > self.h:
                continue
            pygame.draw.rect(self.screen, (0, 255, 255, note_alpha),
                             (nx, ny, nw, note_h - 2), border_radius=2)
            pygame.draw.rect(self.screen, (255, 255, 255, int(note_alpha * 0.5)),
                             (nx, ny, nw, 2))
            pygame.draw.rect(self.screen, (0, 0, 0, int(note_alpha * 0.7)),
                             (nx, ny + note_h - 4, nw, 4))
