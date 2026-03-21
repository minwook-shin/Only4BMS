import glob
import os
import sys
import webbrowser
import math
import subprocess
import pygame
from only4bms.i18n import get as _t, FONT_NAME
from only4bms import i18n as _i18n
from only4bms import paths

from ..core.bms_parser import BMSParser
from .components import (
    make_bg_cache, draw_glass_panel, draw_outer_glow,
    draw_glow_text, draw_hint_bar, draw_scrollbar, draw_pill_button,
    draw_modal,
    C_TEXT_PRIMARY, C_TEXT_SECONDARY, C_TEXT_DIM,
    C_GLOW_CYAN, C_GLOW_PURPLE, C_BORDER_DIM,
    C_GLASS_FILL, C_GLASS_HOVER, C_GLASS_SELECT,
    BASE_W, BASE_H,
)

# ── Base (windowed) resolution ────────────────────────────────────────────
VISIBLE_ITEMS = 6
BMS_EXTS = ('*.bms', '*.bme', '*.bml', '*.pms')
SEARCH_URL = "https://bmssearch.net/search?q={}"

# Legacy aliases (used by click handler logic)
COLOR_ACCENT        = C_GLOW_CYAN
COLOR_ACCENT_DIM    = (0, 150, 120)
COLOR_SELECTED_BG   = ( 40,  50,  80, 225)
COLOR_HOVERED_BG    = ( 35,  35,  60, 160)
COLOR_TEXT_PRIMARY  = C_TEXT_PRIMARY
COLOR_TEXT_SECONDARY= C_TEXT_SECONDARY
COLOR_PANEL_BG      = ( 15,  15,  25, 130)


