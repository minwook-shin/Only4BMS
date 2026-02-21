import pygame

# ── Colors ────────────────────────────────────────────────────────────────
BG_COLOR = (30, 30, 50)
COLOR_SELECTED = (255, 255, 0)
COLOR_HOVERED = (230, 230, 255)
COLOR_DEFAULT = (200, 200, 200)
COLOR_MUTED = (120, 120, 120)
COLOR_INFO = (150, 150, 150)

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
        self.font = pygame.font.SysFont(None, self._s(48))
        self.small_font = pygame.font.SysFont(None, self._s(36))

        self.settings = settings
        self.items = [
            {"key": "fps",             "label": "FPS Limit",             "step": 10,  "min": 30,    "max": 360},
            {"key": "speed",           "label": "Scroll Speed",          "step": 0.1, "min": 0.1,   "max": 2.0},
            {"key": "volume",          "label": "Global Volume",         "step": 0.1, "min": 0.0,   "max": 1.0},
            {"key": "hit_window_mult", "label": "Hit Window Multiplier", "step": 0.1, "min": 0.5,   "max": 3.0},
            {"key": "fullscreen",      "label": "Fullscreen",            "type": "choice", "choices_key": "_fullscreen_opts"},
            {"key": "audio_device_idx","label": "Audio Device",          "type": "choice", "choices_key": "audio_devices"},
            {"key": "audio_freq",      "label": "Sample Rate (Hz)",      "step": 100, "min": 22050, "max": 48000},
            {"key": "audio_buffer",    "label": "Audio Buffer",          "step": 256, "min": 256,   "max": 4096},
            {"key": "audio_channels",  "label": "Audio Channels",        "step": 1,   "min": 1,     "max": 2},
        ]
        self.settings.setdefault("_fullscreen_opts", ["Off", "On"])
        self.settings.setdefault("fullscreen", 0)
        self.selected_index = 0
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
            return COLOR_SELECTED
        return COLOR_HOVERED if hovered else COLOR_DEFAULT

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
        if key == pygame.K_UP and self.selected_index > 0:
            self.selected_index -= 1
        elif key == pygame.K_DOWN and self.selected_index < len(self.items) - 1:
            self.selected_index += 1
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
        for i in range(len(self.items)):
            ry = start_y + i * row_h
            if margin_l <= mx <= margin_r and ry <= my <= ry + self._s(40):
                self.selected_index = i
                break

    # ── Drawing ───────────────────────────────────────────────────────────

    def _draw(self):
        self.screen.fill(BG_COLOR)
        self.screen.blit(self.font.render("SETTINGS", True, (255, 255, 255)), (self._s(50), self._s(50)))

        mx, my = pygame.mouse.get_pos()
        row_h = self._s(60)
        start_y = self._s(120)
        margin_l, margin_r = self._s(50), self.w - self._s(50)
        y = start_y

        for i, item in enumerate(self.items):
            hovered = margin_l <= mx <= margin_r and y <= my <= y + self._s(40)
            color = self._row_color(i, self.selected_index, hovered)
            label = f"{item['label']}:  < {self._format_value(item)} >"
            self.screen.blit(self.small_font.render(label, True, color), (self._s(100), y))
            y += row_h

        self.screen.blit(self.small_font.render("* Audio settings apply on next song", True, COLOR_MUTED), (self._s(50), y + self._s(20)))
        self.screen.blit(self.small_font.render("Press ESC/TAB to Return | Scroll wheel to adjust", True, COLOR_INFO), (self._s(50), y + self._s(60)))
