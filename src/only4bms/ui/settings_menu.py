import pygame
from only4bms.i18n import get as _t, FONT_NAME, LANGUAGES, LANGUAGE_CODES
from only4bms import i18n as _i18n
from .components import (
    make_bg_cache, draw_glass_panel, draw_row, draw_category,
    draw_pill_button, draw_glow_text, draw_hint_bar, draw_scrollbar,
    C_TEXT_ACCENT, C_TEXT_PRIMARY, C_TEXT_SECONDARY, C_TEXT_DIM,
    C_GLOW_CYAN, C_GLOW_PURPLE, C_BORDER_DIM, C_BORDER_ACCENT,
    # Legacy exports used by calibration_menu.py
    COLOR_ACCENT, COLOR_SELECTED_BG, COLOR_TEXT_PRIMARY, COLOR_PANEL_BG,
    BASE_W, BASE_H,
)

MAX_CHOICE_NAME_LEN = 30
INT_KEYS = frozenset((
    "fps", "audio_freq", "audio_buffer", "audio_channels",
    "input_polling_rate", "visual_offset",
))

_ROW_H_BASE  = 64   # unified height used by both drawing and hit-testing
_START_Y_BASE = 112  # top of the scrollable panel


class SettingsMenu:
    def __init__(self, settings, renderer, window):
        from pygame._sdl2.video import Texture
        self.renderer = renderer
        self.window   = window
        self.w, self.h = self.window.size
        self.sx, self.sy = self.w / BASE_W, self.h / BASE_H

        self.screen  = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.texture = None
        self._bg     = make_bg_cache(self.w, self.h)

        pygame.display.set_caption("Settings")
        self.clock      = pygame.time.Clock()
        self.title_font = _i18n.font("ui_title", self.sy, bold=True)
        self.font       = _i18n.font("ui_body",  self.sy)
        self.small_font = _i18n.font("ui_small", self.sy)

        self.settings = settings
        self.items = [
            # SYSTEM
            {"type": "category", "label_key": "cat_system"},
            {"key": "language",          "label_key": "language",         "type": "choice", "choices_key": "_language_opts"},
            {"key": "fps",               "label_key": "fps_limit",        "step": 10,  "min": 30,    "max": 360},
            {"key": "vsync",             "label_key": "vsync",            "type": "choice", "choices_key": "_bool_opts"},
            {"key": "input_polling_rate","label_key": "input_polling",    "step": 100, "min": 125,   "max": 2000},
            {"key": "fullscreen",        "label_key": "fullscreen",       "type": "choice", "choices_key": "_fullscreen_opts"},
            {"key": "audio_device_idx",  "label_key": "audio_device",     "type": "choice", "choices_key": "audio_devices"},
            # AUDIO
            {"type": "category", "label_key": "cat_audio"},
            {"key": "volume",        "label_key": "volume",       "step": 0.1, "min": 0.0,   "max": 1.0},
            {"key": "audio_freq",    "label_key": "sample_rate",  "step": 100, "min": 22050, "max": 48000},
            {"key": "audio_buffer",  "label_key": "audio_buffer", "step": 256, "min": 256,   "max": 4096},
            {"key": "audio_channels","label_key": "audio_channels","step": 1,  "min": 1,     "max": 2},
            # GAMEPLAY
            {"type": "category", "label_key": "cat_gameplay"},
            {"key": "visual_offset",   "label_key": "visual_offset",   "step": 1,   "min": -200, "max": 200},
            {"key": "hit_window_mult", "label_key": "hit_window_mult", "step": 0.1, "min": 0.5,  "max": 3.0},
            {"key": "judge_delay",     "label_key": "judge_delay",     "step": 1,   "min": -200, "max": 200},
            # UI VISIBILITY
            {"type": "category", "label_key": "cat_ui"},
            {"key": "show_bga",           "label_key": "show_bga",           "type": "choice", "choices_key": "_bool_opts"},
            {"key": "show_judgment_text", "label_key": "show_judgment_text", "type": "choice", "choices_key": "_bool_opts"},
            {"key": "show_jitter_bar",    "label_key": "show_jitter_bar",    "type": "choice", "choices_key": "_bool_opts"},
            {"key": "show_fast_slow",     "label_key": "show_fast_slow",     "type": "choice", "choices_key": "_bool_opts"},
            {"key": "show_combo",         "label_key": "show_combo",         "type": "choice", "choices_key": "_bool_opts"},
            {"key": "show_effects",       "label_key": "show_effects",       "type": "choice", "choices_key": "_bool_opts"},
        ]

        # Defaults
        self.settings.setdefault("_fullscreen_opts", ["Off", "On"])
        from only4bms.game.constants import NOTE_TYPE_NAMES
        self.settings["_note_type_opts"] = list(NOTE_TYPE_NAMES)
        self.settings.setdefault("_bool_opts", ["OFF", "ON"])
        self.settings["_language_opts"] = [LANGUAGES[c] for c in LANGUAGE_CODES]

        current_lang = self.settings.get("language", "auto")
        if isinstance(current_lang, int):
            if current_lang < 0 or current_lang >= len(LANGUAGE_CODES):
                self.settings["language"] = 0
        elif current_lang == "auto":
            from only4bms.i18n import get_language
            code = get_language()
            self.settings["language"] = LANGUAGE_CODES.index(code) if code in LANGUAGE_CODES else 0
        elif current_lang in LANGUAGE_CODES:
            self.settings["language"] = LANGUAGE_CODES.index(current_lang)
        else:
            self.settings["language"] = 0

        self.settings.setdefault("fullscreen", 0)
        self.settings.setdefault("vsync", 0)
        self.settings.setdefault("note_type", 0)
        self.settings.setdefault("show_bga", 1)
        self.settings.setdefault("show_judgment_text", 1)
        self.settings.setdefault("show_jitter_bar", 1)
        self.settings.setdefault("show_fast_slow", 1)
        self.settings.setdefault("show_combo", 1)
        self.settings.setdefault("show_effects", 1)

        self.selected_index = 1
        self.view_offset    = 0
        self.max_visible    = max(6, int((self.h / self.sy - _START_Y_BASE - 50) // _ROW_H_BASE))
        self.running        = True

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _s(self, v):
        return max(1, int(v * self.sy))

    def _header_rects(self):
        """Consistent rects used by both _draw and _handle_button_click."""
        title_surf  = self.title_font.render(_t("settings_title"), True, C_TEXT_ACCENT)
        title_rect  = title_surf.get_rect(topleft=(self._s(50), self._s(30)))
        btn_h       = self._s(34)
        btn_w       = self._s(138)
        btn_cal_rect = pygame.Rect(title_rect.right + self._s(16),
                                   title_rect.centery - btn_h // 2, btn_w, btn_h)
        btn_key_rect = pygame.Rect(btn_cal_rect.right + self._s(10),
                                   btn_cal_rect.top, btn_w, btn_h)
        return title_rect, btn_cal_rect, btn_key_rect

    def _adjust(self, item, direction):
        if item.get("type") == "choice":
            choices = self.settings.get(item["choices_key"], ["Default"])
            idx     = (self.settings.get(item["key"], 0) + direction) % len(choices)
            self.settings[item["key"]] = idx
        else:
            val = self.settings.get(item["key"])
            self.settings[item["key"]] = max(item["min"], min(item["max"],
                                             round(val + item["step"] * direction, 2)))
        from ..main import save_settings
        save_settings(self.settings)
        if item.get("key") == "language":
            from only4bms import i18n
            i18n.set_language(LANGUAGE_CODES[self.settings["language"]])

    def _format_value(self, item):
        if item.get("type") == "choice":
            choices = self.settings.get(item["choices_key"], ["Default"])
            idx     = self.settings.get(item["key"], 0)
            name    = choices[idx] if idx < len(choices) else "Default"
            return (name[:MAX_CHOICE_NAME_LEN - 2] + "..") if len(name) > MAX_CHOICE_NAME_LEN else name
        val = self.settings.get(item["key"], 0)
        return str(int(val)) if item["key"] in INT_KEYS else f"{float(val):.1f}"

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        from pygame._sdl2.video import Texture
        pygame.key.set_repeat(300, 50)
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
            self.clock.tick(self.settings.get("fps", 60))
        pygame.key.set_repeat(0)
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
                self._on_key(event.key)
            elif event.type == pygame.MOUSEWHEEL:
                self._adjust(self.items[self.selected_index], event.y)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._on_click(event.pos)
                self._handle_button_click(event.pos)
            elif event.type == pygame.JOYBUTTONDOWN:
                if   event.button == 1:
                    self.running = False
            elif event.type == pygame.JOYHATMOTION:
                vx, vy = event.value
                if vx == 0 and vy == 0: continue
                if   vy ==  1: self._on_key(pygame.K_UP)
                elif vy == -1: self._on_key(pygame.K_DOWN)
                elif vx == -1: self._on_key(pygame.K_LEFT)
                elif vx ==  1: self._on_key(pygame.K_RIGHT)

    def _handle_button_click(self, pos):
        _, btn_cal_rect, btn_key_rect = self._header_rects()
        if btn_cal_rect.collidepoint(pos):
            from .calibration_menu import CalibrationMenu
            CalibrationMenu(self.settings, self.renderer, self.window).run()
            pygame.display.set_caption("Settings")
            pygame.key.set_repeat(300, 50)
            return
        if btn_key_rect.collidepoint(pos):
            from .key_config_menu import KeyConfigMenu
            KeyConfigMenu(self.settings, self.renderer, self.window).run()
            pygame.display.set_caption("Settings")
            pygame.key.set_repeat(300, 50)

    def _on_key(self, key):
        if key == pygame.K_UP and self.selected_index > 1:
            self.selected_index -= 1
            if self.items[self.selected_index].get("type") == "category":
                self.selected_index -= 1
            if self.selected_index < self.view_offset:
                self.view_offset = self.selected_index
        elif key == pygame.K_DOWN and self.selected_index < len(self.items) - 1:
            self.selected_index += 1
            if self.items[self.selected_index].get("type") == "category":
                if self.selected_index < len(self.items) - 1:
                    self.selected_index += 1
                else:
                    self.selected_index -= 1
            if self.selected_index >= self.view_offset + self.max_visible:
                self.view_offset = self.selected_index - self.max_visible + 1
        elif key == pygame.K_LEFT:
            self._adjust(self.items[self.selected_index], -1)
        elif key == pygame.K_RIGHT:
            self._adjust(self.items[self.selected_index], +1)
        elif key in (pygame.K_ESCAPE, pygame.K_TAB):
            self.running = False

    def _on_click(self, pos):
        mx, my  = pos
        row_h   = self._s(_ROW_H_BASE)
        start_y = self._s(_START_Y_BASE)
        margin_l = self._s(50)
        margin_r = self.w - self._s(50)
        for i in range(self.view_offset,
                       min(len(self.items), self.view_offset + self.max_visible)):
            if self.items[i].get("type") == "category":
                continue
            ry = start_y + (i - self.view_offset) * row_h
            if margin_l <= mx <= margin_r and ry <= my <= ry + self._s(50):
                self.selected_index = i
                break

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self):
        mx, my = pygame.mouse.get_pos()

        # Background (pre-rendered)
        self.screen.blit(self._bg, (0, 0))

        # ── Header ──
        title_rect, btn_cal_rect, btn_key_rect = self._header_rects()
        draw_glow_text(self.screen, _t("settings_title"), self.title_font,
                       C_TEXT_ACCENT, C_GLOW_CYAN,
                       title_rect.topleft, glow_radius=4)

        draw_pill_button(self.screen, btn_cal_rect, _t("calibrate"),
                         self.small_font, hovered=btn_cal_rect.collidepoint(mx, my))
        draw_pill_button(self.screen, btn_key_rect, _t("key_config"),
                         self.small_font, hovered=btn_key_rect.collidepoint(mx, my))

        # Thin separator under header
        sep_y = self._s(_START_Y_BASE) - self._s(6)
        sep = pygame.Surface((self.w - self._s(100), 1), pygame.SRCALPHA)
        for x in range(sep.get_width()):
            t = 1.0 - abs(x - sep.get_width() / 2) / (sep.get_width() / 2 + 1)
            sep.set_at((x, 0), (*C_GLOW_CYAN, int(35 * t)))
        self.screen.blit(sep, (self._s(50), sep_y))

        # ── Panel background ──
        row_h    = self._s(_ROW_H_BASE)
        start_y  = self._s(_START_Y_BASE)
        margin_l = self._s(50)
        content_w = self.w - margin_l * 2

        visible_count = min(len(self.items), self.view_offset + self.max_visible) - self.view_offset
        panel_h = visible_count * row_h + self._s(8)
        panel_rect = pygame.Rect(margin_l - self._s(8), start_y - self._s(4),
                                 content_w + self._s(16), panel_h)
        draw_glass_panel(self.screen, panel_rect, radius=14,
                         fill_alpha=8, highlight=False)

        # ── Rows ──
        y = start_y
        for i in range(self.view_offset,
                       min(len(self.items), self.view_offset + self.max_visible)):
            item = self.items[i]
            rect = pygame.Rect(margin_l, y, content_w - self._s(16), row_h - self._s(6))

            if item.get("type") == "category":
                draw_category(self.screen, rect, _t(item.get("label_key", "")),
                              self.small_font)
            else:
                is_sel = (i == self.selected_index)
                is_hov = rect.collidepoint(mx, my) and not is_sel
                draw_row(
                    self.screen, rect,
                    label      = _t(item.get("label_key", "")),
                    font       = self.font,
                    selected   = is_sel,
                    hovered    = is_hov,
                    value_text = self._format_value(item),
                    value_font = self.font,
                )
            y += row_h

        # ── Scrollbar ──
        if len(self.items) > self.max_visible:
            sb_x = margin_l + content_w - self._s(4)
            sb_y = start_y
            sb_h = self.max_visible * row_h
            r0   = self.view_offset / len(self.items)
            r1   = min(1.0, (self.view_offset + self.max_visible) / len(self.items))
            draw_scrollbar(self.screen, sb_x, sb_y, sb_h, r0, r1)

        # ── Hint bar ──
        draw_hint_bar(self.screen,
                      "↑ ↓  Navigate    ←  →  Adjust    ESC  Back",
                      self.small_font, self.h, self.w)
