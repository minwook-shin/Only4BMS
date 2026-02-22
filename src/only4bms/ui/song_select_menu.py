import glob
import os
import sys
import webbrowser

import pygame

from ..core.bms_parser import BMSParser

# ── Base (windowed) resolution ────────────────────────────────────────────
BASE_W, BASE_H = 800, 600

BG_COLOR = (30, 30, 50)
VISIBLE_ITEMS = 6
BMS_EXTS = ('*.bms', '*.bme')
SEARCH_URL = "https://bmssearch.net/search?q={}"

# ── Colors ────────────────────────────────────────────────────────────────
COLOR_SELECTED = (255, 255, 0)
COLOR_SELECTED_BG = (60, 60, 90)
COLOR_HOVERED = (230, 230, 255)
COLOR_HOVERED_BG = (50, 50, 75)
COLOR_DEFAULT = (200, 200, 200)
COLOR_DEFAULT_BG = (40, 40, 60)
COLOR_SUB = (150, 150, 150)
COLOR_DIM = (100, 100, 100)


class SongSelectMenu:
    def __init__(self, settings, renderer, window, mode='single'):
        from pygame._sdl2.video import Texture
        self.renderer = renderer
        self.window = window
        self.mode = mode
        self.ai_difficulties = ['normal', 'hard']
        self.ai_diff_idx = 0
        
        self.w, self.h = self.window.size
        self.sx, self.sy = self.w / BASE_W, self.h / BASE_H
        
        # We use an offscreen surface named 'self.screen' so all existing 
        # draw calls in this class keep working without modification.
        self.screen = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.texture = None # Will hold the uploaded frame
        
        pygame.display.set_caption("Song Selection")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, self._s(36))
        self.small_font = pygame.font.SysFont(None, self._s(24))
        self.settings = settings

        # BMS directory (PyInstaller-compatible)
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.bms_dir = os.path.join(base, 'bms')

        # State
        self.songs = []
        self.selected_index = 0
        self.scroll_offset = 0
        self.running = True
        self.action = "QUIT"
        self.selected_song_path = None

        # Overlays
        self.search_mode = False
        self.search_query = ""
        self.show_guide = False
        self.show_quit_confirm = False
        self._nav_buttons = []
        self._quit_buttons = []

        self.scan_songs()

    def _s(self, v):
        """Scale a base-800x600 value to current resolution."""
        return max(1, int(v * self.sy))

    def _sx_v(self, v):
        """Scale X-axis value."""
        return max(1, int(v * self.sx))

    # ── Song Scanning ────────────────────────────────────────────────────

    def scan_songs(self):
        print(f"Scanning song directory: {self.bms_dir}")
        os.makedirs(self.bms_dir, exist_ok=True)
        bms_files = []
        for ext in BMS_EXTS:
            bms_files.extend(glob.glob(os.path.join(self.bms_dir, '**', ext), recursive=True))
        for f in bms_files:
            title, artist, bpm, playlevel, genre, total_notes = BMSParser(f).get_metadata()
            self.songs.append({
                'filepath': f, 'title': title, 'artist': artist,
                'bpm': bpm, 'playlevel': playlevel, 'genre': genre,
                'total_notes': total_notes,
            })
        if not self.songs:
            self._create_mock_song()

    def _create_mock_song(self):
        try:
            mock_dir = os.path.join(self.bms_dir, 'mock_song')
            os.makedirs(mock_dir, exist_ok=True)
            path = os.path.join(mock_dir, 'demo.bms')
            if not os.path.exists(path):
                with open(path, 'w', encoding='utf-8') as f:
                    f.write("#PLAYER 1\n#TITLE Mock Song Demo\n#ARTIST Antigravity\n"
                            "#BPM 120\n#WAV01 kick.wav\n#00111:01000100\n#00212:00010001")
            self.songs.append({
                'filepath': path, 'title': "Mock Song Demo (Auto-generated)",
                'artist': "Antigravity", 'bpm': 120.0, 'playlevel': '0',
                'genre': 'Demo', 'total_notes': 3,
            })
        except Exception as e:
            print(f"Failed to create mock song: {e}")

    # ── Selection helpers ────────────────────────────────────────────────

    def _move_selection(self, direction):
        new = self.selected_index + direction
        if 0 <= new < len(self.songs):
            self.selected_index = new
            if self.selected_index < self.scroll_offset:
                self.scroll_offset = self.selected_index
            elif self.selected_index >= self.scroll_offset + VISIBLE_ITEMS:
                self.scroll_offset = self.selected_index - VISIBLE_ITEMS + 1

    def _select_play(self):
        if self.songs:
            self.selected_song_path = self.songs[self.selected_index]['filepath']
            self.action = "PLAY"
            self.running = False

    # ── Main loop ────────────────────────────────────────────────────────

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
        return self.action, self.selected_song_path, self.ai_difficulties[self.ai_diff_idx]

    # ── Event handling ───────────────────────────────────────────────────

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if self.show_quit_confirm:
                    if event.key in (pygame.K_y, pygame.K_RETURN):
                        self.running = False
                    elif event.key in (pygame.K_n, pygame.K_ESCAPE):
                        self.show_quit_confirm = False
                    continue
                if self.show_guide:
                    if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                        self.show_guide = False
                    continue
                if self.search_mode:
                    self._handle_search_key(event)
                    continue
                self._handle_nav_key(event.key)
            elif event.type == pygame.MOUSEWHEEL and not self.search_mode and not self.show_guide and not self.show_quit_confirm:
                self._move_selection(-1 if event.y > 0 else 1)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.show_quit_confirm:
                    self._handle_quit_click(event.pos)
                else:
                    self._handle_click(event.pos)

    def _handle_search_key(self, event):
        if event.key == pygame.K_ESCAPE:
            self.search_mode = False
        elif event.key == pygame.K_RETURN:
            if self.search_query.strip():
                webbrowser.open(SEARCH_URL.format(self.search_query))
            self.search_mode = False
            self.show_guide = True
        elif event.key == pygame.K_BACKSPACE:
            self.search_query = self.search_query[:-1]
        else:
            self.search_query += event.unicode

    def _handle_nav_key(self, key):
        if key == pygame.K_UP:
            self._move_selection(-1)
        elif key == pygame.K_DOWN:
            self._move_selection(+1)
        elif key == pygame.K_RETURN:
            self._select_play()
        elif key == pygame.K_ESCAPE:
            self.show_quit_confirm = True
        elif key == pygame.K_TAB:
            self.action = "SETTINGS"
            self.running = False
        elif key == pygame.K_F3:
            self.search_mode = True
            self.search_query = ""
        elif key == pygame.K_F5:
            self.songs = []
            self.scan_songs()

    def _handle_quit_click(self, pos):
        for rect, action in self._quit_buttons:
            if rect.collidepoint(pos):
                if action == "YES":
                    self.running = False
                else:
                    self.show_quit_confirm = False
                return

    def _handle_click(self, pos):
        if self.show_guide:
            self.show_guide = False
            return
        if self.search_mode:
            return
        mx, my = pos

        for btn_rect, btn_action in self._nav_buttons:
            if btn_rect.collidepoint(mx, my):
                if btn_action == "SETTINGS":
                    self.action = "SETTINGS"
                    self.running = False
                elif btn_action == "SEARCH":
                    self.search_mode = True
                    self.search_query = ""
                elif btn_action == "RELOAD":
                    self.songs = []
                    self.scan_songs()
                elif btn_action == "DIFF":
                    self.ai_diff_idx = (self.ai_diff_idx + 1) % len(self.ai_difficulties)
                return

        margin_l, margin_r = self._sx_v(50), self.w - self._sx_v(50)
        if not self.songs or not (margin_l <= mx <= margin_r):
            return
        row_h = self._s(75)
        item_h = self._s(65)
        start_y = self._s(120)
        end = min(len(self.songs), self.scroll_offset + VISIBLE_ITEMS)
        for i in range(self.scroll_offset, end):
            row = i - self.scroll_offset
            y_top = start_y + row * row_h
            if y_top <= my <= y_top + item_h:
                if self.selected_index == i:
                    self._select_play()
                else:
                    self.selected_index = i
                break

    # ── Drawing ──────────────────────────────────────────────────────────

    def _draw(self):
        self.screen.fill(BG_COLOR)

        # Header
        self.screen.blit(
            self.font.render(f"SELECT SONG ({len(self.songs)} Found)", True, (255, 255, 255)),
            (self._sx_v(50), self._s(50)))

        # Clickable nav buttons
        mx, my = pygame.mouse.get_pos()
        self._nav_buttons = []
        btn_labels = [("Settings", "SETTINGS"), ("Search BMS", "SEARCH"), ("Reload", "RELOAD")]
        if self.mode == 'ai_multi':
            btn_labels.append((f"AI: {self.ai_difficulties[self.ai_diff_idx].upper()}", "DIFF"))
            
        bx = self._sx_v(400)
        for label, action in btn_labels:
            surf = self.small_font.render(f"[{label}]", True, (150, 200, 150))
            rect = surf.get_rect(topleft=(bx, self._s(58)))
            hovered = rect.collidepoint(mx, my)
            color = (255, 255, 100) if hovered else (150, 200, 150)
            surf = self.small_font.render(f"[{label}]", True, color)
            self.screen.blit(surf, rect)
            self._nav_buttons.append((rect, action))
            bx = rect.right + self._sx_v(10)

        if not self.songs:
            self.screen.blit(
                self.font.render("No BMS files found in 'bms/' directory.", True, COLOR_SUB),
                (self._sx_v(50), self._s(150)))
        else:
            self._draw_song_list()

        if self.search_mode:
            self._draw_search_overlay()
        if self.show_guide:
            self._draw_guide_overlay()
        if self.show_quit_confirm:
            self._draw_quit_confirm()

    def _draw_song_list(self):
        mx, my = pygame.mouse.get_pos()
        row_h = self._s(75)
        item_h = self._s(65)
        start_y = self._s(120)
        margin_l = self._sx_v(50)
        margin_r = self.w - self._sx_v(50)
        content_w = margin_r - margin_l
        end = min(len(self.songs), self.scroll_offset + VISIBLE_ITEMS)

        for i in range(self.scroll_offset, end):
            row = i - self.scroll_offset
            y = start_y + row * row_h
            hovered = margin_l <= mx <= margin_r and y <= my <= y + item_h

            if i == self.selected_index:
                color, bg = COLOR_SELECTED, COLOR_SELECTED_BG
            elif hovered:
                color, bg = COLOR_HOVERED, COLOR_HOVERED_BG
            else:
                color, bg = COLOR_DEFAULT, COLOR_DEFAULT_BG

            pygame.draw.rect(self.screen, bg, (margin_l, y, content_w, item_h))
            self.screen.blit(self.font.render(self.songs[i]['title'], True, color), (margin_l + self._sx_v(20), y + self._s(10)))

            s = self.songs[i]
            sub = f"Lv.{s['playlevel']} | {s.get('genre', 'Unknown')} | {s['artist']} | BPM: {s['bpm']} | Notes: {s['total_notes']}"
            self.screen.blit(self.small_font.render(sub, True, COLOR_SUB), (margin_l + self._sx_v(20), y + self._s(40)))

        if self.scroll_offset > 0:
            self.screen.blit(self.small_font.render("... [ UP For More ] ...", True, COLOR_DIM),
                             (self.w // 2 - self._sx_v(80), start_y - self._s(25)))
        if end < len(self.songs):
            self.screen.blit(self.small_font.render("... [ DOWN For More ] ...", True, COLOR_DIM),
                             (self.w // 2 - self._sx_v(80), start_y + VISIBLE_ITEMS * row_h))

    def _draw_overlay(self, alpha=200):
        overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, alpha))
        self.screen.blit(overlay, (0, 0))

    def _draw_search_overlay(self):
        self._draw_overlay(200)
        cx = self.w // 2
        pygame.draw.rect(self.screen, (255, 255, 255),
                         (cx - self._sx_v(300), self._s(250), self._sx_v(600), self._s(60)), 2)
        self.screen.blit(self.font.render("Search Web (bmssearch.net)", True, (255, 255, 255)),
                         (cx - self._sx_v(300), self._s(200)))
        self.screen.blit(self.font.render(self.search_query + "_", True, (200, 255, 200)),
                         (cx - self._sx_v(280), self._s(265)))
        self.screen.blit(
            self.small_font.render("Type query and press ENTER to search directly on your browser.", True, COLOR_SUB),
            (cx - self._sx_v(300), self._s(320)))

    def _draw_guide_overlay(self):
        self._draw_overlay(220)
        lines = [
            "Browser Opened! To play a new song:", "",
            "1. Download the track from the opened website.",
            "2. Extract the downloaded ZIP or RAR file.",
            "3. Move the extracted folder into the 'bms' directory.",
            "4. Press F5 closely after this overlay to reload songs.",
            "", "(Press ENTER or ESC or Click to close)",
        ]
        y = self._s(150)
        for line in lines:
            self.screen.blit(self.small_font.render(line, True, (255, 255, 255)), (self._sx_v(100), y))
            y += self._s(35)

    def _draw_quit_confirm(self):
        self._draw_overlay(200)
        mx, my = pygame.mouse.get_pos()
        cx, cy = self.w // 2, self.h // 2

        msg = self.font.render("Quit Game?", True, (255, 255, 255))
        self.screen.blit(msg, msg.get_rect(center=(cx, cy - self._s(50))))

        self._quit_buttons = []
        labels = [("Yes", "YES"), ("No", "NO")]
        bx = cx - self._sx_v(100)
        for label, action in labels:
            surf = self.font.render(f"[ {label} ]", True, (200, 200, 200))
            rect = surf.get_rect(topleft=(bx, cy + self._s(10)))
            hovered = rect.collidepoint(mx, my)
            color = (255, 255, 100) if hovered else (200, 200, 200)
            surf = self.font.render(f"[ {label} ]", True, color)
            self.screen.blit(surf, rect)
            self._quit_buttons.append((rect, action))
            bx += self._sx_v(140)
