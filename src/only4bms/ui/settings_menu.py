import pygame

# ── Colors & Aesthetics ──────────────────────────────────────────────────
COLOR_ACCENT = (0, 255, 200)       # Cyan/Neon
COLOR_ACCENT_DIM = (0, 150, 120)
COLOR_SELECTED_BG = (40, 50, 80, 225)
COLOR_HOVERED_BG = (35, 35, 60, 160)
COLOR_TEXT_PRIMARY = (255, 255, 255)
COLOR_TEXT_SECONDARY = (180, 180, 200)
COLOR_PANEL_BG = (15, 15, 25, 230)

BASE_W, BASE_H = 800, 600
MAX_CHOICE_NAME_LEN = 30
INT_KEYS = frozenset(("fps", "audio_freq", "audio_buffer", "audio_channels"))


class SettingsMenu:
    def __init__(self, settings, renderer, window):
        from pygame._sdl2.video import Texture
        self.renderer = renderer
        self.window = window
        
        self.w, self.h = self.window.size
        self.sx, self.sy = self.w / BASE_W, self.h / BASE_H  # scale factors
        
        # Offscreen surface for hybrid rendering
        self.screen = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.texture = None
        
        pygame.display.set_caption("Settings")
        self.clock = pygame.time.Clock()
        self.title_font = pygame.font.SysFont("Outfit, Roboto, sans-serif", self._s(44), bold=True)
        self.font = pygame.font.SysFont("Outfit, Roboto, sans-serif", self._s(32))
        self.small_font = pygame.font.SysFont("Outfit, Roboto, sans-serif", self._s(22))

        self.settings = settings
        self.items = [
            # SYSTEM Category
            {"type": "category", "label": "SYSTEM"},
            {"key": "fps",             "label": "FPS Limit",             "step": 10,  "min": 30,    "max": 360},
            {"key": "fullscreen",      "label": "Fullscreen",            "type": "choice", "choices_key": "_fullscreen_opts"},
            {"key": "audio_device_idx","label": "Audio Device",          "type": "choice", "choices_key": "audio_devices"},
            
            # AUDIO Category
            {"type": "category", "label": "AUDIO"},
            {"key": "volume",          "label": "Global Volume",         "step": 0.1, "min": 0.0,   "max": 1.0},
            {"key": "audio_freq",      "label": "Sample Rate (Hz)",      "step": 100, "min": 22050, "max": 48000},
            {"key": "audio_buffer",    "label": "Audio Buffer",          "step": 256, "min": 256,   "max": 4096},
            {"key": "audio_channels",  "label": "Audio Channels",        "step": 1,   "min": 1,     "max": 2},
            
            # GAMEPLAY Category
            {"type": "category", "label": "GAMEPLAY"},
            {"key": "speed",           "label": "Scroll Speed",          "step": 0.1, "min": 0.1,   "max": 2.0},
            {"key": "hit_window_mult", "label": "Hit Window Multiplier", "step": 0.1, "min": 0.5,   "max": 3.0},
            {"key": "judge_delay",     "label": "Judge Delay (ms)",     "step": 1,   "min": -200,  "max": 200},
            {"key": "note_type",       "label": "Note Appearance (Player)", "type": "choice", "choices_key": "_note_type_opts"},
            {"key": "ai_note_type",    "label": "Note Appearance (AI)",     "type": "choice", "choices_key": "_note_type_opts"},
        ]
        self.settings.setdefault("_fullscreen_opts", ["Off", "On"])
        self.settings.setdefault("_note_type_opts", ["Bar", "Circle"])
        self.settings.setdefault("fullscreen", 0)
        self.settings.setdefault("note_type", 0)
        self.settings.setdefault("note_type", 0)
        self.settings.setdefault("ai_note_type", 0)
        self.selected_index = 1 # Start at first setting, skip SYSTEM header
        self.view_offset = 0
        self.max_visible = 6 # Reduced to 6 to prevent footer overlap
        self.running = True

    def _s(self, v):
        """Scale a base-800x600 value to current resolution."""
        return max(1, int(v * self.sy))

    # ── Value helpers ─────────────────────────────────────────────────────

    def _adjust(self, item, direction):
        if item.get("type") == "choice":
            choices = self.settings.get(item["choices_key"], ["Default"])
            idx = (self.settings.get(item["key"], 0) + direction) % len(choices)
            self.settings[item["key"]] = idx
        else:
            val = self.settings.get(item["key"])
            self.settings[item["key"]] = max(item["min"], min(item["max"], round(val + item["step"] * direction, 2)))
        
        # Save on every adjustment for better persistence
        from ..main import save_settings
        save_settings(self.settings)

    def _format_value(self, item):
        if item.get("type") == "choice":
            choices = self.settings.get(item["choices_key"], ["Default"])
            idx = self.settings.get(item["key"], 0)
            name = choices[idx] if idx < len(choices) else "Default"
            return (name[:MAX_CHOICE_NAME_LEN - 2] + "..") if len(name) > MAX_CHOICE_NAME_LEN else name
        if item["key"] in INT_KEYS:
            return str(int(self.settings[item["key"]]))
        return f"{self.settings[item['key']]:.1f}"

    @staticmethod
    def _row_color(index, selected, hovered):
        if index == selected:
            return COLOR_ACCENT
        return COLOR_TEXT_PRIMARY if hovered else COLOR_TEXT_SECONDARY

    # ── Main loop ─────────────────────────────────────────────────────────

    def run(self):
        from pygame._sdl2.video import Texture
        pygame.key.set_repeat(300, 50)
        while self.running:
            self._handle_events()
            self._draw()
            
            # Hybrid GPU presentation
            if not self.texture:
                self.texture = Texture.from_surface(self.renderer, self.screen)
            else:
                self.texture.update(self.screen)
            
            self.renderer.clear()
            self.renderer.blit(self.texture, pygame.Rect(0, 0, self.w, self.h))
            self.renderer.present()

            self.clock.tick(self.settings.get('fps', 60))
            
        pygame.key.set_repeat(0)
        return self.settings

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._on_key(event.key)
            elif event.type == pygame.MOUSEWHEEL:
                self._adjust(self.items[self.selected_index], event.y)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._on_click(event.pos)

    def _on_key(self, key):
        if key == pygame.K_UP and self.selected_index > 1: # Can't go to index 0 (SYSTEM header)
            self.selected_index -= 1
            # Skip categories when navigating up
            if self.items[self.selected_index].get("type") == "category":
                self.selected_index -= 1
            
            if self.selected_index < self.view_offset:
                self.view_offset = self.selected_index
        elif key == pygame.K_DOWN and self.selected_index < len(self.items) - 1:
            self.selected_index += 1
            # Skip categories when navigating
            if self.items[self.selected_index].get("type") == "category":
                if self.selected_index < len(self.items) - 1:
                    self.selected_index += 1
                else:
                    self.selected_index -= 1 # Backtrack if at end
            
            if self.selected_index >= self.view_offset + self.max_visible:
                self.view_offset = self.selected_index - self.max_visible + 1
        elif key == pygame.K_LEFT:
            self._adjust(self.items[self.selected_index], -1)
        elif key == pygame.K_RIGHT:
            self._adjust(self.items[self.selected_index], +1)
        elif key in (pygame.K_ESCAPE, pygame.K_TAB):
            self.running = False

    def _on_click(self, pos):
        mx, my = pos
        row_h = self._s(60)
        start_y = self._s(120)
        margin_l, margin_r = self._s(50), self.w - self._s(50)
        for i in range(self.view_offset, min(len(self.items), self.view_offset + self.max_visible)):
            if self.items[i].get("type") == "category":
                continue # Headers are not clickable for selection

            ry = start_y + (i - self.view_offset) * row_h
            if margin_l <= mx <= margin_r and ry <= my <= ry + self._s(40):
                self.selected_index = i
                break

    # ── Drawing ───────────────────────────────────────────────────────────

    def _draw(self):
        # Commercial Dark Gradient Background
        for y in range(self.h):
            grad = 1.0 - (y / self.h)
            c = [int(30 * grad), int(30 * grad), int(50 * grad + 30)]
            pygame.draw.line(self.screen, c, (0, y), (self.w, y))

        # Header Title
        self.screen.blit(
            self.title_font.render("SYSTEM SETTINGS", True, COLOR_ACCENT),
            (self._s(50), self._s(40)))

        mx, my = pygame.mouse.get_pos()
        row_h = self._s(65)
        start_y = self._s(120)
        margin_l = self._s(50)
        content_w = self.w - margin_l * 2
        
        # Panel Background
        panel_rect = (margin_l - 10, start_y - 10, content_w + 20, self.max_visible * row_h + 20)
        pygame.draw.rect(self.screen, COLOR_PANEL_BG, panel_rect, border_radius=15)
        pygame.draw.rect(self.screen, COLOR_HOVERED_BG, panel_rect, 1, border_radius=15)

        y = start_y
        for i in range(self.view_offset, min(len(self.items), self.view_offset + self.max_visible)):
            item = self.items[i]
            
            if item.get("type") == "category":
                # Category Header
                rect = pygame.Rect(margin_l, y, content_w, row_h - 5)
                pygame.draw.rect(self.screen, (COLOR_ACCENT[0], COLOR_ACCENT[1], COLOR_ACCENT[2], 25), rect, border_radius=8)
                txt = self.small_font.render(item['label'], True, COLOR_ACCENT)
                self.screen.blit(txt, txt.get_rect(center=(margin_l + content_w // 2, y + row_h // 2)))
                y += row_h
                continue

            rect = pygame.Rect(margin_l, y, content_w, row_h - 5)
            hovered = rect.collidepoint(mx, my) or i == self.selected_index
            
            if i == self.selected_index:
                pygame.draw.rect(self.screen, COLOR_SELECTED_BG, rect, border_radius=8)
                pygame.draw.rect(self.screen, COLOR_ACCENT, rect, 2, border_radius=8)
            elif hovered:
                pygame.draw.rect(self.screen, COLOR_HOVERED_BG, rect, border_radius=8)

            color = self._row_color(i, self.selected_index, rect.collidepoint(mx, my))
            
            # Label
            lbl_surf = self.font.render(item['label'], True, color)
            self.screen.blit(lbl_surf, (margin_l + 20, y + 15))
            
            # Value Box
            val_text = self._format_value(item)
            val_surf = self.font.render(f"<  {val_text}  >", True, COLOR_ACCENT if i == self.selected_index else COLOR_TEXT_PRIMARY)
            val_rect = val_surf.get_rect(midright=(margin_l + content_w - 20, y + row_h // 2))
            self.screen.blit(val_surf, val_rect)

            y += row_h