class SongSelectMenu:
    def __init__(self, settings, renderer, window, mode='single', song_groups=None, extra_opts=None, extra_nav_buttons=None):
        from pygame._sdl2.video import Texture
        self.renderer = renderer
        self.window = window
        self.mode = mode
        self.extra_opts = extra_opts or []
        self.extra_nav_buttons = extra_nav_buttons or []
        from ..game.note_mods import get_mod_ids
        self.note_mods = get_mod_ids()
        self.note_mod_idx = settings.get('note_mod_idx', 0)
        
        self.w, self.h = self.window.size
        self.sx, self.sy = self.w / BASE_W, self.h / BASE_H
        
        # We use an offscreen surface named 'self.screen' so all existing 
        # draw calls in this class keep working without modification.
        self.screen  = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.texture = None  # Will hold the uploaded frame
        self._bg     = make_bg_cache(self.w, self.h)
        self.view_offset = 0  # scroll position restored from settings
        
        pygame.display.set_caption(_t("song_selection_caption"))
        self.clock = pygame.time.Clock()
        self.font = _i18n.font("select_body", self.sy)
        self.font_bold = _i18n.font("select_bold", self.sy, bold=True)
        self.small_font = _i18n.font("select_small", self.sy)
        self.title_font = _i18n.font("select_title", self.sy, bold=True)
        self.settings = settings

        # BMS directory
        self.bms_dir = paths.SONG_DIR

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
        self._nav_buttons = []

        # Input debouncing
        self.ignore_enter = pygame.key.get_pressed()[pygame.K_RETURN]

        # ChallengeManager is loaded once — reading disk every frame was causing microstutters
        from ..game.challenge import ChallengeManager
        self._cm = ChallengeManager()

        # Core data
        self.song_groups = []
        self._scanning = False
        if song_groups is not None:
            self.song_groups = song_groups
            # Restore last hovered position from cache
            last_path = self.settings.get('last_hovered_path')
            if last_path:
                for g_idx, group in enumerate(self.song_groups):
                    for c_idx, chart in enumerate(group.get('charts', [])):
                        if chart.get('filepath') == last_path:
                            self.selected_group_idx = g_idx
                            self.selected_chart_idx = c_idx
                            self.view_offset = max(0, g_idx - 2)
                            break
        else:
            self._start_scan()
                
        self.last_previewed_path = None

    def _s(self, v):
        """Scale a base-800x600 value to current resolution."""
        return max(1, int(v * self.sy))

    def _sx_v(self, v):
        """Scale X-axis value."""
        return max(1, int(v * self.sx))

    def _save(self):
        """Persist settings to disk."""
        from ..main import save_settings
        save_settings(self.settings)

    def _cycle_skin(self):
        """Advance note_skin to the next unlocked skin (wraps back to default)."""
        from ..game.skins import get_available_skins
        options = ['default'] + [s.id for s in get_available_skins(self._cm)]
        current = self.settings.get('note_skin', 'default')
        if current not in options:
            current = 'default'
        self.settings['note_skin'] = options[(options.index(current) + 1) % len(options)]

    # ── Song Scanning ────────────────────────────────────────────────────

    def _start_scan(self):
        """Begin a cooperative scan — collects file list, then parses incrementally."""
        self._scanning = True
        self._scan_groups = {}
        # Collect file list (fast, no parsing)
        bms_files = []
        os.makedirs(self.bms_dir, exist_ok=True)
        for ext in BMS_EXTS:
            search_pattern = os.path.join(glob.escape(self.bms_dir), '**', ext)
            bms_files.extend(glob.glob(search_pattern, recursive=True))
        self._scan_queue = bms_files
        self._scan_total = len(bms_files)
        print(f"Scanning song directory: {self.bms_dir} ({self._scan_total} files)")

    def _scan_tick(self):
        """Parse one BMS file per call. Call this every frame during scanning."""
        if not self._scanning or not self._scan_queue:
            # Done — finalise
            self.song_groups = list(self._scan_groups.values())
            for g in self.song_groups:
                g['charts'].sort(key=lambda x: int(x['playlevel']) if x['playlevel'].isdigit() else 0)
            if not self.song_groups:
                self._create_mock_song()
            self._scanning = False
            # Restore last hovered position
            last_path = self.settings.get('last_hovered_path')
            if last_path:
                for g_idx, group in enumerate(self.song_groups):
                    for c_idx, chart in enumerate(group.get('charts', [])):
                        if chart.get('filepath') == last_path:
                            self.selected_group_idx = g_idx
                            self.selected_chart_idx = c_idx
                            self.view_offset = max(0, g_idx - 2)
                            return
            return

        # Parse a batch (up to 5 files per frame for speed)
        for _ in range(min(5, len(self._scan_queue))):
            f = self._scan_queue.pop(0)
            try:
                folder = os.path.dirname(f)
                res = BMSParser(f).get_metadata()
                title, artist, bpm, playlevel, genre, total_notes, preview_path, stagefile, banner, h_val, lanes_comp = res
                chart_data = {
                    'filepath': f, 'title': title, 'artist': artist,
                    'bpm': bpm, 'playlevel': playlevel, 'genre': genre,
                    'total_notes': total_notes, 'preview_path': preview_path,
                    'stagefile': stagefile, 'banner': banner, 'hash': h_val,
                    'lanes_compressed': lanes_comp
                }
                if folder not in self._scan_groups:
                    self._scan_groups[folder] = {
                        'folder': folder, 'title': title, 'artist': artist,
                        'genre': genre, 'preview_path': preview_path,
                        'stagefile': stagefile, 'banner': banner,
                        'charts': [chart_data]
                    }
                else:
                    self._scan_groups[folder]['charts'].append(chart_data)
            except Exception as e:
                print(f"Error parsing {f}: {e}")




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
            if self._scanning:
                self._scan_tick()
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
        
        # Save state to settings
        if self.song_groups and self.selected_group_idx < len(self.song_groups):
            group = self.song_groups[self.selected_group_idx]
            charts = group.get('charts', [])
            if self.selected_chart_idx < len(charts):
                self.settings['last_hovered_path'] = charts[self.selected_chart_idx]['filepath']
                
        self.settings['note_mod_idx'] = self.note_mod_idx

        return self.action, self.selected_song_path, self.note_mods[self.note_mod_idx]

    def _open_bms_folder(self):
        """Open the system file explorer to the BMS song directory."""
        path = os.path.abspath(self.bms_dir)
        
        if not os.path.exists(path):
            try:
                os.makedirs(path)
            except Exception as e:
                print(f"Error creating BMS folder: {e}")
                return
        
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

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
                if self.search_mode:
                    self._handle_search_key(event)
                    continue
                self._handle_nav_key(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_click(event.pos, event.button)
            elif event.type == pygame.JOYBUTTONDOWN:
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
            self.settings['note_mod_idx'] = self.note_mod_idx
            self._save()
        elif key == pygame.K_o: # Open BMS folder
            self._open_bms_folder()
        elif key == pygame.K_1: # Dec Speed
            self.settings['speed'] = max(0.1, self.settings.get('speed', 1.0) - 0.1)
            self._save()
        elif key == pygame.K_2: # Inc Speed
            self.settings['speed'] = min(2.0, self.settings.get('speed', 1.0) + 0.1)
            self._save()
        elif key == pygame.K_t: # Toggle Note Type
            self.settings['note_type'] = 1 if self.settings.get('note_type', 0) == 0 else 0
            self._save()
        elif key == pygame.K_F3 or key == pygame.K_b: # Search BMS
            self.search_mode = True
            self.search_query = ""
        elif key == pygame.K_F5 or key == pygame.K_r: # Reload BMS
            self.song_groups = []
            self._start_scan()
        elif key == pygame.K_s: # Settings shortcut
            self.action = "SETTINGS"
            self.running = False
            pygame.mixer.music.stop()
        elif key == pygame.K_g: # Toggle Note Skin
            self._cycle_skin()
            self._save()

    def _handle_click(self, pos, button=1):
        if self.search_mode:
            return
        mx, my = pos

        # Check Gameplay Options Rects
        for r, action in getattr(self, '_opt_rects', []):
            if r.collidepoint(mx, my):
                if action == "SPEED":
                    delta = -0.1 if button == 1 else 0.1
                    self.settings['speed'] = max(0.1, min(2.0, self.settings.get('speed', 1.0) + delta))
                elif action == "TYPE": self.settings['note_type'] = 1 if self.settings.get('note_type', 0) == 0 else 0
                elif action == "SKIN":
                    self._cycle_skin()
                else:
                    for opt in self.extra_opts:
                        if action == opt['action']:
                            opt['on_click']()
                            break
                self._save()
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
                    self.song_groups = []
                    self._start_scan()
                elif btn_action == "OPEN_FOLDER":
                    self._open_bms_folder()
                elif btn_action == "MOD":
                    self.note_mod_idx = (self.note_mod_idx + 1) % len(self.note_mods)
                else:
                    for nav_opt in self.extra_nav_buttons:
                        if btn_action == nav_opt['action']:
                            nav_opt['on_click']()
                            break
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
        # ── Background ──
        self.screen.blit(self._bg, (0, 0))
        if self.bg_surf:
            try:
                bx = (self.w - self.bg_surf.get_width())  // 2
                by = (self.h - self.bg_surf.get_height()) // 2
                self.screen.blit(self.bg_surf, (bx, by))
                dim = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
                dim.fill((0, 0, 0, 140))
                self.screen.blit(dim, (0, 0))
            except Exception:
                pass

        # ── Main Panels ──
        self._draw_info_panel()
        self._draw_song_list()

        # ── Title ──
        draw_glow_text(self.screen, _t("music_selection"), self.title_font,
                       C_GLOW_CYAN, C_GLOW_CYAN,
                       (self._sx_v(40), self._s(18)), glow_radius=3)

        # ── Nav pill buttons (right-aligned) ──
        mx, my = pygame.mouse.get_pos()
        self._nav_buttons = []
        btn_labels = [
            (_t("settings_btn"),  "SETTINGS"),
            (_t("open_folder"),   "OPEN_FOLDER"),
            (_t("search_bms"),    "SEARCH"),
            (_t("reload"),        "RELOAD"),
        ]
        bx = self.w - self._sx_v(30)
        btn_h = self._s(28)
        btn_y = self._s(22)
        for label, action in btn_labels:
            tw = self.small_font.size(label)[0] + self._sx_v(18)
            bx -= tw
            rect    = pygame.Rect(bx, btn_y, tw, btn_h)
            hovered = rect.collidepoint(mx, my)
            draw_pill_button(self.screen, rect, label, self.small_font, hovered=hovered)
            self._nav_buttons.append((rect, action))
            bx -= self._sx_v(10)

        for nav_opt in self.extra_nav_buttons:
            label = nav_opt['label_fn']()
            tw = self.small_font.size(label)[0] + self._sx_v(18)
            bx -= tw
            rect    = pygame.Rect(bx, btn_y, tw, btn_h)
            hovered = rect.collidepoint(mx, my)
            draw_pill_button(self.screen, rect, label, self.small_font,
                             hovered=hovered, accent=C_GLOW_PURPLE)
            self._nav_buttons.append((rect, nav_opt['action']))
            bx -= self._sx_v(10)

        # ── States ──
        if self._scanning:
            self._draw_scan_spinner()
        elif not self.song_groups:
            msg = self.font.render(_t("no_bms_files"), True, C_TEXT_SECONDARY)
            self.screen.blit(msg, (self._sx_v(370), self._s(160)))

        # ── Hint bar ──
        draw_hint_bar(self.screen,
                      "↑ ↓  Song    ← →  Difficulty    ENTER  Play    TAB  Settings    ESC  Back",
                      self.small_font, self.h, self.w)

        if self.search_mode:
            self._draw_search_overlay()

    def _draw_scan_spinner(self):
        """Draw a circular loading spinner during background scan."""
        # Draw inside the right-side song list area
        list_cx = self._sx_v(360) + self._sx_v(200)
        cy = self.h // 2
        r  = self._s(28)
        t  = pygame.time.get_ticks() / 1000.0

        for i in range(8):
            angle = t * 4.0 + i * (math.pi / 4)
            alpha = int(255 * (1.0 - i / 8.0))
            ex = int(list_cx + r * math.cos(angle))
            ey = int(cy      + r * math.sin(angle))
            sz = max(2, self._s(4) - i // 2)
            dot = pygame.Surface((sz * 2, sz * 2), pygame.SRCALPHA)
            pygame.draw.circle(dot, (*C_GLOW_CYAN, alpha), (sz, sz), sz)
            self.screen.blit(dot, (ex - sz, ey - sz))

        done  = self._scan_total - len(getattr(self, '_scan_queue', []))
        label = f"{_t('scanning')} {done}/{self._scan_total}"
        txt   = self.small_font.render(label, True, C_TEXT_SECONDARY)
        self.screen.blit(txt, txt.get_rect(center=(list_cx, cy + r + self._s(18))))

    def _draw_song_list(self):
        from ..game.constants import DIFFICULTY_DEFS, DIFFICULTY_DEFAULT_COLOR

        def get_diff_label(chart):
            f = chart['filepath'].lower()
            for d in DIFFICULTY_DEFS:
                if any(kw in f for kw in d['keywords']):
                    return d['label']
            return "LV."

        def get_diff_color(label):
            for d in DIFFICULTY_DEFS:
                if label == d['label']:
                    return d['color']
            return DIFFICULTY_DEFAULT_COLOR

        mx, my  = pygame.mouse.get_pos()
        row_h   = self._s(70)
        start_y = self._s(70)
        margin_l  = self._sx_v(360)
        content_w = self._sx_v(400)
        end = min(len(self.song_groups), self.scroll_offset + VISIBLE_ITEMS)

        # Glass panel behind the whole list
        panel_rect = pygame.Rect(margin_l - self._sx_v(8), start_y - self._s(8),
                                 content_w + self._sx_v(16),
                                 VISIBLE_ITEMS * row_h + self._s(16))
        draw_glass_panel(self.screen, panel_rect,
                         border_color=(*C_GLOW_CYAN, 55), radius=12, fill_alpha=10)

        for i in range(self.scroll_offset, end):
            row = i - self.scroll_offset
            y   = start_y + row * row_h
            is_sel = (i == self.selected_group_idx)
            hovered = (margin_l <= mx <= margin_l + content_w and y <= my <= y + row_h - 5
                       and not is_sel)

            rect = pygame.Rect(margin_l, y, content_w, row_h - self._s(5))

            if is_sel:
                fill   = (*C_GLOW_CYAN, 20)
                border = (*C_GLOW_CYAN, 200)
                draw_outer_glow(self.screen, rect, C_GLOW_CYAN, radius=8, passes=3, max_alpha=30)
                # Selected pip
                pip_h = rect.height - 10
                pygame.draw.rect(self.screen, C_GLOW_CYAN,
                                 pygame.Rect(rect.x + 3, rect.y + 5, 3, pip_h), border_radius=2)
            elif hovered:
                fill   = (*C_GLOW_CYAN, 10)
                border = (*C_GLOW_CYAN, 80)
            else:
                fill   = C_GLASS_FILL
                border = C_BORDER_DIM

            bg = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(bg, fill, (0, 0, *rect.size), border_radius=8)
            self.screen.blit(bg, rect.topleft)
            pygame.draw.rect(self.screen, border, rect, 1, border_radius=8)

            group = self.song_groups[i]

            # Title
            title_text = group['title']
            max_title_w = content_w - self._sx_v(185)
            if self.font.size(title_text)[0] > max_title_w:
                while self.font.size(title_text + "...")[0] > max_title_w and len(title_text) > 0:
                    title_text = title_text[:-1]
                title_text += "..."

            title_col  = C_GLOW_CYAN if is_sel else C_TEXT_PRIMARY
            title_surf = self.font.render(title_text, True, title_col)
            self.screen.blit(title_surf, (margin_l + self._sx_v(14), y + self._s(8)))

            artist_surf = self.small_font.render(group['artist'], True, C_TEXT_SECONDARY)
            self.screen.blit(artist_surf, (margin_l + self._sx_v(14), y + self._s(42)))

            # Difficulty badges
            charts     = group['charts']
            num_badges = 4
            num_charts = len(charts)
            if i == self.selected_group_idx:
                start = max(0, self.selected_chart_idx - 1)
                if start + num_badges > num_charts:
                    start = max(0, num_charts - num_badges)
                end_idx = min(num_charts, start + num_badges)
            else:
                start   = 0
                end_idx = min(num_charts, num_badges)

            group['badge_rects'] = []
            base_dx = rect.right - self._sx_v(38)
            dx      = base_dx

            if start > 0:
                self.screen.blit(self.small_font.render("<", True, C_TEXT_DIM),
                                 (dx - self._sx_v(14), y + row_h // 2 - 10))
                dx -= self._sx_v(18)

            for v_idx, chart in enumerate(reversed(charts[start:end_idx])):
                actual_idx = start + (len(charts[start:end_idx]) - 1 - v_idx)
                label   = get_diff_label(chart)
                lv      = str(chart['playlevel'])
                txt     = f"{label} {lv}"
                bg_color = get_diff_color(label)

                t_surf  = self.small_font.render(txt, True, (255, 255, 255))
                tw, th  = t_surf.get_width() + self._sx_v(10), self._s(20)
                br      = pygame.Rect(dx - tw, y + row_h // 2 - th // 2, tw, th)

                is_sel_chart = (self.selected_group_idx == i and self.selected_chart_idx == actual_idx)
                if is_sel_chart:
                    pygame.draw.rect(self.screen, (255, 255, 255), br.inflate(4, 4), border_radius=4)

                pygame.draw.rect(self.screen, bg_color, br, border_radius=4)
                self.screen.blit(t_surf, t_surf.get_rect(center=br.center))

                if self.selected_group_idx == i:
                    group['badge_rects'].append((br, actual_idx))

                dx -= tw + self._sx_v(7)

            if end_idx < num_charts:
                self.screen.blit(self.small_font.render(">", True, C_TEXT_DIM),
                                 (base_dx + self._sx_v(4), y + row_h // 2 - 10))

        # Scrollbar
        if len(self.song_groups) > VISIBLE_ITEMS:
            sb_x = margin_l + content_w + self._sx_v(4)
            r0   = self.scroll_offset / len(self.song_groups)
            r1   = min(1.0, (self.scroll_offset + VISIBLE_ITEMS) / len(self.song_groups))
            draw_scrollbar(self.screen, sb_x, start_y, VISIBLE_ITEMS * row_h, r0, r1)

    def _draw_info_panel(self):
        if not self.song_groups: return
        mx, my = pygame.mouse.get_pos()
        group  = self.song_groups[self.selected_group_idx]
        chart  = group['charts'][self.selected_chart_idx]

        panel_x = self._sx_v(30)
        panel_y = self._s(62)
        panel_w = self._sx_v(300)
        panel_h = self.h - panel_y - self._s(50)
        draw_glass_panel(self.screen, pygame.Rect(panel_x, panel_y, panel_w, panel_h),
                         border_color=(*C_GLOW_CYAN, 65), radius=14, fill_alpha=12)

        cx = panel_x + self._sx_v(16)
        y  = panel_y + self._s(16)

        # Genre pill
        genre_s = self.small_font.render(group['genre'].upper(), True, C_GLOW_CYAN)
        self.screen.blit(genre_s, (cx, y))
        y += genre_s.get_height() + self._s(8)

        # Title
        title_text = chart['title']
        max_w = panel_w - self._sx_v(32)
        if self.title_font.size(title_text)[0] > max_w:
            while self.title_font.size(title_text + "...")[0] > max_w and len(title_text) > 0:
                title_text = title_text[:-1]
            title_text += "..."
        t_surf = self.title_font.render(title_text.strip(), True, C_TEXT_PRIMARY)
        self.screen.blit(t_surf, (cx, y))
        y += t_surf.get_height() + self._s(6)

        # Artist
        artist_text = chart['artist']
        if self.font.size(artist_text)[0] > max_w:
            while self.font.size(artist_text + "...")[0] > max_w and len(artist_text) > 0:
                artist_text = artist_text[:-1]
            artist_text += "..."
        a_surf = self.font.render(artist_text, True, C_TEXT_SECONDARY)
        self.screen.blit(a_surf, (cx, y))
        y += a_surf.get_height() + self._s(18)

        # Divider
        dw = panel_w - self._sx_v(32)
        div = pygame.Surface((dw, 1), pygame.SRCALPHA)
        for x in range(dw):
            t = 1.0 - abs(x - dw / 2) / (dw / 2 + 1)
            div.set_at((x, 0), (*C_GLOW_CYAN, int(40 * t)))
        self.screen.blit(div, (cx, y))
        y += self._s(14)

        # Stats grid
        stats = [("BPM", str(chart['bpm'])), ("NOTES", str(chart['total_notes'])),
                 ("LEVEL", f"Lv.{chart['playlevel']}")]
        stat_x = cx
        stat_col_w = (panel_w - self._sx_v(32)) // 3
        for label, val in stats:
            self.screen.blit(self.small_font.render(label, True, C_TEXT_DIM), (stat_x, y))
            self.screen.blit(self.font_bold.render(val, True, C_TEXT_PRIMARY),
                             (stat_x, y + self._s(22)))
            stat_x += stat_col_w
        y += self._s(64)

        # ── Gameplay Options ──
        opt_hdr = self.small_font.render(_t("gameplay_options"), True, C_GLOW_CYAN)
        self.screen.blit(opt_hdr, (cx, y))
        y += opt_hdr.get_height() + self._s(8)

        opt_rects = []
        iy        = self._s(30)

        def _opt_row(label_text, action, color=C_TEXT_SECONDARY):
            nonlocal y
            r = pygame.Rect(cx - self._sx_v(4), y, panel_w - self._sx_v(24), iy - self._s(2))
            hov = r.collidepoint(mx, my)
            if hov:
                bg = pygame.Surface(r.size, pygame.SRCALPHA)
                pygame.draw.rect(bg, (*C_GLOW_CYAN, 10), (0, 0, *r.size), border_radius=6)
                self.screen.blit(bg, r.topleft)
            s = self.small_font.render(label_text, True, C_GLOW_CYAN if hov else color)
            self.screen.blit(s, (cx, y + (iy - s.get_height()) // 2))
            opt_rects.append((r, action))
            y += iy

        speed  = self.settings.get('speed', 1.0)
        _opt_row(f"{_t('speed_label')}: x{speed:.1f}  (1 / 2)", "SPEED")

        n_type = "CIRCLE" if self.settings.get('note_type', 0) == 1 else "BAR"
        _opt_row(f"{_t('player_note')}: {n_type}  (T)", "TYPE")

        for opt in self.extra_opts:
            _opt_row(opt['label_fn'](), opt['action'])

        # Note skin
        from ..game.skins import get_skin, get_available_skins
        available_skins  = get_available_skins(self._cm)
        current_skin_id  = self.settings.get('note_skin', 'default')
        current_skin_obj = get_skin(current_skin_id)
        if current_skin_obj and not current_skin_obj.is_unlocked(self._cm):
            self.settings['note_skin'] = 'default'
            current_skin_id  = 'default'
            current_skin_obj = None
        if available_skins:
            skin_label = current_skin_obj.get_display_name() if current_skin_obj else _t("note_skin_default")
            skin_color = current_skin_obj.ui_color if current_skin_obj else C_TEXT_SECONDARY
            _opt_row(f"{_t('note_skin_label')}: {skin_label}  (G)", "SKIN", color=skin_color)
        else:
            _opt_row(f"{_t('note_skin_label')}: {_t('note_skin_default')}", "SKIN")

        self._opt_rects = opt_rects

        # ── Note Mod ──
        y += self._s(10)
        self.screen.blit(self.small_font.render(_t("note_mod_label"), True, C_TEXT_DIM), (cx, y))
        y += self._s(22)
        mod_rect  = pygame.Rect(cx - self._sx_v(4), y, panel_w - self._sx_v(24), self._s(30))
        hover_mod = mod_rect.collidepoint(mx, my)
        if hover_mod:
            bg = pygame.Surface(mod_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(bg, (*C_GLOW_CYAN, 10), (0, 0, *mod_rect.size), border_radius=6)
            self.screen.blit(bg, mod_rect.topleft)
        mod_text = self.note_mods[self.note_mod_idx]
        mod_surf = self.small_font.render(mod_text, True, C_GLOW_CYAN if hover_mod else C_TEXT_PRIMARY)
        self.screen.blit(mod_surf, (cx, y + (self._s(30) - mod_surf.get_height()) // 2))
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
        # Dim overlay
        dim = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 200))
        self.screen.blit(dim, (0, 0))

        # Modal panel
        pw, ph = self._sx_v(580), self._s(180)
        px = (self.w - pw) // 2
        py = self.h // 2 - ph // 2 - self._s(20)
        panel = pygame.Rect(px, py, pw, ph)

        base = pygame.Surface(panel.size, pygame.SRCALPHA)
        pygame.draw.rect(base, (10, 8, 22, 235), (0, 0, *panel.size), border_radius=14)
        self.screen.blit(base, panel.topleft)
        draw_glass_panel(self.screen, panel, border_color=(*C_GLOW_CYAN, 180), radius=14, fill_alpha=18)

        y = py + self._s(18)
        title_s = self.font.render(_t("search_web_title"), True, C_GLOW_CYAN)
        self.screen.blit(title_s, title_s.get_rect(centerx=self.w // 2, top=y))
        y += title_s.get_height() + self._s(14)

        # Input box
        bw = pw - self._sx_v(40)
        bx = px + self._sx_v(20)
        bh = self._s(44)
        box_r = pygame.Rect(bx, y, bw, bh)
        box_bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pygame.draw.rect(box_bg, (*C_GLOW_CYAN, 10), (0, 0, bw, bh), border_radius=8)
        self.screen.blit(box_bg, (bx, y))
        pygame.draw.rect(self.screen, (*C_GLOW_CYAN, 160), box_r, 1, border_radius=8)

        q_surf = self.font.render(self.search_query + "_", True, C_TEXT_PRIMARY)
        self.screen.blit(q_surf, (bx + self._sx_v(10), y + (bh - q_surf.get_height()) // 2))
        y += bh + self._s(14)

        hint_s = self.small_font.render(_t("search_hint"), True, C_TEXT_DIM)
        self.screen.blit(hint_s, hint_s.get_rect(centerx=self.w // 2, top=y))
