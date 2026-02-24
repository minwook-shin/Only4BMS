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
BMS_EXTS = ('*.bms', '*.bme', '*.bml', '*.pms')
SEARCH_URL = "https://bmssearch.net/search?q={}"

# ── Colors & Aesthetics ──────────────────────────────────────────────────
COLOR_ACCENT = (0, 255, 200)       # Cyan/Neon
COLOR_ACCENT_DIM = (0, 150, 120)
COLOR_SELECTED_BG = (40, 50, 80, 225)
COLOR_HOVERED_BG = (35, 35, 60, 160)
COLOR_TEXT_PRIMARY = (255, 255, 255)
COLOR_TEXT_SECONDARY = (180, 180, 200)
COLOR_PANEL_BG = (15, 15, 25, 130)


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
        self.font = pygame.font.SysFont("Outfit, Roboto, sans-serif", self._s(32))
        self.font_bold = pygame.font.SysFont("Outfit, Roboto, sans-serif", self._s(38), bold=True)
        self.small_font = pygame.font.SysFont("Outfit, Roboto, sans-serif", self._s(22))
        self.title_font = pygame.font.SysFont("Outfit, Roboto, sans-serif", self._s(44), bold=True)
        self.settings = settings

        # BMS directory
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.bms_dir = os.path.join(base, 'bms')

        # State
        self.song_groups = [] # List of {title, artist, folder, charts: [metadata]}
        self.selected_group_idx = 0
        self.selected_chart_idx = 0
        self.scroll_offset = 0
        self.running = True
        self.action = "QUIT"
        self.selected_song_path = None

        # Music Preview
        self.last_previewed_path = None
        self.bg_surf = None
        self.last_bg_path = None
        self.bg_needs_update = True
        self.preview_timer = 0
        self.PREVIEW_DELAY_MS = 500

        # Overlays
        self.search_mode = False
        self.search_query = ""
        self.show_guide = False
        self._nav_buttons = []

        # Input debouncing
        self.ignore_enter = pygame.key.get_pressed()[pygame.K_RETURN]

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
        
        # Group by directory
        groups_dict = {} # folder_path -> {title, artist, charts}
        
        bms_files = []
        for ext in BMS_EXTS:
            # Escape path to handle [] correctly
            search_pattern = os.path.join(glob.escape(self.bms_dir), '**', ext)
            bms_files.extend(glob.glob(search_pattern, recursive=True))
            
        for f in bms_files:
            try:
                folder = os.path.dirname(f)
                res = BMSParser(f).get_metadata()
                title, artist, bpm, playlevel, genre, total_notes, preview_path, stagefile, banner = res
                
                chart_data = {
                    'filepath': f, 'title': title, 'artist': artist,
                    'bpm': bpm, 'playlevel': playlevel, 'genre': genre,
                    'total_notes': total_notes, 'preview_path': preview_path,
                    'stagefile': stagefile, 'banner': banner
                }
                
                if folder not in groups_dict:
                    groups_dict[folder] = {
                        'folder': folder,
                        'title': title, # Use first encountered title as group title
                        'artist': artist,
                        'genre': genre,
                        'preview_path': preview_path,
                        'stagefile': stagefile,
                        'banner': banner,
                        'charts': [chart_data]
                    }
                else:
                    groups_dict[folder]['charts'].append(chart_data)
            except Exception as e:
                print(f"Error parsing {f}: {e}")

        self.song_groups = list(groups_dict.values())
        # Sort charts in each group by difficulty
        for g in self.song_groups:
            g['charts'].sort(key=lambda x: int(x['playlevel']) if x['playlevel'].isdigit() else 0)

        if not self.song_groups:
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
            
            mock_meta = {
                'filepath': path, 'title': "Mock Song Demo (Auto-generated)",
                'artist': "Antigravity", 'bpm': 120.0, 'playlevel': '0',
                'genre': 'Demo', 'total_notes': 3,
            }
            self.song_groups.append({
                'folder': mock_dir,
                'title': mock_meta['title'],
                'artist': mock_meta['artist'],
                'genre': mock_meta['genre'],
                'charts': [mock_meta]
            })
        except Exception as e:
            print(f"Failed to create mock song: {e}")

    # ── Selection helpers ────────────────────────────────────────────────

    def _move_selection(self, direction):
        new = self.selected_group_idx + direction
        if 0 <= new < len(self.song_groups):
            self.selected_group_idx = new
            self.selected_chart_idx = 0 # Reset diff when changing song
            self._update_scroll()
            self._update_background()
            self.preview_timer = pygame.time.get_ticks() # Trigger preview timer

    def _move_chart_selection(self, direction):
        if not self.song_groups: return
        charts = self.song_groups[self.selected_group_idx]['charts']
        new = (self.selected_chart_idx + direction) % len(charts)
        self.selected_chart_idx = new
        self._update_background()

    def _update_scroll(self):
        if self.selected_group_idx < self.scroll_offset:
            self.scroll_offset = self.selected_group_idx
        elif self.selected_group_idx >= self.scroll_offset + VISIBLE_ITEMS:
            self.scroll_offset = self.selected_group_idx - VISIBLE_ITEMS + 1

    def _select_play(self):
        if not self.song_groups: return # Added safety check
        group = self.song_groups[self.selected_group_idx]
        self.selected_song_path = group['charts'][self.selected_chart_idx]['filepath']
        self.running = False
        self.action = "PLAY"
        pygame.mixer.music.stop()

    def _update_background(self):
        if not self.song_groups: return
        group = self.song_groups[self.selected_group_idx]
        chart = group['charts'][self.selected_chart_idx]
        
        # Priority: chart stagefile -> group stagefile -> chart banner -> group banner
        bg_path = chart.get('stagefile') or group.get('stagefile') or \
                  chart.get('banner') or group.get('banner')
                  
        if bg_path == self.last_bg_path and not self.bg_needs_update:
            return
            
        self.last_bg_path = bg_path
        self.bg_needs_update = False
        if bg_path and os.path.exists(bg_path):
            try:
                img = pygame.image.load(bg_path)
                img_w, img_h = img.get_size()
                scale = max(self.w / img_w, self.h / img_h)
                new_size = (int(img_w * scale), int(img_h * scale))
                self.bg_surf = pygame.transform.scale(img, new_size)
            except Exception as e:
                print(f"Failed to load background {bg_path}: {e}")
                self.bg_surf = None
        else:
            self.bg_surf = None

    def _update_preview(self):
        if not self.song_groups: return
        
        group = self.song_groups[self.selected_group_idx]
        if self.last_previewed_path == group['folder']:
            return
            
        now = pygame.time.get_ticks()
        if now - self.preview_timer < self.PREVIEW_DELAY_MS:
            return
            
        self.last_previewed_path = group['folder']
        
        # Try to find a preview candidate
        audio_files = []
        try:
            for f in os.listdir(group['folder']):
                if f.lower().endswith(('.mp3', '.ogg', '.wav')):
                    audio_files.append(os.path.join(group['folder'], f))
        except Exception as e:
            print(f"Error listing folder: {e}")
            return
            
        if not audio_files: return
        
        best = None
        # Priority 1: Explicitly defined preview in BMS metadata
        preview_meta = group.get('preview_path')
        if preview_meta:
            if os.path.exists(preview_meta):
                best = preview_meta
            else:
                # Extension fallback (e.g. .wav -> .ogg)
                base = os.path.splitext(preview_meta)[0]
                for ext in ('.ogg', '.mp3', '.wav', '.WAV'):
                    if os.path.exists(base + ext):
                        best = base + ext
                        break
        
        # Priority 2: Filename containing 'preview' or 'highlight' or starting with 'pre'
        if not best:
            for f in audio_files:
                fname = os.path.basename(f).lower()
                if 'preview' in fname or 'highlight' in fname or (fname.startswith('pre') and len(fname) < 12):
                    best = f
                    break
        
        # Fallback: largest file (likely the main track)
        if not best:
            best = max(audio_files, key=os.path.getsize)
            
        try:
            pygame.mixer.music.load(best)
            pygame.mixer.music.set_volume(self.settings.get('volume', 0.5) * 0.6)
            # Find a good starting point if we are playing the main track
            # (Crude heuristic: start at 1/3 of the song or use BMS highlight if we parsed it)
            pygame.mixer.music.play(loops=-1, start=0.0, fade_ms=500)
        except Exception as e:
            print(f"Failed to play preview: {e}")

    # ── Main loop ────────────────────────────────────────────────────────

    def run(self):
        from pygame._sdl2.video import Texture
        pygame.key.set_repeat(300, 50)
        pygame.event.clear()
        
        self._update_background()
        self.preview_timer = pygame.time.get_ticks()
        
        while self.running:
            self._handle_events()
            self._update_preview()
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
        pygame.mixer.music.stop()
        return self.action, self.selected_song_path, self.ai_difficulties[self.ai_diff_idx]

    # ── Event handling ───────────────────────────────────────────────────

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_RETURN:
                    self.ignore_enter = False
            elif event.type == pygame.KEYDOWN:
                if self.show_guide:
                    if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                        self.show_guide = False
                    continue
                if self.search_mode:
                    self._handle_search_key(event)
                    continue
                self._handle_nav_key(event.key)
            elif event.type == pygame.MOUSEWHEEL and not self.search_mode and not self.show_guide:
                self._move_selection(-1 if event.y > 0 else 1)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
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
        elif key == pygame.K_LEFT:
            self._move_chart_selection(-1)
        elif key == pygame.K_RIGHT:
            self._move_chart_selection(+1)
        elif key == pygame.K_RETURN:
            if not self.ignore_enter:
                self._select_play()
        elif key == pygame.K_ESCAPE:
            self.action = "MENU"
            self.running = False
            pygame.mixer.music.stop()
        elif key == pygame.K_TAB:
            self.action = "SETTINGS"
            self.running = False
            pygame.mixer.music.stop()
        elif key == pygame.K_F3:
            self.search_mode = True
            self.search_query = ""
        elif key == pygame.K_F5:
            self.song_groups = []
            self.scan_songs()

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

        margin_l, margin_r = self._sx_v(360), self._sx_v(760)
        if not self.song_groups or not (margin_l <= mx <= margin_r):
            return
        row_h = self._s(70)
        start_y = self._s(120)
        end = min(len(self.song_groups), self.scroll_offset + VISIBLE_ITEMS)
        for i in range(self.scroll_offset, end):
            row = i - self.scroll_offset
            y_top = start_y + row * row_h
            if y_top <= my <= y_top + row_h:
                if self.selected_group_idx == i:
                    self._select_play()
                else:
                    self.selected_group_idx = i
                    self.selected_chart_idx = 0
                    self._update_background()
                    self.preview_timer = pygame.time.get_ticks()
                break

    # ── Drawing ──────────────────────────────────────────────────────────

    def _draw(self):
        # 1. Clear Screen (Fully transparent)
        self.screen.fill((0, 0, 0, 0)) 

        # 2. Draw Background
        has_bg = False
        if self.bg_surf:
            try:
                bx = (self.w - self.bg_surf.get_width()) // 2
                by = (self.h - self.bg_surf.get_height()) // 2
                self.screen.blit(self.bg_surf, (bx, by))
                has_bg = True
            except:
                pass
        
        if has_bg:
            # Dim overlay (Balanced for better legibility)
            overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 120)) 
            self.screen.blit(overlay, (0, 0))
        else:
            # Full Fallback Gradient (Only if NO image)
            for y in range(self.h):
                grad = 1.0 - (y / self.h)
                c = [int(20 * grad), int(20 * grad), int(40 * grad + 20)]
                pygame.draw.line(self.screen, c, (0, y), (self.w, y))

        # Main Panels
        self._draw_song_list()
        self._draw_info_panel()

        # Header Title
        title_y = self._s(45)
        self.screen.blit(
            self.title_font.render("MUSIC SELECTION", True, COLOR_ACCENT),
            (self._sx_v(40), title_y))

        # Clickable nav buttons (Right-aligned, matching title height)
        mx, my = pygame.mouse.get_pos()
        self._nav_buttons = []
        btn_labels = [("Reload", "RELOAD"), ("Search BMS", "SEARCH"), ("Settings", "SETTINGS")] # Reversed for right-to-left draw
        if self.mode == 'ai_multi':
            btn_labels.insert(0, (f"AI: {self.ai_difficulties[self.ai_diff_idx].upper()}", "DIFF"))
            
        bx = self.w - self._sx_v(40) # Start from right margin
        for label, action in btn_labels:
            surf = self.small_font.render(label, True, (255, 255, 255))
            tw, th = surf.get_size()
            
            # Align center with title_y + offset
            # (Note: title_font is 44px, small_font is 22px)
            rect = pygame.Rect(bx - tw - 10, title_y + self._s(8), tw + 10, th + 5)
            hovered = rect.collidepoint(mx, my)
            
            pygame.draw.rect(self.screen, (60, 80, 60) if hovered else (40, 50, 40), rect, border_radius=4)
            color = (255, 255, 255) if hovered else (200, 220, 200)
            btn_surf = self.small_font.render(label, True, color)
            self.screen.blit(btn_surf, (rect.x + 5, rect.y + 2))
            
            self._nav_buttons.append((rect, action))
            bx = rect.x - self._sx_v(15) # Move left for next button

        if not self.song_groups:
            self.screen.blit(
                self.font.render("No BMS files found in 'bms/' directory.", True, COLOR_TEXT_SECONDARY),
                (self._sx_v(50), self._s(150)))

        if self.search_mode:
            self._draw_search_overlay()
        if self.show_guide:
            self._draw_guide_overlay()

    def _draw_song_list(self):
        mx, my = pygame.mouse.get_pos()
        row_h = self._s(70)
        start_y = self._s(120)
        margin_l = self._sx_v(360)
        content_w = self._sx_v(400)
        end = min(len(self.song_groups), self.scroll_offset + VISIBLE_ITEMS)

        # Glass Panel for List (Using Surface for correct blending)
        panel_rect = (margin_l - 10, start_y - 10, content_w + 20, VISIBLE_ITEMS * row_h + 20)
        psurf = pygame.Surface((panel_rect[2], panel_rect[3]), pygame.SRCALPHA)
        psurf.fill(COLOR_PANEL_BG)
        self.screen.blit(psurf, (panel_rect[0], panel_rect[1]))
        pygame.draw.rect(self.screen, (COLOR_ACCENT[0], COLOR_ACCENT[1], COLOR_ACCENT[2], 60), panel_rect, 1, border_radius=10)

        for i in range(self.scroll_offset, end):
            row = i - self.scroll_offset
            y = start_y + row * row_h
            hovered = margin_l <= mx <= margin_l + content_w and y <= my <= y + row_h - 5

            rect = pygame.Rect(margin_l, y, content_w, row_h - 5)
            
            if i == self.selected_group_idx:
                pygame.draw.rect(self.screen, COLOR_SELECTED_BG, rect, border_radius=5)
                pygame.draw.rect(self.screen, COLOR_ACCENT, rect, 2, border_radius=5)
                color = COLOR_ACCENT
            elif hovered:
                pygame.draw.rect(self.screen, COLOR_HOVERED_BG, rect, border_radius=5)
                color = COLOR_TEXT_PRIMARY
            else:
                color = COLOR_TEXT_SECONDARY

            group = self.song_groups[i]
            # Truncate Title if needed
            title_text = group['title']
            max_title_w = content_w - self._sx_v(180) # Reserve more space for circles
            if self.font.size(title_text)[0] > max_title_w:
                while self.font.size(title_text + "...")[0] > max_title_w and len(title_text) > 0:
                    title_text = title_text[:-1]
                title_text += "..."
                
            title_surf = self.font.render(title_text, True, color)
            self.screen.blit(title_surf, (margin_l + self._sx_v(15), y + self._s(8)))
            
            artist_surf = self.small_font.render(group['artist'], True, COLOR_TEXT_SECONDARY)
            self.screen.blit(artist_surf, (margin_l + self._sx_v(15), y + self._s(42)))
            
            # Difficulty indicators (Limited to 4 circles in list, anchored to right)
            base_dx = rect.right - self._sx_v(25)
            max_circles = 4
            charts = group['charts']
            display_charts = charts[-max_circles:]
            
            # 1. Draw up to 4 circles from right to left
            dx = base_dx
            for chart in reversed(display_charts):
                lv = chart['playlevel']
                lv_surf = self.small_font.render(str(lv), True, COLOR_TEXT_PRIMARY)
                pygame.draw.circle(self.screen, (80, 80, 100), (dx, y + row_h // 2 - 2), self._s(12))
                self.screen.blit(lv_surf, lv_surf.get_rect(center=(dx, y + row_h // 2 - 2)))
                dx -= self._sx_v(30)
            
            # 2. Draw +N label to the left of circles if necessary
            if len(charts) > max_circles:
                count_surf = self.small_font.render(f"+{len(charts)-max_circles}", True, COLOR_TEXT_SECONDARY)
                self.screen.blit(count_surf, count_surf.get_rect(midright=(dx + self._sx_v(5), y + row_h // 2 - 2)))

    def _draw_info_panel(self):
        if not self.song_groups: return
        group = self.song_groups[self.selected_group_idx]
        chart = group['charts'][self.selected_chart_idx]
        
        panel_x = self._sx_v(40)
        panel_y = self._s(110)
        panel_w = self._sx_v(290)
        panel_h = self.h - panel_y - self._s(50)
        
        # Glass Panel for Info (Using Surface for correct blending)
        psurf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        psurf.fill(COLOR_PANEL_BG)
        self.screen.blit(psurf, (panel_x, panel_y))
        pygame.draw.rect(self.screen, (COLOR_ACCENT[0], COLOR_ACCENT[1], COLOR_ACCENT[2], 60), (panel_x, panel_y, panel_w, panel_h), 1, border_radius=15)

        # Content
        cx = panel_x + 25
        y = panel_y + 30
        
        # Genre
        self.screen.blit(self.small_font.render(group['genre'].upper(), True, COLOR_ACCENT), (cx, y))
        y += self._s(30)
        
        # Title (Use chart specific title, limit to 1 line to prevent vertical overflow)
        title_text = chart['title']
        if self.title_font.size(title_text)[0] > (panel_w - 50):
            while self.title_font.size(title_text + "...")[0] > (panel_w - 50) and len(title_text) > 0:
                title_text = title_text[:-1]
            title_text += "..."
        self.screen.blit(self.title_font.render(title_text.strip(), True, COLOR_TEXT_PRIMARY), (cx, y))
        y += self._s(45) # Tighter spacing
        
        # Artist (Use chart specific artist, truncate if too long)
        artist_text = chart['artist']
        if self.font.size(artist_text)[0] > (panel_w - 50):
            while self.font.size(artist_text + "...")[0] > (panel_w - 50) and len(artist_text) > 0:
                artist_text = artist_text[:-1]
            artist_text += "..."
        self.screen.blit(self.font.render(artist_text, True, COLOR_TEXT_SECONDARY), (cx, y))
        y += self._s(50) # Tighter spacing
        
        # Stats Grid
        stats = [
            ("BPM", str(chart['bpm'])),
            ("NOTES", str(chart['total_notes'])),
            ("LEVEL", f"Lv.{chart['playlevel']}")
        ]
        
        y += self._s(15) # Add some breathing room before the grid
        stat_x = cx
        stat_spacing = self._sx_v(115) # Increased from 100 for better separation
        for label, val in stats:
            self.screen.blit(self.small_font.render(label, True, COLOR_ACCENT_DIM), (stat_x, y))
            # Increased vertical gap between label and value (25 -> 32 scaled)
            self.screen.blit(self.font_bold.render(val, True, COLOR_TEXT_PRIMARY), (stat_x, y + self._s(32)))
            stat_x += stat_spacing
        
        y += self._s(110) # Increased from 100
        
        # Difficulty Selector (Ultra Compact)
        self.screen.blit(self.small_font.render("SELECT DIFFICULTY (Left / Right)", True, COLOR_ACCENT_DIM), (cx, y))
        y += self._s(30)
        
        dx = cx
        row_limit = cx + panel_w - 40
        icon_size = self._sx_v(32)
        spacing = self._sx_v(38)
        
        for idx, c in enumerate(group['charts']):
            is_sel = idx == self.selected_chart_idx
            
            # Wrap if too many
            if dx + spacing > row_limit:
                dx = cx
                y += spacing + self._s(5)
            
            rect = pygame.Rect(dx, y, icon_size, icon_size)
            color = COLOR_ACCENT if is_sel else (60, 60, 80)
            pygame.draw.rect(self.screen, color, rect, border_radius=4)
            
            # Use very small font for level if needed
            lv_text = self.small_font.render(str(c['playlevel']), True, (255, 255, 255) if is_sel else (180, 180, 200))
            self.screen.blit(lv_text, lv_text.get_rect(center=rect.center))
            
            if is_sel:
                pygame.draw.rect(self.screen, (255, 255, 255), rect, 2, border_radius=4)
            
            dx += spacing



    def _wrap_text(self, text, font, max_w):
        words = text.split(' ')
        lines = []
        cur = ""
        for w in words:
            test = cur + w + " "
            if font.size(test)[0] < max_w:
                cur = test
            else:
                lines.append(cur)
                cur = w + " "
        lines.append(cur)
        return lines

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
            self.small_font.render("Type query and press ENTER to search directly on your browser.", True, COLOR_TEXT_SECONDARY),
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

