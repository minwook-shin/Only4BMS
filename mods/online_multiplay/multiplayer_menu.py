import pygame
import threading
import os
import time
import math
from only4bms.i18n import get as _host_t
from only4bms import i18n as _i18n
from .i18n import t as _t
from only4bms import paths
from only4bms.core.network_manager import NetworkManager
from only4bms.ui.components import (
    make_bg_cache, draw_glass_panel, draw_outer_glow,
    draw_glow_text, draw_hint_bar, draw_scrollbar, draw_row,
    C_TEXT_PRIMARY, C_TEXT_SECONDARY, C_TEXT_DIM,
    C_GLOW_CYAN, C_GLOW_PURPLE, C_BORDER_DIM,
    C_GLASS_FILL, C_GLASS_HOVER, C_GLASS_SELECT,
    BASE_W, BASE_H,
)

C_ONLINE_ACCENT = C_GLOW_CYAN
C_HOST_GOLD     = (255, 215,  50)


class MultiplayerMenu:
    def __init__(self, settings, renderer, window):
        from pygame._sdl2.video import Texture
        self.settings = settings
        self.renderer = renderer
        self.window   = window

        self.w, self.h = self.window.size
        self.sx, self.sy = self.w / BASE_W, self.h / BASE_H

        self.screen  = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.texture = None
        self._bg     = make_bg_cache(self.w, self.h)

        self.clock      = pygame.time.Clock()
        self.title_font = _i18n.font("menu_title",  self.sy, bold=True)
        self.font       = _i18n.font("menu_option", self.sy)
        self.small_font = _i18n.font("menu_small",  self.sy)
        self.body_font  = _i18n.font("ui_body",     self.sy)

        self.net = NetworkManager()
        if self.net.is_connected:
            self.state = "LOBBY"
            self.net.game_start_time = None
        else:
            self.state = "INPUT_ADDRESS"

        self.running          = True
        self.action           = "QUIT"
        self.selected_song_path = None

        self.address_input  = self.settings.get("last_server_ip", "127.0.0.1:5000")
        self.password_input = ""

        self.server_songs     = []
        self.available_bms    = []
        self.selected_song_idx = 0
        self.selected_bms_idx  = 0
        self.scroll_offset     = 0

        self.download_progress = 0
        self.download_total    = 0

        self.input_focus = 0  # 0: Address, 1: Password

        self.ms_idx    = 0
        self.ms_speed  = self.settings.get('speed', 1.0)
        self.ms_mod    = 0
        self.ms_buff   = 0
        self.ms_debuff = 0

        self.mod_opts    = ["None", "Random", "Mirror"]
        self.buff_opts   = ["None", "HP_BOOST", "HP_REGEN", "WINDOW_WIDE", "SPEED_SLOW"]
        self.debuff_opts = ["None", "HP_FRAGILE", "WINDOW_TIGHT", "SPEED_FAST", "HP_DRAIN"]

        self.ignore_keys = pygame.key.get_pressed()[pygame.K_RETURN]

    def _s(self, v): return max(1, int(v * self.sy))

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        from pygame._sdl2.video import Texture
        pygame.key.set_repeat(300, 50)
        pygame.event.clear()

        while self.running:
            self._handle_events()
            self._update_network_state()
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
        self.settings["last_server_ip"] = self.address_input
        return self.action, self.selected_song_path

    # ── Network state ─────────────────────────────────────────────────────────

    def _update_network_state(self):
        if self.net.join_error:
            self.state = "INPUT_PASSWORD"
            self.net.join_error = None

        elif self.state == "LOBBY":
            if not self.net.is_connected:
                self.state = "INPUT_ADDRESS"

            sel_song_id = self.net.lobby_state.get('selected_song_id')
            sel_bms     = self.net.lobby_state.get('selected_bms_file')
            if sel_song_id and sel_bms and self.net.player_id != self.net.host_id:
                self.state = "DOWNLOADING"
                threading.Thread(target=self._download_task, args=(sel_song_id, sel_bms), daemon=True).start()

        elif self.state == "WAITING_START":
            if self.net.game_start_time and time.time() >= self.net.game_start_time:
                self.action = "START_MULTI"
                self.running = False
            elif (self.net.game_start_time is None
                  and hasattr(self, '_waiting_since')
                  and time.time() - self._waiting_since > 30):
                print("[Net] start_game timeout — forcing local countdown")
                self.net.game_start_time = time.time() + 3.0

    def _download_task(self, song_id, target_bms=None):
        self.download_progress = 0
        self.download_total    = 1

        self.net._ready_sent         = False
        self.net.game_start_time     = None
        self.net.opponent_in_game    = False

        cache_dir = os.path.join(paths.SONG_DIR, ".multiplayer_cache")

        def progress_cb(cur, tot):
            self.download_progress = cur
            self.download_total    = tot

        success = self.net.download_song(song_id, cache_dir, progress_cb)

        if success:
            if target_bms:
                self.selected_song_path = os.path.join(cache_dir, song_id, target_bms)
            else:
                self.selected_song_path = os.path.join(cache_dir, song_id, "demo.bms")
                song_dir = os.path.join(cache_dir, song_id)
                for f in os.listdir(song_dir):
                    if f.lower().endswith(('.bms', '.bme', '.bml')):
                        self.selected_song_path = os.path.join(song_dir, f)
                        break

            self._waiting_since = time.time()
            self.state = "WAITING_START"
            self.net.send_ready()
        else:
            print("Download failed")
            self.net._ready_sent = False
            self.state = "LOBBY"

    # ── Events ────────────────────────────────────────────────────────────────

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYUP:
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.ignore_keys = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if   self.state == "MATCH_SETTINGS":   self.state = "DIFFICULTY_SELECT"
                    elif self.state == "DIFFICULTY_SELECT": self.state = "SONG_SELECT"
                    elif self.state == "SONG_SELECT":       self.state = "LOBBY"
                    elif self.state == "INPUT_PASSWORD":    self.state = "INPUT_ADDRESS"
                    else:
                        self.net.disconnect()
                        self.action = "MENU"
                        self.running = False
                    continue

                if self.state == "INPUT_ADDRESS":
                    if event.key in (pygame.K_TAB, pygame.K_DOWN, pygame.K_UP):
                        self.input_focus = 1 - self.input_focus
                    elif event.key == pygame.K_BACKSPACE:
                        if self.input_focus == 0:
                            self.address_input = self.address_input[:-1]
                        else:
                            self.password_input = self.password_input[:-1]
                    elif event.key == pygame.K_RETURN and not self.ignore_keys:
                        self.state = "CONNECTING"
                        def connect_thread():
                            if self.net.connect(self.address_input):
                                self.net.join_lobby(password=self.password_input)
                                self.state = "CONNECTING"
                                time.sleep(1)
                                if self.net.is_connected and not self.net.join_error and hasattr(self.net, 'player_id') and self.net.player_id:
                                    self.state = "LOBBY"
                                elif self.net.join_error:
                                    self.state = "INPUT_PASSWORD"
                            else:
                                self.state = "INPUT_ADDRESS"
                        threading.Thread(target=connect_thread, daemon=True).start()
                    else:
                        if event.unicode.isprintable():
                            if self.input_focus == 0 and len(self.address_input) < 40:
                                self.address_input += event.unicode
                            elif self.input_focus == 1 and len(self.password_input) < 40:
                                self.password_input += event.unicode

                elif self.state == "INPUT_PASSWORD":
                    if event.key == pygame.K_BACKSPACE:
                        self.password_input = self.password_input[:-1]
                    elif event.key == pygame.K_RETURN and not self.ignore_keys:
                        self.state = "CONNECTING"
                        self.net.join_lobby(password=self.password_input)
                        time.sleep(0.5)
                        if self.net.is_connected and not self.net.join_error:
                            self.state = "LOBBY"
                        else:
                            self.state = "INPUT_PASSWORD"
                    else:
                        if len(self.password_input) < 40 and event.unicode.isprintable():
                            self.password_input += event.unicode

                elif self.state == "LOBBY":
                    if event.key == pygame.K_RETURN and not self.ignore_keys:
                        if self.net.player_id == self.net.host_id:
                            self.state = "SONG_SELECT"
                            def fetch_songs():
                                self.server_songs = self.net.get_server_songs()
                            threading.Thread(target=fetch_songs, daemon=True).start()

                elif self.state == "SONG_SELECT":
                    if   event.key == pygame.K_UP:   self.selected_song_idx = max(0, self.selected_song_idx - 1)
                    elif event.key == pygame.K_DOWN:
                        if self.server_songs:
                            self.selected_song_idx = min(len(self.server_songs) - 1, self.selected_song_idx + 1)
                    elif event.key == pygame.K_RETURN and not self.ignore_keys:
                        if self.server_songs:
                            sel_song = self.server_songs[self.selected_song_idx]
                            song_id  = sel_song['id']
                            self.state = "FETCHING_MANIFEST"
                            def fetch_manifest():
                                try:
                                    import requests
                                    r = requests.get(f"{self.net.server_url}/api/songs/{song_id}", timeout=3)
                                    manifest = r.json()
                                    self.available_bms = [f for f in manifest.get('files', []) if f.lower().endswith(('.bms', '.bme', '.bml'))]
                                    if not self.available_bms:
                                        self.available_bms = ["demo.bms"]
                                    self.selected_bms_idx = 0
                                    self.state = "DIFFICULTY_SELECT"
                                except Exception as e:
                                    print("Failed to fetch manifest", e)
                                    self.state = "SONG_SELECT"
                            threading.Thread(target=fetch_manifest, daemon=True).start()

                elif self.state == "DIFFICULTY_SELECT":
                    if   event.key == pygame.K_UP:   self.selected_bms_idx = max(0, self.selected_bms_idx - 1)
                    elif event.key == pygame.K_DOWN:
                        if self.available_bms:
                            self.selected_bms_idx = min(len(self.available_bms) - 1, self.selected_bms_idx + 1)
                    elif event.key == pygame.K_RETURN and not self.ignore_keys:
                        if self.available_bms:
                            self.state = "MATCH_SETTINGS"

                elif self.state == "MATCH_SETTINGS":
                    if   event.key == pygame.K_UP:   self.ms_idx = max(0, self.ms_idx - 1)
                    elif event.key == pygame.K_DOWN: self.ms_idx = min(2, self.ms_idx + 1)
                    elif event.key == pygame.K_LEFT:
                        if   self.ms_idx == 0: self.ms_mod    = max(0, self.ms_mod    - 1)
                        elif self.ms_idx == 1: self.ms_buff   = max(0, self.ms_buff   - 1)
                        elif self.ms_idx == 2: self.ms_debuff = max(0, self.ms_debuff - 1)
                    elif event.key == pygame.K_RIGHT:
                        if   self.ms_idx == 0: self.ms_mod    = min(len(self.mod_opts)    - 1, self.ms_mod    + 1)
                        elif self.ms_idx == 1: self.ms_buff   = min(len(self.buff_opts)   - 1, self.ms_buff   + 1)
                        elif self.ms_idx == 2: self.ms_debuff = min(len(self.debuff_opts) - 1, self.ms_debuff + 1)
                    elif event.key == pygame.K_RETURN and not self.ignore_keys:
                        sel_bms  = self.available_bms[self.selected_bms_idx]
                        sel_song = self.server_songs[self.selected_song_idx]
                        ms_dict  = {
                            "speed":     round(self.ms_speed, 1),
                            "modifiers": [self.mod_opts[self.ms_mod]]    if self.ms_mod    > 0 else [],
                            "buffs":     [self.buff_opts[self.ms_buff]]  if self.ms_buff   > 0 else [],
                            "debuffs":   [self.debuff_opts[self.ms_debuff]] if self.ms_debuff > 0 else [],
                        }
                        self.net.select_song(sel_song['id'], sel_bms, match_settings=ms_dict)
                        self.state = "DOWNLOADING"
                        threading.Thread(target=self._download_task, args=(sel_song['id'], sel_bms), daemon=True).start()

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self):
        self.screen.blit(self._bg, (0, 0))

        # ── Title ──
        draw_glow_text(self.screen, _t("menu_online_multi"), self.title_font,
                       C_GLOW_CYAN, C_GLOW_CYAN,
                       (self.w // 2, self._s(30)), anchor="center", glow_radius=4)

        # Accent line under title
        lw = self._s(220)
        lx = (self.w - lw) // 2
        ly = self._s(86)
        for x in range(lw):
            t = 1.0 - abs(x - lw / 2) / (lw / 2 + 1)
            self.screen.set_at((lx + x, ly), (*C_GLOW_CYAN, int(55 * t)))

        # State-specific content
        if self.state in ("INPUT_ADDRESS", "INPUT_PASSWORD"):
            self._draw_input()
        elif self.state == "CONNECTING":
            self._draw_connecting()
        elif self.state == "LOBBY":
            self._draw_lobby()
        elif self.state in ("SONG_SELECT", "FETCHING_MANIFEST"):
            self._draw_song_select()
        elif self.state == "DIFFICULTY_SELECT":
            self._draw_difficulty_select()
        elif self.state == "MATCH_SETTINGS":
            self._draw_match_settings()
        elif self.state in ("DOWNLOADING", "WAITING_START"):
            self._draw_downloading()

    def _center_panel(self, w_frac=0.55, h_frac=0.6, y_off=0):
        pw = self._s(int(800 * w_frac))
        ph = self._s(int(600 * h_frac))
        px = (self.w - pw) // 2
        py = (self.h - ph) // 2 + self._s(y_off)
        return pygame.Rect(px, py, pw, ph)

    def _draw_input(self):
        panel = self._center_panel(0.55, 0.5, 30)
        draw_glass_panel(self.screen, panel, border_color=(*C_GLOW_CYAN, 80), radius=14, fill_alpha=10)

        cx  = panel.x + self._s(20)
        y   = panel.y + self._s(20)
        bw  = panel.width - self._s(40)
        bh  = self._s(46)

        lbl = self.body_font.render(_t("mp_enter_server"), True, C_TEXT_SECONDARY)
        self.screen.blit(lbl, lbl.get_rect(centerx=panel.centerx, top=y))
        y += lbl.get_height() + self._s(22)

        # Address field
        is_pw_state = (self.state == "INPUT_PASSWORD")
        for fi, (field_lbl, field_val, is_active) in enumerate([
            ("Address",  self.address_input,  (self.input_focus == 0) and not is_pw_state),
            ("Password", "*" * len(self.password_input), (self.input_focus == 1) or is_pw_state),
        ]):
            if is_pw_state and fi == 0:
                continue  # only show password field when in password-only state

            accent  = C_GLOW_CYAN if is_active else C_BORDER_DIM
            box_r   = pygame.Rect(cx, y, bw, bh)
            bg      = pygame.Surface((bw, bh), pygame.SRCALPHA)
            pygame.draw.rect(bg, (*C_GLOW_CYAN, 8) if is_active else (255, 255, 255, 6),
                             (0, 0, bw, bh), border_radius=8)
            self.screen.blit(bg, (cx, y))
            pygame.draw.rect(self.screen, accent, box_r, 1, border_radius=8)

            lbl_s = self.small_font.render(field_lbl + ":", True, C_TEXT_DIM)
            self.screen.blit(lbl_s, (cx + self._s(8), y - lbl_s.get_height() - self._s(2)))

            cursor = "_" if is_active else ""
            val_s  = self.body_font.render(field_val + cursor, True, C_TEXT_PRIMARY)
            self.screen.blit(val_s, (cx + self._s(12), y + (bh - val_s.get_height()) // 2))
            y += bh + self._s(28)

        hint = self.small_font.render("Tab / Arrows to switch fields   Enter to connect", True, C_TEXT_DIM)
        self.screen.blit(hint, hint.get_rect(centerx=panel.centerx, top=y + self._s(4)))

        draw_hint_bar(self.screen, "Tab  Switch Field    ENTER  Connect    ESC  Back",
                      self.small_font, self.h, self.w)

    def _draw_connecting(self):
        t_now = pygame.time.get_ticks() / 500.0
        dots  = "." * (int(t_now) % 4)
        msg   = self.font.render(_t("mp_connecting").format(dots=dots), True, C_TEXT_PRIMARY)
        self.screen.blit(msg, msg.get_rect(center=(self.w // 2, self.h // 2)))

    def _draw_lobby(self):
        panel = self._center_panel(0.6, 0.55, 20)
        draw_glass_panel(self.screen, panel, border_color=(*C_GLOW_CYAN, 80), radius=14, fill_alpha=10)

        players = self.net.lobby_state.get('players', [])
        y = panel.y + self._s(22)

        lbl = self.small_font.render("LOBBY", True, C_TEXT_DIM)
        self.screen.blit(lbl, (panel.x + self._s(20), y))
        y += lbl.get_height() + self._s(12)

        for p in players:
            is_host = (p['id'] == self.net.host_id)
            is_me   = (p['id'] == self.net.player_id)
            role_txt = f"[{_t('mp_host')}]" if is_host else f"[{_t('mp_guest')}]"
            me_txt   = f"  ({_t('mp_you')})" if is_me else ""

            row_r = pygame.Rect(panel.x + self._s(10), y, panel.width - self._s(20), self._s(44))
            if is_me:
                bg = pygame.Surface(row_r.size, pygame.SRCALPHA)
                pygame.draw.rect(bg, (*C_GLOW_CYAN, 14), (0, 0, *row_r.size), border_radius=8)
                self.screen.blit(bg, row_r.topleft)
                pygame.draw.rect(self.screen, (*C_GLOW_CYAN, 120), row_r, 1, border_radius=8)

            color = C_GLOW_CYAN if is_me else C_TEXT_PRIMARY
            role_col = C_HOST_GOLD if is_host else C_TEXT_SECONDARY
            role_s  = self.small_font.render(role_txt, True, role_col)
            name_s  = self.body_font.render(f"Player {p['id']}{me_txt}", True, color)
            self.screen.blit(name_s,  (row_r.x + self._s(14), row_r.centery - name_s.get_height() // 2))
            self.screen.blit(role_s,  (row_r.right - role_s.get_width() - self._s(14),
                                       row_r.centery - role_s.get_height() // 2))
            y += self._s(50)

        y += self._s(16)
        if len(players) < 2:
            msg = self.body_font.render(_t("mp_waiting_opponent"), True, C_TEXT_SECONDARY)
            self.screen.blit(msg, msg.get_rect(centerx=panel.centerx, top=y))
        else:
            if self.net.player_id == self.net.host_id:
                msg = self.body_font.render(_t("mp_press_enter_song"), True, C_GLOW_CYAN)
            else:
                msg = self.body_font.render(_t("mp_waiting_host"), True, C_TEXT_SECONDARY)
            self.screen.blit(msg, msg.get_rect(centerx=panel.centerx, top=y))

        draw_hint_bar(self.screen, "ENTER  Select Song (Host)    ESC  Disconnect",
                      self.small_font, self.h, self.w)

    def _draw_song_select(self):
        panel = self._center_panel(0.7, 0.65, 15)
        draw_glass_panel(self.screen, panel, border_color=(*C_GLOW_CYAN, 80), radius=14, fill_alpha=10)

        hdr = self.small_font.render("SELECT SONG", True, C_TEXT_DIM)
        self.screen.blit(hdr, (panel.x + self._s(20), panel.y + self._s(14)))

        if self.state == "FETCHING_MANIFEST" or not self.server_songs:
            msg = self.body_font.render(_t("mp_fetching_songs"), True, C_TEXT_SECONDARY)
            self.screen.blit(msg, msg.get_rect(center=panel.center))
            return

        row_h   = self._s(44)
        visible = max(1, (panel.height - self._s(50)) // row_h)
        start_y = panel.y + self._s(44)

        for i, song in enumerate(self.server_songs):
            if i < self.scroll_offset or i >= self.scroll_offset + visible:
                continue
            row = i - self.scroll_offset
            is_sel = (i == self.selected_song_idx)
            rect   = pygame.Rect(panel.x + self._s(10),
                                 start_y + row * row_h,
                                 panel.width - self._s(20),
                                 row_h - self._s(4))

            if is_sel:
                bg = pygame.Surface(rect.size, pygame.SRCALPHA)
                pygame.draw.rect(bg, (*C_GLOW_CYAN, 18), (0, 0, *rect.size), border_radius=8)
                self.screen.blit(bg, rect.topleft)
                draw_outer_glow(self.screen, rect, C_GLOW_CYAN, radius=8, passes=3, max_alpha=28)
                pygame.draw.rect(self.screen, (*C_GLOW_CYAN, 180), rect, 1, border_radius=8)

            txt = f"{song.get('title', 'Unknown')} — {song.get('artist', '?')}  (Lv.{song.get('level', '?')})"
            color = C_GLOW_CYAN if is_sel else C_TEXT_PRIMARY
            s = self.body_font.render(txt, True, color)
            self.screen.blit(s, (rect.x + self._s(12), rect.centery - s.get_height() // 2))

        draw_hint_bar(self.screen, "↑ ↓  Navigate    ENTER  Select    ESC  Back",
                      self.small_font, self.h, self.w)

    def _draw_difficulty_select(self):
        panel = self._center_panel(0.6, 0.55, 15)
        draw_glass_panel(self.screen, panel, border_color=(*C_GLOW_PURPLE, 80), radius=14, fill_alpha=10)

        hdr = self.small_font.render("SELECT DIFFICULTY", True, C_TEXT_DIM)
        self.screen.blit(hdr, (panel.x + self._s(20), panel.y + self._s(14)))

        row_h   = self._s(44)
        start_y = panel.y + self._s(44)

        for i, bms in enumerate(self.available_bms):
            is_sel = (i == self.selected_bms_idx)
            rect   = pygame.Rect(panel.x + self._s(10),
                                 start_y + i * row_h,
                                 panel.width - self._s(20),
                                 row_h - self._s(4))

            if is_sel:
                bg = pygame.Surface(rect.size, pygame.SRCALPHA)
                pygame.draw.rect(bg, (*C_GLOW_PURPLE, 18), (0, 0, *rect.size), border_radius=8)
                self.screen.blit(bg, rect.topleft)
                pygame.draw.rect(self.screen, (*C_GLOW_PURPLE, 180), rect, 1, border_radius=8)

            color = (200, 120, 255) if is_sel else C_TEXT_PRIMARY
            s = self.body_font.render(bms, True, color)
            self.screen.blit(s, (rect.x + self._s(12), rect.centery - s.get_height() // 2))

        draw_hint_bar(self.screen, "↑ ↓  Navigate    ENTER  Select    ESC  Back",
                      self.small_font, self.h, self.w)

    def _draw_match_settings(self):
        panel = self._center_panel(0.65, 0.55, 15)
        draw_glass_panel(self.screen, panel, border_color=(*C_GLOW_PURPLE, 80), radius=14, fill_alpha=10)

        hdr = self.small_font.render("MATCH SETTINGS", True, C_TEXT_DIM)
        self.screen.blit(hdr, (panel.x + self._s(20), panel.y + self._s(14)))

        settings_layout = [
            (_t("ms_modifier") if _t("ms_modifier") != "ms_modifier" else "Modifier",
             self.mod_opts[self.ms_mod]),
            (_t("ms_buff")     if _t("ms_buff")     != "ms_buff"     else "Buff",
             self.buff_opts[self.ms_buff]),
            (_t("ms_debuff")   if _t("ms_debuff")   != "ms_debuff"   else "Debuff",
             self.debuff_opts[self.ms_debuff]),
        ]

        row_h   = self._s(56)
        start_y = panel.y + self._s(50)
        for i, (lbl, val) in enumerate(settings_layout):
            is_sel = (i == self.ms_idx)
            rect   = pygame.Rect(panel.x + self._s(10),
                                 start_y + i * row_h,
                                 panel.width - self._s(20),
                                 row_h - self._s(6))

            if is_sel:
                bg = pygame.Surface(rect.size, pygame.SRCALPHA)
                pygame.draw.rect(bg, (*C_GLOW_CYAN, 18), (0, 0, *rect.size), border_radius=8)
                self.screen.blit(bg, rect.topleft)
                pygame.draw.rect(self.screen, (*C_GLOW_CYAN, 180), rect, 1, border_radius=8)

            lbl_col = C_GLOW_CYAN if is_sel else C_TEXT_SECONDARY
            val_col = C_TEXT_PRIMARY if is_sel else C_TEXT_DIM
            val_txt = f"◀  {val}  ▶" if is_sel else val

            lbl_s = self.body_font.render(lbl, True, lbl_col)
            val_s = self.body_font.render(val_txt, True, val_col)
            self.screen.blit(lbl_s, (rect.x + self._s(14), rect.centery - lbl_s.get_height() // 2))
            self.screen.blit(val_s, (rect.right - val_s.get_width() - self._s(14),
                                     rect.centery - val_s.get_height() // 2))

        draw_hint_bar(self.screen, "↑ ↓  Select    ← →  Change    ENTER  Start Match    ESC  Back",
                      self.small_font, self.h, self.w)

    def _draw_downloading(self):
        panel = self._center_panel(0.55, 0.38, 20)
        draw_glass_panel(self.screen, panel, border_color=(*C_GLOW_CYAN, 80), radius=14, fill_alpha=10)

        if self.state == "DOWNLOADING":
            hdr = self.body_font.render(_t("mp_downloading"), True, C_TEXT_PRIMARY)
            self.screen.blit(hdr, hdr.get_rect(centerx=panel.centerx, top=panel.y + self._s(22)))

            bar_w = panel.width - self._s(60)
            bar_h = self._s(8)
            bx    = panel.x + self._s(30)
            by    = panel.centery

            # Track
            trk = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
            trk.fill((60, 55, 70, 120))
            self.screen.blit(trk, (bx, by))
            pygame.draw.rect(self.screen, (*C_BORDER_DIM[:3], 40),
                             pygame.Rect(bx, by, bar_w, bar_h), 1, border_radius=4)
            # Fill
            if self.download_total > 0:
                pct    = self.download_progress / float(self.download_total)
                fill_w = max(bar_h, int(bar_w * pct))
                pygame.draw.rect(self.screen, C_GLOW_CYAN,
                                 pygame.Rect(bx, by, fill_w, bar_h), border_radius=4)

            prog_s = self.small_font.render(
                _t("mp_download_prog").format(cur=self.download_progress, tot=self.download_total),
                True, C_TEXT_SECONDARY)
            self.screen.blit(prog_s, prog_s.get_rect(centerx=panel.centerx,
                                                      top=by + bar_h + self._s(10)))
        else:  # WAITING_START
            msg = self.body_font.render(_t("mp_ready_waiting"), True, C_GLOW_CYAN)
            self.screen.blit(msg, msg.get_rect(centerx=panel.centerx, top=panel.y + self._s(28)))

            if self.net.game_start_time:
                rem = max(0, self.net.game_start_time - time.time())
                rem_s = self.body_font.render(
                    _t("mp_starting_in").format(rem=f"{rem:.1f}"), True, C_TEXT_PRIMARY)
                self.screen.blit(rem_s, rem_s.get_rect(centerx=panel.centerx,
                                                        top=panel.y + self._s(72)))
