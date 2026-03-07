import pygame
import threading
import os
import time
from only4bms.i18n import get as _t
from only4bms import i18n as _i18n
from only4bms import paths
from only4bms.core.network_manager import NetworkManager

BASE_W, BASE_H = 800, 600
COLOR_ACCENT = (0, 255, 200)
COLOR_TEXT_PRIMARY = (255, 255, 255)
COLOR_TEXT_SECONDARY = (180, 180, 200)
COLOR_PANEL_BG = (15, 15, 25, 230)
COLOR_SELECTED_BG = (40, 50, 80, 225)
COLOR_HOVERED_BG = (35, 35, 60, 160)

class MultiplayerMenu:
    def __init__(self, settings, renderer, window):
        from pygame._sdl2.video import Texture
        self.settings = settings
        self.renderer = renderer
        self.window = window

        self.w, self.h = self.window.size
        self.sx, self.sy = self.w / BASE_W, self.h / BASE_H

        self.screen = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.texture = None

        self.clock = pygame.time.Clock()
        self.title_font = _i18n.font("menu_title", self.sy, bold=True)
        self.font = _i18n.font("menu_option", self.sy)
        self.small_font = _i18n.font("menu_small", self.sy)

        self.net = NetworkManager()
        if self.net.is_connected:
            self.state = "LOBBY"
            self.net.game_start_time = None
        else:
            self.state = "INPUT_ADDRESS"
        
        self.running = True
        self.action = "QUIT"
        self.selected_song_path = None
        
        self.address_input = self.settings.get("last_server_ip", "127.0.0.1:5000")
        self.password_input = ""
        
        self.server_songs = []
        self.available_bms = []
        self.selected_song_idx = 0
        self.selected_bms_idx = 0
        self.scroll_offset = 0
        
        self.download_progress = 0
        self.download_total = 0
        
        # UI Focus States
        self.input_focus = 0 # 0: Address, 1: Password
        
        # Match Settings Form States
        self.ms_idx = 0
        self.ms_speed = self.settings.get('speed', 1.0)
        self.ms_mod = 0 # 0: None, 1: Random, 2: Mirror
        self.ms_buff = 0 # 0: None, 1: HP_BOOST, 2: HP_REGEN, 3: WINDOW_WIDE, 4: SPEED_SLOW
        self.ms_debuff = 0 # 0: None, 1: HP_FRAGILE, 2: WINDOW_TIGHT, 3: SPEED_FAST, 4: HP_DRAIN
        
        self.mod_opts = ["None", "Random", "Mirror"]
        self.buff_opts = ["None", "HP_BOOST", "HP_REGEN", "WINDOW_WIDE", "SPEED_SLOW"]
        self.debuff_opts = ["None", "HP_FRAGILE", "WINDOW_TIGHT", "SPEED_FAST", "HP_DRAIN"]
        
        # Debounce
        self.ignore_keys = pygame.key.get_pressed()[pygame.K_RETURN]

    def _s(self, v): return max(1, int(v * self.sy))

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

    def _update_network_state(self):
        if self.net.join_error:
            self.state = "INPUT_PASSWORD"
            self.net.join_error = None
            
        elif self.state == "LOBBY":
            if not self.net.is_connected:
                self.state = "INPUT_ADDRESS"
            
            # Check if host selected a song
            sel_song_id = self.net.lobby_state.get('selected_song_id')
            sel_bms = self.net.lobby_state.get('selected_bms_file')
            if sel_song_id and sel_bms and self.net.player_id != self.net.host_id:
                # Guest transitioning to download because host chose a song
                self.state = "DOWNLOADING"
                threading.Thread(target=self._download_task, args=(sel_song_id, sel_bms), daemon=True).start()
                
        elif self.state == "WAITING_START":
            if self.net.game_start_time and time.time() >= self.net.game_start_time:
                self.action = "START_MULTI"
                self.running = False
                
    def _download_task(self, song_id, target_bms=None):
        self.download_progress = 0
        self.download_total = 1 # Fake initial to avoid div by zero
        
        cache_dir = os.path.join(paths.SONG_DIR, ".multiplayer_cache")
        
        def progress_cb(cur, tot):
            self.download_progress = cur
            self.download_total = tot
            
        success = self.net.download_song(song_id, cache_dir, progress_cb)
        
        if success:
            if target_bms:
                self.selected_song_path = os.path.join(cache_dir, song_id, target_bms)
            else:
                self.selected_song_path = os.path.join(cache_dir, song_id, "demo.bms") # We need to find the specific .bms file inside
                
                # Search for actual bms file
                song_dir = os.path.join(cache_dir, song_id)
                for f in os.listdir(song_dir):
                    if f.lower().endswith(('.bms', '.bme', '.bml')):
                        self.selected_song_path = os.path.join(song_dir, f)
                        break
            
            self.state = "WAITING_START"
            self.net.send_ready()
        else:
            print("Download failed")
            self.state = "LOBBY" # fallback

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYUP:
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.ignore_keys = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == "MATCH_SETTINGS":
                        self.state = "DIFFICULTY_SELECT"
                    elif self.state == "DIFFICULTY_SELECT":
                        self.state = "SONG_SELECT"
                    elif self.state == "SONG_SELECT":
                        self.state = "LOBBY"
                    elif self.state == "INPUT_PASSWORD":
                        self.state = "INPUT_ADDRESS"
                    else:
                        self.net.disconnect()
                        self.action = "MENU"
                        self.running = False
                    continue
                    
                if self.state == "INPUT_ADDRESS":
                    if event.key == pygame.K_TAB or event.key == pygame.K_DOWN or event.key == pygame.K_UP:
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
                                # We wait for LOBBY or INPUT_PASSWORD state change driven by events
                                # so we just sleep briefly then fallback if not connected
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
                    if event.key == pygame.K_UP:
                        self.selected_song_idx = max(0, self.selected_song_idx - 1)
                    elif event.key == pygame.K_DOWN:
                        if self.server_songs:
                            self.selected_song_idx = min(len(self.server_songs) - 1, self.selected_song_idx + 1)
                    elif event.key == pygame.K_RETURN and not self.ignore_keys:
                        if self.server_songs:
                            sel_song = self.server_songs[self.selected_song_idx]
                            song_id = sel_song['id']
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
                    if event.key == pygame.K_UP:
                        self.selected_bms_idx = max(0, self.selected_bms_idx - 1)
                    elif event.key == pygame.K_DOWN:
                        if self.available_bms:
                            self.selected_bms_idx = min(len(self.available_bms) - 1, self.selected_bms_idx + 1)
                    elif event.key == pygame.K_RETURN and not self.ignore_keys:
                        if self.available_bms:
                            self.state = "MATCH_SETTINGS"
                
                elif self.state == "MATCH_SETTINGS":
                    if event.key == pygame.K_UP:
                        self.ms_idx = max(0, self.ms_idx - 1)
                    elif event.key == pygame.K_DOWN:
                        self.ms_idx = min(2, self.ms_idx + 1) # Max is now 2 (Mod, Buff, Debuff)
                    elif event.key == pygame.K_LEFT:
                        if   self.ms_idx == 0: self.ms_mod = max(0, self.ms_mod - 1)
                        elif self.ms_idx == 1: self.ms_buff = max(0, self.ms_buff - 1)
                        elif self.ms_idx == 2: self.ms_debuff = max(0, self.ms_debuff - 1)
                    elif event.key == pygame.K_RIGHT:
                        if   self.ms_idx == 0: self.ms_mod = min(len(self.mod_opts)-1, self.ms_mod + 1)
                        elif self.ms_idx == 1: self.ms_buff = min(len(self.buff_opts)-1, self.ms_buff + 1)
                        elif self.ms_idx == 2: self.ms_debuff = min(len(self.debuff_opts)-1, self.ms_debuff + 1)
                    
                    elif event.key == pygame.K_RETURN and not self.ignore_keys:
                        sel_bms = self.available_bms[self.selected_bms_idx]
                        sel_song = self.server_songs[self.selected_song_idx]
                        
                        ms_dict = {
                            "speed": round(self.ms_speed, 1),
                            "modifiers": [self.mod_opts[self.ms_mod]] if self.ms_mod > 0 else [],
                            "buffs": [self.buff_opts[self.ms_buff]] if self.ms_buff > 0 else [],
                            "debuffs": [self.debuff_opts[self.ms_debuff]] if self.ms_debuff > 0 else []
                        }
                        
                        self.net.select_song(sel_song['id'], sel_bms, match_settings=ms_dict)
                        self.state = "DOWNLOADING"
                        threading.Thread(target=self._download_task, args=(sel_song['id'], sel_bms), daemon=True).start()

    def _draw(self):
        self.screen.fill((20, 20, 30, 255))
        
        # Title
        title_surf = self.title_font.render(_t("menu_online_multi"), True, COLOR_ACCENT)
        self.screen.blit(title_surf, ((self.w - title_surf.get_width()) // 2, self._s(40)))

        if self.state == "INPUT_ADDRESS":
            msg = self.font.render(_t("mp_enter_server"), True, COLOR_TEXT_PRIMARY)
            self.screen.blit(msg, ((self.w - msg.get_width()) // 2, self.h // 2 - self._s(100)))
            
            # IP Input Box
            box_w, box_h = self._s(400), self._s(50)
            box_rect_ip = pygame.Rect((self.w - box_w) // 2, self.h // 2 - self._s(40), box_w, box_h)
            pygame.draw.rect(self.screen, COLOR_PANEL_BG, box_rect_ip)
            pygame.draw.rect(self.screen, COLOR_ACCENT if self.input_focus == 0 else COLOR_TEXT_SECONDARY, box_rect_ip, 2)
            
            ip_lbl = self.small_font.render("Address:", True, COLOR_TEXT_SECONDARY)
            self.screen.blit(ip_lbl, (box_rect_ip.x - ip_lbl.get_width() - 10, box_rect_ip.y + 15))
            
            text_surf_ip = self.font.render(self.address_input + ("_" if self.input_focus == 0 else ""), True, COLOR_TEXT_PRIMARY)
            self.screen.blit(text_surf_ip, (box_rect_ip.x + self._s(10), box_rect_ip.y + self._s(10)))
            
            # Password Input Box
            box_rect_pw = pygame.Rect((self.w - box_w) // 2, self.h // 2 + self._s(20), box_w, box_h)
            pygame.draw.rect(self.screen, COLOR_PANEL_BG, box_rect_pw)
            pygame.draw.rect(self.screen, COLOR_ACCENT if self.input_focus == 1 else COLOR_TEXT_SECONDARY, box_rect_pw, 2)
            
            pw_lbl = self.small_font.render("Password:", True, COLOR_TEXT_SECONDARY)
            self.screen.blit(pw_lbl, (box_rect_pw.x - pw_lbl.get_width() - 10, box_rect_pw.y + 15))
            
            hidden_pw = "*" * len(self.password_input)
            text_surf_pw = self.font.render(hidden_pw + ("_" if self.input_focus == 1 else ""), True, COLOR_TEXT_PRIMARY)
            self.screen.blit(text_surf_pw, (box_rect_pw.x + self._s(10), box_rect_pw.y + self._s(10)))
            
            hint = self.small_font.render("Use Tab/Arrows to switch. Press Enter to connect.", True, COLOR_TEXT_SECONDARY)
            self.screen.blit(hint, ((self.w - hint.get_width()) // 2, box_rect_pw.bottom + self._s(20)))

        elif self.state == "CONNECTING":
            t = pygame.time.get_ticks() / 500.0
            dots = "." * (int(t) % 4)
            msg = self.font.render(_t("mp_connecting").format(dots=dots), True, COLOR_TEXT_PRIMARY)
            self.screen.blit(msg, ((self.w - msg.get_width()) // 2, self.h // 2))

        elif self.state == "LOBBY":
            # Show players
            players = self.net.lobby_state.get('players', [])
            
            py = self._s(150)
            for p in players:
                is_host = (p['id'] == self.net.host_id)
                role = f"[{_t('mp_host')}]" if is_host else f"[{_t('mp_guest')}]"
                is_me = (p['id'] == self.net.player_id)
                me_tag = f"({_t('mp_you')})" if is_me else ""
                
                color = COLOR_ACCENT if is_me else COLOR_TEXT_PRIMARY
                p_text = f"{_t('mp_player')} {p['id']} {role} {me_tag}"
                surf = self.font.render(p_text, True, color)
                self.screen.blit(surf, ((self.w - surf.get_width()) // 2, py))
                py += self._s(50)
                
            if len(players) < 2:
                msg = self.font.render(_t("mp_waiting_opponent"), True, COLOR_TEXT_SECONDARY)
                self.screen.blit(msg, ((self.w - msg.get_width()) // 2, py + self._s(50)))
            else:
                if self.net.player_id == self.net.host_id:
                    msg = self.font.render(_t("mp_press_enter_song"), True, COLOR_ACCENT)
                    self.screen.blit(msg, ((self.w - msg.get_width()) // 2, self.h - self._s(100)))
                else:
                    msg = self.font.render(_t("mp_waiting_host"), True, COLOR_TEXT_SECONDARY)
                    self.screen.blit(msg, ((self.w - msg.get_width()) // 2, self.h - self._s(100)))

        elif self.state == "SONG_SELECT":
            if not self.server_songs:
                msg = self.font.render(_t("mp_fetching_songs"), True, COLOR_TEXT_SECONDARY)
                self.screen.blit(msg, ((self.w - msg.get_width()) // 2, self.h // 2))
            else:
                start_y = self._s(150)
                for i, song in enumerate(self.server_songs):
                    color = COLOR_ACCENT if i == self.selected_song_idx else COLOR_TEXT_PRIMARY
                    txt = f"{song.get('title', 'Unknown')} - {song.get('artist', 'Unknown')} (LV.{song.get('level', '?')})"
                    surf = self.font.render(txt, True, color)
                    self.screen.blit(surf, (self._s(100), start_y + i * self._s(40)))
                    
                msg = self.small_font.render(_t("mp_choose_hint"), True, COLOR_TEXT_SECONDARY)
                self.screen.blit(msg, ((self.w - msg.get_width()) // 2, self.h - self._s(50)))

        elif self.state == "FETCHING_MANIFEST":
            msg = self.font.render(_t("mp_checking_diff"), True, COLOR_TEXT_SECONDARY)
            self.screen.blit(msg, ((self.w - msg.get_width()) // 2, self.h // 2))

        elif self.state == "DIFFICULTY_SELECT":
            start_y = self._s(150)
            msg = self.font.render(_t("mp_select_diff"), True, COLOR_TEXT_PRIMARY)
            self.screen.blit(msg, ((self.w - msg.get_width()) // 2, start_y - self._s(60)))
            
            for i, bms in enumerate(self.available_bms):
                color = COLOR_ACCENT if i == self.selected_bms_idx else COLOR_TEXT_PRIMARY
                surf = self.font.render(bms, True, color)
                self.screen.blit(surf, (self._s(100), start_y + i * self._s(40)))
                
            hint = self.small_font.render(_t("mp_diff_hint"), True, COLOR_TEXT_SECONDARY)
            self.screen.blit(hint, ((self.w - hint.get_width()) // 2, self.h - self._s(50)))

        elif self.state == "MATCH_SETTINGS":
            msg = self.font.render("Match Settings", True, COLOR_ACCENT)
            self.screen.blit(msg, ((self.w - msg.get_width()) // 2, self._s(80)))
            
            settings_layout = [
                ("Modifier", self.mod_opts[self.ms_mod]),
                ("Buff", self.buff_opts[self.ms_buff]),
                ("Debuff", self.debuff_opts[self.ms_debuff])
            ]
            
            py = self._s(180)
            item_h = self._s(60)
            for i, (lbl, val) in enumerate(settings_layout):
                color = COLOR_ACCENT if i == self.ms_idx else COLOR_TEXT_PRIMARY
                lbl_surf = self.font.render(lbl, True, color)
                val_surf = self.font.render(f"< {val} >" if i == self.ms_idx else val, True, color)
                
                self.screen.blit(lbl_surf, (self.w // 2 - self._s(200), py))
                self.screen.blit(val_surf, (self.w // 2 + self._s(50), py))
                py += item_h
                
            hint = self.small_font.render("Arrows to change. Enter to start the match.", True, COLOR_TEXT_SECONDARY)
            self.screen.blit(hint, ((self.w - hint.get_width()) // 2, py + self._s(20)))

        elif self.state == "DOWNLOADING":
            msg = self.font.render(_t("mp_downloading"), True, COLOR_TEXT_PRIMARY)
            self.screen.blit(msg, ((self.w - msg.get_width()) // 2, self.h // 2 - self._s(50)))
            
            # Progress bar
            bar_w, bar_h = self._s(400), self._s(20)
            bx = (self.w - bar_w) // 2
            by = self.h // 2 + self._s(10)
            pygame.draw.rect(self.screen, COLOR_PANEL_BG, (bx, by, bar_w, bar_h))
            
            if self.download_total > 0:
                pct = self.download_progress / float(self.download_total)
                pygame.draw.rect(self.screen, COLOR_ACCENT, (bx, by, int(bar_w * pct), bar_h))
                
            p_text = self.small_font.render(_t("mp_download_prog").format(cur=self.download_progress, tot=self.download_total), True, COLOR_TEXT_SECONDARY)
            self.screen.blit(p_text, ((self.w - p_text.get_width()) // 2, by + self._s(30)))

        elif self.state == "WAITING_START":
            msg = self.font.render(_t("mp_ready_waiting"), True, COLOR_ACCENT)
            self.screen.blit(msg, ((self.w - msg.get_width()) // 2, self.h // 2))
            if self.net.game_start_time:
                rem = max(0, self.net.game_start_time - time.time())
                rem_txt = self.font.render(_t("mp_starting_in").format(rem=f"{rem:.1f}"), True, COLOR_TEXT_PRIMARY)
                self.screen.blit(rem_txt, ((self.w - rem_txt.get_width()) // 2, self.h // 2 + self._s(40)))
