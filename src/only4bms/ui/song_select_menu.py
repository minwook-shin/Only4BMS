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
        self.note_mods = ['None', 'Mirror', 'Random']
        self.note_mod_idx = 0
        
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

        # Core data
        self.song_groups = []
        self.scan_songs()
        
        self.last_previewed_path = None

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
                title, artist, bpm, playlevel, genre, total_notes, preview_path, stagefile, banner, h_val = res
                
                chart_data = {
                    'filepath': f, 'title': title, 'artist': artist,
                    'bpm': bpm, 'playlevel': playlevel, 'genre': genre,
                    'total_notes': total_notes, 'preview_path': preview_path,
                    'stagefile': stagefile, 'banner': banner, 'hash': h_val
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
        return self.action, self.selected_song_path, self.ai_difficulties[self.ai_diff_idx], self.note_mods[self.note_mod_idx]

    # ── Event handling ───────────────────────────────────────────────────

    def _handle_events(self):
        from ..main import refresh_joysticks
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                refresh_joysticks()
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
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_click(event.pos, event.button)
            elif event.type == pygame.JOYBUTTONDOWN:
                if self.show_guide:
                    self.show_guide = False
                    continue
                if self.search_mode:
                    continue
                if event.button == 0: # A
                    self._select_play()
                elif event.button == 1: # B
                    self.action = "MENU"
                    self.running = False
                    pygame.mixer.music.stop()
                elif event.button == 3: # Y (Settings)
                    self.action = "SETTINGS"
                    self.running = False
                    pygame.mixer.music.stop()
                elif event.button == 2: # X (Mod)
                    self.note_mod_idx = (self.note_mod_idx + 1) % len(self.note_mods)
            elif event.type == pygame.JOYHATMOTION:
                if self.show_guide or self.search_mode: continue
                vx, vy = event.value
                if vx == 0 and vy == 0: continue
                if vy == 1: self._move_selection(-1)
                elif vy == -1: self._move_selection(+1)
                elif vx == -1: self._move_chart_selection(-1)
                elif vx == 1: self._move_chart_selection(+1)

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
        elif key == pygame.K_m: # Note Mod toggle
            self.note_mod_idx = (self.note_mod_idx + 1) % len(self.note_mods)
        elif key == pygame.K_1: # Dec Speed
            self.settings['speed'] = max(0.1, self.settings.get('speed', 1.0) - 0.1)
        elif key == pygame.K_2: # Inc Speed
            self.settings['speed'] = min(2.0, self.settings.get('speed', 1.0) + 0.1)
        elif key == pygame.K_t: # Toggle Player Note Type
            self.settings['note_type'] = "Circle" if self.settings.get('note_type', "Bar") == "Bar" else "Bar"
        elif key == pygame.K_a: # Toggle AI Note Type
            self.settings['ai_note_type'] = "Circle" if self.settings.get('ai_note_type', "Bar") == "Bar" else "Bar"
        elif key == pygame.K_F3:
            self.search_mode = True
            self.search_query = ""
        elif key == pygame.K_F5:
            self.song_groups = []
            self.scan_songs()

    def _handle_click(self, pos, button=1):
        if self.show_guide:
            self.show_guide = False
            return
        if self.search_mode:
            return
        mx, my = pos

        # Check Gameplay Options Rects
        for r, action in getattr(self, '_opt_rects', []):
            if r.collidepoint(mx, my):
                if action == "SPEED": 
                    delta = -0.1 if button == 1 else 0.1
                    self.settings['speed'] = max(0.1, min(2.0, self.settings.get('speed', 1.0) + delta))
                elif action == "TYPE": self.settings['note_type'] = "Circle" if self.settings.get('note_type', "Bar") == "Bar" else "Bar"
                elif action == "AI_TYPE": self.settings['ai_note_type'] = "Circle" if self.settings.get('ai_note_type', "Bar") == "Bar" else "Bar"
                return

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
                elif btn_action == "MOD":
                    self.note_mod_idx = (self.note_mod_idx + 1) % len(self.note_mods)
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
                # 1. Check difficulty badges first
                group = self.song_groups[i]
                found_badge = False
                if button == 1:
                    for br, c_idx in group.get('badge_rects', []):
                        if br.collidepoint(mx, my):
                            self.selected_group_idx = i
                            self.selected_chart_idx = c_idx
                            self._update_background()
                            self.preview_timer = pygame.time.get_ticks()
                            found_badge = True
                            break
                
                if found_badge: break

                # 2. Main row click (select if already active, else switch group)
                if button == 1:
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
            
            # Difficulty indicators (Text badges in list)
            base_dx = rect.right - self._sx_v(40)
            charts = group['charts']
            
            # Map levels to short labels if possible
            def get_diff_label(chart):
                lv = str(chart['playlevel'])
                f = chart['filepath'].lower()
                if 'beginner' in f or '7b' in f or '5b' in f: return "BEG"
                if 'normal' in f or '7n' in f or '5n' in f: return "NOR"
                if 'hyper' in f or '7h' in f or '5h' in f: return "HYP"
                if 'another' in f or '7a' in f or '5a' in f: return "ANO"
                if 'insane' in f or '7i' in f: return "INS"
                return "LV."
            
            # Store badge rects for clicking
            group['badge_rects'] = []
            
            # Scrollable window of badges
            num_badges = 4
            num_charts = len(charts)
            
            # Find window range to show
            if i == self.selected_group_idx:
                # Center around selected_chart_idx
                start = max(0, self.selected_chart_idx - 1)
                if start + num_badges > num_charts:
                    start = max(0, num_charts - num_badges)
                end_idx = min(num_charts, start + num_badges)
            else:
                start = 0
                end_idx = min(num_charts, num_badges)

            group['badge_rects'] = []
            dx = base_dx
            
            # Show "more" indicator if there are charts before the window
            if start > 0:
                self.screen.blit(self.small_font.render("<", True, COLOR_TEXT_SECONDARY), (dx - self._sx_v(15), y + row_h // 2 - 10))
                dx -= self._sx_v(20)

            # Draw badges from left to right (actually anchor right and go left but in order)
            # Wait, it's easier to just draw them consistently.
            # Let's draw from dx going left-ish but let's calculate total width first or just iterate.
            
            visible_charts = charts[start:end_idx]
            # To keep right-alignment, we still iterate reversed(visible_charts) or similar.
            for v_idx, chart in enumerate(reversed(visible_charts)):
                actual_idx = start + (len(visible_charts) - 1 - v_idx)
                
                label = get_diff_label(chart)
                lv = str(chart['playlevel'])
                    
                label = get_diff_label(chart)
                lv = str(chart['playlevel'])
                txt = f"{label} {lv}"
                
                # Colors based on difficulty
                l_lower = label.lower()
                bg_color = (60, 60, 80)
                if l_lower == "beg": bg_color = (130, 200, 130)
                elif l_lower == "nor": bg_color = (100, 150, 255)
                elif l_lower == "hyp": bg_color = (255, 200, 100)
                elif l_lower == "ano": bg_color = (255, 100, 100)
                elif l_lower == "ins": bg_color = (200, 80, 255)
                
                t_surf = self.small_font.render(txt, True, (255, 255, 255))
                tw, th = t_surf.get_width() + self._sx_v(10), self._s(20)
                br = pygame.Rect(dx - tw, y + row_h // 2 - th // 2, tw, th)
                
                # Highlight if this is the selected chart for the *selected* group
                is_sel_chart = (self.selected_group_idx == i and self.selected_chart_idx == actual_idx)
                if is_sel_chart:
                    pygame.draw.rect(self.screen, (255, 255, 255), br.inflate(4, 4), border_radius=4)
                
                pygame.draw.rect(self.screen, bg_color, br, border_radius=4)
                self.screen.blit(t_surf, t_surf.get_rect(center=br.center))
                
                # Save hitbox (relative to screen)
                if self.selected_group_idx == i:
                    group['badge_rects'].append((br, actual_idx))
                
                dx -= tw + self._sx_v(8)
                
            # Show "more" indicator if there are charts after the window
            if end_idx < num_charts:
                self.screen.blit(self.small_font.render(">", True, COLOR_TEXT_SECONDARY), (base_dx + self._sx_v(5), y + row_h // 2 - 10))

    def _draw_info_panel(self):
        if not self.song_groups: return
        mx, my = pygame.mouse.get_pos()
        group = self.song_groups[self.selected_group_idx]
        chart = group['charts'][self.selected_chart_idx]
        
        panel_x = self._sx_v(40)
        panel_y = self._s(85) # Moved up from 110
        panel_w = self._sx_v(290)
        panel_h = self.h - panel_y - self._s(40) # Slightly taller panel
        
        # Glass Panel for Info (Using Surface for correct blending)
        psurf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        psurf.fill(COLOR_PANEL_BG)
        self.screen.blit(psurf, (panel_x, panel_y))
        pygame.draw.rect(self.screen, (COLOR_ACCENT[0], COLOR_ACCENT[1], COLOR_ACCENT[2], 60), (panel_x, panel_y, panel_w, panel_h), 1, border_radius=15)

        # Content
        cx = panel_x + 20
        y = panel_y + 20
        
        # Genre
        self.screen.blit(self.small_font.render(group['genre'].upper(), True, COLOR_ACCENT), (cx, y))
        y += self._s(25)
        
        # Title (Use chart specific title, limit to 1 line to prevent vertical overflow)
        title_text = chart['title']
        if self.title_font.size(title_text)[0] > (panel_w - 40):
            while self.title_font.size(title_text + "...")[0] > (panel_w - 40) and len(title_text) > 0:
                title_text = title_text[:-1]
            title_text += "..."
        self.screen.blit(self.title_font.render(title_text.strip(), True, COLOR_TEXT_PRIMARY), (cx, y))
        y += self._s(50) # Tighter spacing
        
        # Artist (Use chart specific artist, truncate if too long)
        artist_text = chart['artist']
        if self.font.size(artist_text)[0] > (panel_w - 40):
            while self.font.size(artist_text + "...")[0] > (panel_w - 40) and len(artist_text) > 0:
                artist_text = artist_text[:-1]
            artist_text += "..."
        self.screen.blit(self.font.render(artist_text, True, COLOR_TEXT_SECONDARY), (cx, y))
        y += self._s(55) # Tighter spacing
        
        # Stats Grid
        stats = [
            ("BPM", str(chart['bpm'])),
            ("NOTES", str(chart['total_notes'])),
            ("LEVEL", f"Lv.{chart['playlevel']}")
        ]
        
        y += self._s(10) # Add some breathing room before the grid
        stat_x = cx
        stat_spacing = self._sx_v(85)
        for label, val in stats:
            self.screen.blit(self.small_font.render(label, True, COLOR_ACCENT_DIM), (stat_x, y))
            self.screen.blit(self.font_bold.render(val, True, COLOR_TEXT_PRIMARY), (stat_x, y + self._s(24)))
            stat_x += stat_spacing
        
        y += self._s(100) # Tighter gap before Gameplay Options
        
        # ── GAMEPLAY OPTIONS ──
        self.screen.blit(self.small_font.render("GAMEPLAY OPTIONS", True, COLOR_ACCENT), (cx, y))
        y += self._s(25)
        
        opt_rects = []
        # Item spacing
        iy = self._s(28)
        
        # Speed
        speed = self.settings.get('speed', 1.0)
        s_rect = pygame.Rect(cx, y, panel_w - 40, iy)
        if s_rect.collidepoint(mx, my):
            pygame.draw.rect(self.screen, COLOR_HOVERED_BG, s_rect, border_radius=5)
        self.screen.blit(self.small_font.render(f"SPEED: x{speed:.1f} (1/2)", True, COLOR_TEXT_SECONDARY), (cx, y))
        opt_rects.append((s_rect, "SPEED"))
        y += iy
        
        y += iy
        
        # Player Note Type
        n_type = "CIRCLE" if self.settings.get('note_type', 0) == "Circle" else "BAR"
        t_rect = pygame.Rect(cx, y, panel_w - 40, iy)
        if t_rect.collidepoint(mx, my):
            pygame.draw.rect(self.screen, COLOR_HOVERED_BG, t_rect, border_radius=5)
        self.screen.blit(self.small_font.render(f"PLAYER NOTE: {n_type} (T)", True, COLOR_TEXT_SECONDARY), (cx, y))
        opt_rects.append((t_rect, "TYPE"))
        y += iy
        
        # AI Note Type
        ai_n_type = "CIRCLE" if self.settings.get('ai_note_type', 0) == "Circle" else "BAR"
        a_rect = pygame.Rect(cx, y, panel_w - 40, iy)
        if a_rect.collidepoint(mx, my):
            pygame.draw.rect(self.screen, COLOR_HOVERED_BG, a_rect, border_radius=5)
        self.screen.blit(self.small_font.render(f"AI NOTE: {ai_n_type} (A)", True, COLOR_TEXT_SECONDARY), (cx, y))
        opt_rects.append((a_rect, "AI_TYPE"))
        self._opt_rects = opt_rects # Store for click handler

        # ── NOTE MOD ──
        # Adding some space since records are gone
        y += self._s(40)
        self.screen.blit(self.small_font.render("NOTE MOD (M)", True, COLOR_ACCENT_DIM), (cx, y))
        y += self._s(25)
        mod_rect = pygame.Rect(cx, y, panel_w - 40, self._s(28))
        hover_mod = mod_rect.collidepoint(mx, my)
        if hover_mod:
            pygame.draw.rect(self.screen, COLOR_HOVERED_BG, mod_rect, border_radius=5)
        
        mod_text = self.note_mods[self.note_mod_idx]
        mod_surf = self.small_font.render(mod_text, True, COLOR_ACCENT if hover_mod else COLOR_TEXT_PRIMARY)
        self.screen.blit(mod_surf, (cx + 10, y + 2))
        self._nav_buttons.append((mod_rect, "MOD"))

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

