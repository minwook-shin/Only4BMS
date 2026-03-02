import os
import json
import time
import pygame
import copy
import math
import numpy as np
from only4bms.i18n import get as _t

from .constants import *
from .assets import AssetLoader
from .engine import GameEngine
from .renderer import GameRenderer

class RhythmGame:
    def __init__(self, notes_orig, bgms, bgas, wav_map, bmp_map, title, settings, visual_timing_map=None, measures=None, mode='single', metadata=None, renderer=None, window=None, ai_difficulty='normal', note_mod='None',
                 course_hp=None, course_hp_max=100.0, course_modifier=None, challenge_manager=None):
        self.mode = mode
        self.ai_difficulty = ai_difficulty
        self.renderer = renderer
        self.window = window
        self.width, self.height = window.size
        self.notes_orig = notes_orig
        self.bgms = bgms
        self.bgas = bgas or []
        self.visual_timing_map = visual_timing_map or []
        self.measures = measures or []
        self.wav_map = wav_map
        self.title = title
        self.settings = settings
        self.metadata = metadata or {}
        self.challenge_manager = challenge_manager
        self.newly_completed = []
        self._challenge_checked = False
        # ── Course mode HP overlay ────────────────────────────────────────
        self.course_hp      = course_hp        # None means non-course mode
        self.course_hp_max  = course_hp_max
        self.course_modifier = course_modifier  # list of modifier tuples or None
        # Challenge Tracking Flags
        self.course_failed   = False
        self.ai_paused       = False
        self.ai_restarted    = False
        self.speed_changed   = False
        self.first_note_miss = False
        self.has_hit_first_note = False
        self.start_speed     = self.settings.get('speed', 1.0)
        self.lanes_compressed = self.metadata.get('lanes_compressed', False)
        self.used_dfjk       = self.settings.get('keybinds', ['d', 'f', 'j', 'k']) == ['d', 'f', 'j', 'k']
        
        # Deepcopy notes so modifications like Mirror/Random don't persist across restarts
        notes = copy.deepcopy(notes_orig)
        
        # Load Assets
        self.assets = AssetLoader(renderer, window, title, self.metadata, settings)
        self.assets.load(wav_map, bmp_map)
        
        # Engine Config
        self.hw_mult = self.settings.get('hit_window_mult', 1.0)
        self.speed = self.settings.get('speed', 1.0) * (self.height / BASE_H)
        self.lane_w = int(LANE_W * (self.width / BASE_W))
        self.lane_total_w = NUM_LANES * self.lane_w
        
        # Cache frequently accessed settings
        self.note_type = self.settings.get('note_type', 0)
        self.ai_note_type = self.settings.get('ai_note_type', 0)
        
        # Lane grouping
        if self.mode == 'single':
            start_x = (self.width - self.lane_total_w) // 2
            self.lane_x = [start_x + i * self.lane_w for i in range(NUM_LANES)]
        else: # ai_multi
            p1_start_x = self.width // 4 - self.lane_total_w // 2
            self.p1_lane_x = [p1_start_x + i * self.lane_w for i in range(NUM_LANES)]
            p2_start_x = (self.width * 3) // 4 - self.lane_total_w // 2
            self.p2_lane_x = [p2_start_x + i * self.lane_w for i in range(NUM_LANES)]
            self.lane_x = self.p1_lane_x # Default to p1 for rendering logic if shared

        # Engines
        last_note_time = max((n.get('end_time_ms', n['time_ms']) for n in notes), default=0)
        
        # Initial max_time check (trigger times)
        max_bgm_trigger = max((b['time_ms'] for b in bgms), default=0)
        max_bga_trigger = max((b['time_ms'] for b in bgas), default=0)
        max_time = max(last_note_time, max_bgm_trigger, max_bga_trigger)
        
        # Refine max_time using actual sound durations
        for bgm in bgms:
            sid = bgm['sample_id']
            if sid in self.assets.sounds and self.assets.sounds[sid]:
                end_t = bgm['time_ms'] + self.assets.sounds[sid].get_length() * 1000.0
                max_time = max(max_time, end_t)
        
        for note in notes:
            for sid in note['sample_ids']:
                if sid in self.assets.sounds and self.assets.sounds[sid]:
                    end_t = note['time_ms'] + self.assets.sounds[sid].get_length() * 1000.0
                    max_time = max(max_time, end_t)
        
        # Apply Note Mods (Mirror/Random)
        self.used_mod = False
        if note_mod != 'None':
            self.used_mod = True
            self._apply_note_mod(notes, note_mod)
        self.note_mod = note_mod

        self.engine = GameEngine(notes, bgms, bgas, self.hw_mult, self._play_sound, self.set_judgment, max_time, visual_timing_map, last_note_time, self.on_ln_tick)
        self.has_ln = any(n.get('is_ln', False) for n in notes)
        
        if self.mode == 'ai_multi':
            from ..ai.inference import RhythmInference
            self.ai_model = RhythmInference(self.ai_difficulty)
            self.ai_notes = [n.copy() for n in notes] # Lighter than deepcopy, enough for note modification
            self.ai_engine = GameEngine(self.ai_notes, [], [], self.hw_mult, lambda s: None, self.set_ai_judgment, max_time, visual_timing_map, last_note_time, self.on_ai_ln_tick)
            self.ai_lane_pressed = [False] * NUM_LANES
        
        # Calculate total judgments (LN counts twice: hit + release)
        self.total_judgments = sum(2 if n.get('is_ln') else 1 for n in notes)

        # Presentation
        self.game_renderer = GameRenderer(renderer, (self.width, self.height), self.settings)
        self.keys = self.settings.get('keys', [pygame.K_d, pygame.K_f, pygame.K_j, pygame.K_k])
        self.joy_keys = self.settings.get('joystick_keys', [0, 1, 2, 3])
        self.clock = pygame.time.Clock()
        
        # State Tracking
        self.start_time = 0
        self.state = "PLAYING" # PLAYING, PAUSED, COUNTDOWN, RESULT
        self.paused_at = 0
        self.countdown_start = 0
        self.frame_count = 0
        self._last_logic_time = 0
        
        self.judgments = {k: 0 for k in JUDGMENT_ORDER}
        self.combo = 0
        self.max_combo = 0
        self.judgment_text = ""
        self.judgment_key = ""
        self.judgment_timer = 0
        self.combo_timer = 0
        self.judgment_color = (255, 255, 255)
        self.judgment_err = 0 # ms error
        self.judgment_err_timer = 0
        self.jitter_history = [] # Last 50 timing errors
        self.hit_history = [] # List of (time_ms, err_ms, key)
        
        
        self.lane_pressed = [False] * NUM_LANES
        self.effects = []
        self.needs_restart = False

        if self.mode == 'ai_multi':
            self.ai_judgments = {k: 0 for k in JUDGMENT_ORDER}
            self.ai_combo = 0
            self.ai_max_combo = 0
            self.ai_judgment_text = ""
            self.ai_judgment_key = ""
            self.ai_judgment_timer = 0
            self.ai_combo_timer = 0
            self.ai_judgment_color = (255, 255, 255)
            self.ai_hit_history = [] # List of (time_ms, err_ms, key)
            self.ai_update_timer = 0.0
            self.ai_dt = 1.0 / 120.0 # 120Hz AI update frequency
            
        self._draw_state_cache = {'p1': {}, 'ai': {}}

    def _play_sound(self, sid):
        if sid in self.assets.sounds and self.assets.sounds[sid]:
            self.assets.sounds[sid].play()

    def set_judgment(self, key, lane=None, t=None, timing_diff=0):
        if not self.has_hit_first_note:
            self.has_hit_first_note = True
            if key == "MISS":
                self.first_note_miss = True
                
        if t is None: t = (time.perf_counter() - self.start_time) * 1000.0
        j = JUDGMENT_DEFS[key]
        _JUDGMENT_I18N = {"PERFECT": "judgment_perfect", "GREAT": "judgment_great", "GOOD": "judgment_good", "MISS": "judgment_miss"}
        self.judgment_text = _t(_JUDGMENT_I18N.get(key, key))
        self.judgment_key = key
        self.judgment_color = j["color"]
        self.judgment_timer = t
        self.judgment_err = timing_diff
        self.judgment_err_timer = t
        if key != "MISS":
            self.jitter_history.append((timing_diff, t))
            if len(self.jitter_history) > 50: self.jitter_history.pop(0)
            self.hit_history.append((t, timing_diff, key))
        else:
            self.hit_history.append((t, 0, "MISS"))
            
        self.judgments[key] += 1
        self._update_course_hp(key)

        if key in ("PERFECT", "GREAT"):
            self.combo += 1
            self.max_combo = max(self.max_combo, self.combo)
            self.combo_timer = t
        elif key == "MISS":
            self.combo = 0
        if lane is not None:
            self.effects.append({
                'lane': lane, 'radius': 30, 'color': j["color"], 'alpha': 255,
                'note_type': self.note_type
            })

    def set_ai_judgment(self, key, lane, t=None, timing_diff=0):
        if t is None: t = (time.perf_counter() - self.start_time) * 1000.0
        j = JUDGMENT_DEFS[key]
        _JUDGMENT_I18N = {"PERFECT": "judgment_perfect", "GREAT": "judgment_great", "GOOD": "judgment_good", "MISS": "judgment_miss"}
        self.ai_judgment_text = _t(_JUDGMENT_I18N.get(key, key))
        self.ai_judgment_key = key
        self.ai_judgment_color = j["color"]
        self.ai_judgment_timer = t
        self.ai_judgment_err = timing_diff
        self.ai_judgment_err_timer = t
        if not hasattr(self, 'ai_hit_history'): self.ai_hit_history = []
        if key != "MISS":
            self.ai_hit_history.append((t, timing_diff, key))
            # AI Hit Effect
            self.effects.append({
                'lane': lane + NUM_LANES,  # AI lanes are offset by NUM_LANES
                'radius': 22,
                'color': j["color"],
                'alpha': 160,
                'note_type': self.ai_note_type
            })
        else:
            self.ai_hit_history.append((t, 0, "MISS"))

        self.ai_judgments[key] += 1
        if key == "MISS": self.ai_combo = 0
        else:
            self.ai_combo += 1
            self.ai_max_combo = max(self.ai_max_combo, self.ai_combo)
            self.ai_combo_timer = t
    
    def on_ln_tick(self, t=None):
        if t is None: t = (time.perf_counter() - self.start_time) * 1000.0
        self.combo += 1
        self.max_combo = max(self.max_combo, self.combo)
        self.combo_timer = t
        # Override displayed judgment with the held LN's own judgment
        best = "PERFECT"
        for ln in self.engine.held_lns:
            if ln:
                best = ln.get('start_judgment', 'PERFECT')
                break
        _JUDGMENT_I18N = {"PERFECT": "judgment_perfect", "GREAT": "judgment_great", "GOOD": "judgment_good", "MISS": "judgment_miss"}
        self.judgment_text = _t(_JUDGMENT_I18N.get(best, best))
        self.judgment_key = best
        self.judgment_color = JUDGMENT_DEFS[best]["color"]
        self.judgment_timer = t

    def on_ai_ln_tick(self, t=None):
        if t is None: t = (time.perf_counter() - self.start_time) * 1000.0
        self.ai_combo += 1
        self.ai_max_combo = max(self.ai_max_combo, self.ai_combo)
        self.ai_combo_timer = t
        self.ai_judgment_timer = t

    def handle_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE or event.key == pygame.K_TAB:
                if self.mode == 'ai_multi':
                    self.ai_paused = True
                self._pause()
                return
            if event.key == pygame.K_r: # Quick Retry
                if self.mode == 'ai_multi':
                    self.ai_restarted = True
                    # Check challenges immediately if restarted during ai_multi
                    if self.challenge_manager and not self._challenge_checked:
                        self.challenge_manager.check_challenges(self.get_stats())
                        self._challenge_checked = True
                self.needs_restart = True
                return
            if event.key == pygame.K_F1: # Increase Speed
                self.speed_changed = True
                self.speed = min(5.0 * (self.height / BASE_H), self.speed + 0.1 * (self.height / BASE_H))
                self.settings['speed'] = self.speed / (self.height / BASE_H)
                return
            if event.key == pygame.K_F2: # Decrease Speed
                self.speed_changed = True
                self.speed = max(0.1 * (self.height / BASE_H), self.speed - 0.1 * (self.height / BASE_H))
                self.settings['speed'] = self.speed / (self.height / BASE_H)
                return
                
            for i, k in enumerate(self.keys):
                if event.key == k:
                    self.lane_pressed[i] = True
                    # Use high precision timing directly
                    t_now = time.perf_counter()
                    delay_ms = self.settings.get('judge_delay', 30.0)
                    t_ms = (t_now - self.start_time) * 1000.0 - delay_ms
                    self.engine.process_hit(i, t_ms)
        elif event.type == pygame.KEYUP:
            for i, k in enumerate(self.keys):
                if event.key == k:
                    self.lane_pressed[i] = False
                    t_ms = (time.perf_counter() - self.start_time) * 1000.0
                    self.engine.process_release(i, t_ms)
        elif event.type == pygame.JOYBUTTONDOWN:
            for i, mapping in enumerate(self.joy_keys):
                if isinstance(mapping, str) and mapping.startswith("BTN_"):
                    btn_idx = int(mapping.split("_")[1])
                    if event.button == btn_idx:
                        self.lane_pressed[i] = True
                        t_ms = (time.perf_counter() - self.start_time) * 1000.0 - self.settings.get('judge_delay', 30.0)
                        self.engine.process_hit(i, t_ms)
                elif event.button == mapping: # Fallback for old integer settings
                    self.lane_pressed[i] = True
                    t_ms = (time.perf_counter() - self.start_time) * 1000.0 - self.settings.get('judge_delay', 30.0)
                    self.engine.process_hit(i, t_ms)
        elif event.type == pygame.JOYBUTTONUP:
            for i, mapping in enumerate(self.joy_keys):
                if isinstance(mapping, str) and mapping.startswith("BTN_"):
                    btn_idx = int(mapping.split("_")[1])
                    if event.button == btn_idx:
                        self.lane_pressed[i] = False
                        t_ms = (time.perf_counter() - self.start_time) * 1000.0
                        self.engine.process_release(i, t_ms)
                elif event.button == mapping:
                    self.lane_pressed[i] = False
                    t_ms = (time.perf_counter() - self.start_time) * 1000.0
                    self.engine.process_release(i, t_ms)
        elif event.type == pygame.JOYHATMOTION:
            for i, mapping in enumerate(self.joy_keys):
                if isinstance(mapping, str) and mapping.startswith("HAT_"):
                    parts = mapping.split("_")
                    hat_idx = int(parts[1])
                    dir_str = parts[2]
                    if event.hat == hat_idx:
                        vx, vy = event.value
                        is_active = False
                        if dir_str == "UP" and vy == 1: is_active = True
                        elif dir_str == "DOWN" and vy == -1: is_active = True
                        elif dir_str == "LEFT" and vx == -1: is_active = True
                        elif dir_str == "RIGHT" and vx == 1: is_active = True
                        
                        if is_active and not self.lane_pressed[i]:
                            self.lane_pressed[i] = True
                            t_ms = (time.perf_counter() - self.start_time) * 1000.0 - self.settings.get('judge_delay', 30.0)
                            self.engine.process_hit(i, t_ms)
                        elif not is_active and self.lane_pressed[i]:
                            self.lane_pressed[i] = False
                            t_ms = (time.perf_counter() - self.start_time) * 1000.0
                            self.engine.process_release(i, t_ms)

    def _pause(self):
        self.paused_at = time.perf_counter()
        self.state = "PAUSED"
        pygame.mouse.set_visible(True)
        pygame.mixer.pause()

    def _resume(self):
        self.countdown_start = time.perf_counter()
        self.state = "COUNTDOWN"
        pygame.mouse.set_visible(False)
        
    def _get_rank(self, score_ratio):
        if score_ratio >= 1.0: return "P"
        if score_ratio >= 0.95: return "AAA"
        if score_ratio >= 0.85: return "AA"
        if score_ratio >= 0.75: return "A"
        if score_ratio >= 0.65: return "B"
        if score_ratio >= 0.55: return "C"
        if score_ratio >= 0.45: return "D"
        return "E"

    def run(self):
        self.start_time = time.perf_counter()
        self.is_running = True
        pygame.mouse.set_visible(False)
        
        # High Polling Rate & Logic Sub-stepping Initialization
        polling_rate = self.settings.get('input_polling_rate', 1000)
        dt_logic = 1.0 / polling_rate
        accumulator = 0.0
        last_frame_time = time.perf_counter()
        simulated_real_time = self.start_time
        
        # Render rate control
        target_fps = self.settings.get('fps', 144)
        dt_render = 1.0 / target_fps
        last_render_time = time.perf_counter()

        while self.is_running:
            if self.needs_restart:
                pygame.mouse.set_visible(True)
                pygame.mixer.stop()
                return {"action": "RESTART"}
            
            t_now = time.perf_counter()
            elapsed = t_now - last_frame_time
            last_frame_time = t_now
            accumulator += elapsed
            
            # 1. High-Precision Logic Loop (Sub-stepping)
            # This loop simulates time in fixed dt_logic steps regardless of frame rate
            while accumulator >= dt_logic:
                # 1a. Poll Input Events (Happens every sub-step for peak precision)
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.is_running = False
                    elif event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                        from ..main import refresh_joysticks
                        refresh_joysticks()
                    elif self.state == "PLAYING":
                        self.handle_input(event)
                    elif self.state == "PAUSED":
                        self._handle_pause_input(event)
                    elif self.state == "RESULT":
                        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                            self.is_running = False
                        elif event.type == pygame.JOYBUTTONDOWN and event.button in (0, 1):
                            self.is_running = False
                
                # 1b. Update Game Game Logic (Simulated sub-step time)
                if self.state == "PLAYING":
                    # We use the midpoint of the sub-step for logic to balance jitter
                    sim_time_ms = (simulated_real_time - self.start_time) * 1000.0
                    
                    sim_time_ms = (simulated_real_time - self.start_time) * 1000.0
                    
                    if self.engine.update(sim_time_ms, self.lane_pressed):
                        self.state = "RESULT"
                        pygame.mouse.set_visible(True)
                simulated_real_time += dt_logic
                accumulator -= dt_logic
                # Safety break to prevent "Spiral of Death"
                if time.perf_counter() - t_now > 0.05:
                    accumulator = 0 # Drop frames if we can't keep up
                    break 
            
            # 1c. Separate AI Update (Throttled to 120Hz)
            if self.mode == 'ai_multi' and self.state == "PLAYING":
                if t_now - self.ai_update_timer >= self.ai_dt:
                    sim_time_ms = (t_now - self.start_time) * 1000.0
                    self._update_ai(sim_time_ms)
                    self.ai_update_timer = t_now
            
            # 2. Render Loop (Capped)
            t_render_check = time.perf_counter()
            if t_render_check - last_render_time >= dt_render: 
                now_ms = (t_render_check - self.start_time) * 1000.0
                vis_offset = self.settings.get('visual_offset', 0.0)
                
                if self.state == "PLAYING":
                    # Continuous LN Effects
                    self.frame_count += 1
                    if self.frame_count % 4 == 0:
                        for lane, note in enumerate(self.engine.held_lns):
                            if note:
                                self.effects.append({
                                    'lane': lane, 'radius': 22, 'color': (0, 255, 255), 'alpha': 160,
                                    'note_type': self.note_type
                                })
                        # AI LN effects at half frequency (every 8 frames)
                        if self.mode == 'ai_multi' and self.frame_count % 8 == 0:
                            for lane, note in enumerate(self.ai_engine.held_lns):
                                if note:
                                    self.effects.append({
                                        'lane': lane + NUM_LANES, 'radius': 22, 'color': (0, 255, 255), 'alpha': 160,
                                        'note_type': self.ai_note_type
                                    })
                    # Pass offset time to draw for visual adjustment
                    self._draw(now_ms + vis_offset)
                elif self.state == "PAUSED":
                    self._draw_paused()
                elif self.state == "COUNTDOWN":
                    self._draw_countdown()
                elif self.state == "RESULT":
                    # Check for newly achieved challenges when the game ends (Result screen)
                    if self.challenge_manager and not self._challenge_checked:
                        self.newly_completed = self.challenge_manager.check_challenges(self.get_stats())
                        self._challenge_checked = True
                    self._draw_result(now_ms + vis_offset)

                self.renderer.present()
                last_render_time = time.perf_counter()
        
        pygame.mouse.set_visible(True)
        if getattr(self, 'restart_flag', False):
            return {"action": "RESTART"}
        if getattr(self, 'quit_flag', False):
            return {"action": "QUIT"}
        
        if self.state == "RESULT":
            stats = self.get_stats()
            stats["action"] = "CLEAR"
            return stats
        return {"action": "QUIT"}

    def get_stats(self):
        max_ex = max(1, self.total_judgments * 2)
        p1_ex = self.judgments["PERFECT"] * 2 + self.judgments["GREAT"] * 1
        accuracy = (p1_ex / max_ex) * 100.0
        
        ai_p1_ex = getattr(self, 'ai_judgments', {}).get("PERFECT", 0) * 2 + getattr(self, 'ai_judgments', {}).get("GREAT", 0)
        ai_acc = (ai_p1_ex / max_ex) * 100.0 if self.mode == 'ai_multi' else 0.0
        
        return {
            'mode': self.mode,
            'title': self.title,
            'level': self.metadata.get('level', self.metadata.get('playlevel', '0')),
            'judgments': self.judgments,
            'max_combo': self.max_combo,
            'accuracy': accuracy,
            'ai_accuracy': ai_acc,
            'total_score': p1_ex,
            'total_notes': len(self.engine.notes),
            'failed': self.course_failed,
            'ai_paused': self.ai_paused,
            'ai_restarted': self.ai_restarted,
            'speed_changed': self.speed_changed,
            'first_note_miss': self.first_note_miss,
            'lanes_compressed': self.lanes_compressed,
            'used_dfjk': self.used_dfjk,
            'used_mod': getattr(self, 'used_mod', False),
            'note_mod': getattr(self, 'note_mod', 'None'),
            'has_ln': getattr(self, 'has_ln', False),
            'ai_diff': self.ai_difficulty,
            'must_win': (self.mode == 'ai_multi' and p1_ex > ai_p1_ex),
            'ai_judgments': getattr(self, 'ai_judgments', None),
            'ai_max_combo': getattr(self, 'ai_max_combo', 0),
            'newly_completed': self.newly_completed
        }

    def _update_ai(self, current_time):
        miss_window = JUDGMENT_DEFS["MISS"]["threshold_ms"] * self.hw_mult
        self.ai_engine.update(current_time)
        
        # AI Perception
        ai_jitter = 30.0 if self.ai_difficulty == 'normal' else 2.0
        ai_actions = [0] * NUM_LANES
        
        for lane in range(NUM_LANES):
            obs = self.ai_engine.get_observation(current_time, lane, jitter=ai_jitter, is_pressed=self.ai_lane_pressed[lane])
            act = self.ai_model.predict(obs, deterministic=True)
            ai_actions[lane] = int(act) if np.isscalar(act) else int(act.item())
        
        for lane in range(NUM_LANES):
            pressed = bool(ai_actions[lane])
            if pressed: self.ai_engine.process_hit(lane, current_time)
            self.ai_lane_pressed[lane] = pressed
        
        self.ai_engine.update(current_time, self.ai_lane_pressed)

    def _draw(self, t):
        self.renderer.draw_color = (0, 0, 0, 255)
        self.renderer.clear()
        self.game_renderer.draw_bga(t, self.engine.current_bga_img, self.assets, is_course=(self.course_hp is not None))
        
        # Player 1 View
        p1_state = self._get_draw_state('p1', t)
        self.game_renderer.draw_playing(t, p1_state)
        
        # Effects Rendering (Handles both P1 and AI effects)
        all_lanes = self.lane_x
        if self.mode == 'ai_multi':
            all_lanes = self.p1_lane_x + self.p2_lane_x
        self.game_renderer.draw_effects(self.effects, all_lanes, self.lane_w)

        # Performance Gauges (EX Ratio)
        fade_mult = 1.0
        passed_time = p1_state.get('all_notes_passed_time')
        if passed_time is not None:
            elapsed = t - passed_time
            fade_mult = max(0.0, 1.0 - elapsed / 500.0)

        max_ex = max(1, self.total_judgments * 2)
        p1_ex = self.judgments["PERFECT"] * 2 + self.judgments["GREAT"] * 1
        p1_ratio = min(1.0, p1_ex / max_ex)
        gw, gh = self.game_renderer._sx(12), self.game_renderer._s(400) # Thicker (8 -> 12)
        gy = self.game_renderer.hit_y - gh
        ga = int(255 * fade_mult)

        if self.mode == 'single':
            gx = self.lane_x[0] - gw - self.game_renderer._sx(10)
            self.game_renderer.draw_vertical_gauge(gx, gy, gw, gh, p1_ratio, (0, 255, 255), ga)
        else: # ai_multi
            # Player Gauge (Right of Player lanes, Center)
            gx_p1 = self.p1_lane_x[-1] + self.lane_w + self.game_renderer._sx(5)
            self.game_renderer.draw_vertical_gauge(gx_p1, gy, gw, gh, p1_ratio, (0, 255, 255), ga)
            
            # AI View
            ai_state = self._get_draw_state('ai', t)
            self.game_renderer.draw_playing(t, ai_state)
            self.game_renderer.draw_score_bar(self.judgments, self.ai_judgments)

            # AI Gauge (Left of AI lanes, Center)
            ai_ex = self.ai_judgments["PERFECT"] * 2 + self.ai_judgments["GREAT"] * 1
            ai_ratio = min(1.0, ai_ex / max_ex)
            gx_ai = self.p2_lane_x[0] - gw - self.game_renderer._sx(5)
            self.game_renderer.draw_vertical_gauge(gx_ai, gy, gw, gh, ai_ratio, (255, 80, 80), ga)

    def _get_draw_state(self, side, t):
        d = self._draw_state_cache[side]
        if side == 'p1':
            d['lane_x'] = self.p1_lane_x if self.mode == 'ai_multi' else self.lane_x
            d['notes'] = self.engine.notes
            d['note_idx'] = self.engine.note_idx
            d['lane_pressed'] = self.lane_pressed
            d['judgments'] = self.judgments
            d['combo'] = self.combo
            d['judgment_text'] = self.judgment_text
            d['judgment_key'] = self.judgment_key
            d['judgment_color'] = self.judgment_color
            d['judgment_timer'] = self.judgment_timer
            d['judgment_err'] = self.judgment_err
            d['judgment_err_timer'] = self.judgment_err_timer
            d['jitter_history'] = self.jitter_history
            d['combo_timer'] = self.combo_timer
            d['lane_total_w'] = self.lane_total_w
            d['speed'] = self.speed
            d['hw_mult'] = self.hw_mult
            d['held_lns'] = self.engine.held_lns
            d['current_visual_time'] = self.engine.get_visual_time(t)
            d['all_notes_passed'] = self.engine.all_notes_passed
            d['all_notes_passed_time'] = self.engine.all_notes_passed_time
            d['note_type'] = self.note_type
            d['is_ai'] = False
            d['measures'] = self.measures
            d['course_hp']       = self.course_hp
            d['course_hp_max']   = self.course_hp_max
            d['course_modifier'] = self.course_modifier
            if self.mode == 'ai_multi':
                d['ai_judgments'] = self.ai_judgments
                d['ai_hit_history'] = self.ai_hit_history
        else:  # side == 'ai'
            d['lane_x'] = self.p2_lane_x
            d['notes'] = self.ai_notes
            d['note_idx'] = self.ai_engine.note_idx
            d['lane_pressed'] = self.ai_lane_pressed
            d['judgments'] = self.ai_judgments
            d['combo'] = self.ai_combo
            d['judgment_text'] = self.ai_judgment_text
            d['judgment_key'] = getattr(self, 'ai_judgment_key', '')
            d['judgment_color'] = self.ai_judgment_color
            d['judgment_timer'] = self.ai_judgment_timer
            d['judgment_err'] = getattr(self, 'ai_judgment_err', 0)
            d['judgment_err_timer'] = getattr(self, 'ai_judgment_err_timer', 0)
            d['combo_timer'] = self.ai_combo_timer
            d['lane_total_w'] = self.lane_total_w
            d['speed'] = self.speed
            d['hw_mult'] = self.hw_mult
            d['held_lns'] = self.ai_engine.held_lns
            d['current_visual_time'] = self.ai_engine.get_visual_time(t)
            d['all_notes_passed'] = self.ai_engine.all_notes_passed
            d['all_notes_passed_time'] = self.ai_engine.all_notes_passed_time
            d['note_type'] = self.ai_note_type
            d['is_ai'] = True
            d['measures'] = self.measures
        return d

    def _draw_paused(self):
        self._draw((self.paused_at - self.start_time) * 1000.0) # Draw frozen background
        self.renderer.draw_color = (0, 0, 0, 150)
        self.renderer.fill_rect((0, 0, self.width, self.height))
        
        s = self.game_renderer._s
        tex1 = self.game_renderer._get_text_texture(_t("paused"), True, (255, 255, 255), size_override=s(56))
        self.renderer.blit(tex1, pygame.Rect(self.width // 2 - tex1.width // 2, self.height // 2 - s(80), tex1.width, tex1.height))
        
        tex2 = self.game_renderer._get_text_texture(_t("resume_hint"), False, (200, 255, 200), size_override=s(24))
        self.renderer.blit(tex2, pygame.Rect(self.width // 2 - tex2.width // 2, self.height // 2 - s(10), tex2.width, tex2.height))
        
        tex3 = self.game_renderer._get_text_texture(_t("quit_hint"), False, (255, 200, 200), size_override=s(24))
        self.renderer.blit(tex3, pygame.Rect(self.width // 2 - tex3.width // 2, self.height // 2 + s(25), tex3.width, tex3.height))

    def _handle_pause_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_TAB):
                self._resume()
            elif event.key in (pygame.K_q, pygame.K_RETURN, pygame.K_BACKSPACE):
                self.is_running = False
                self.quit_flag = True
        elif event.type == pygame.JOYBUTTONDOWN:
            if event.button == 0: # A
                self.is_running = False
                self.quit_flag = True
            elif event.button == 1: # B
                self._resume()

    def _draw_countdown(self):
        elapsed = time.perf_counter() - self.countdown_start
        rem = 3 - elapsed
        if rem <= 0:
            self.start_time += (time.perf_counter() - self.paused_at)
            self.state = "PLAYING"
            pygame.mouse.set_visible(False)
            pygame.mixer.unpause()
            return
        
        self._draw((self.paused_at - self.start_time) * 1000.0)
        val = int(math.ceil(rem))
        tex = self.game_renderer._get_text_texture(str(val), True, (255, 255, 0), size_override=self.game_renderer._s(120))
        self.renderer.blit(tex, pygame.Rect(self.width // 2 - tex.width // 2, self.height // 2 - tex.height // 2, tex.width, tex.height))

    def _draw_result(self, t):
        self.game_renderer.draw_bga(t, self.engine.current_bga_img, self.assets)
        stats = {
            'mode': self.mode, 'title': self.title, 'metadata': self.metadata,
            'judgments': self.judgments, 'max_combo': self.max_combo,
            'hit_history': self.hit_history, 'ai_hit_history': getattr(self, 'ai_hit_history', []),
            'ai_judgments': getattr(self, 'ai_judgments', None), 'ai_max_combo': getattr(self, 'ai_max_combo', 0),
            'max_time': self.engine.max_time,
            'total_notes': len(self.engine.notes),
            'cover_texture': self.assets.cover_texture,
            'failed': self.course_failed,
            'newly_completed': self.newly_completed
        }
        self.game_renderer.draw_result(stats, t)

    def _apply_note_mod(self, notes, mod):
        if mod == 'Mirror':
            for n in notes:
                n['lane'] = (NUM_LANES - 1) - n['lane']
        elif mod == 'Random':
            # Create a mapping for each note to shuffle lanes
            # Actually, standardリ듬게임 Random usually shuffles the ENTIRE LANE mapping once
            mapping = list(range(NUM_LANES))
            import random
            random.shuffle(mapping)
            for n in notes:
                n['lane'] = mapping[n['lane']]

    def _update_course_hp(self, key):
        if self.course_hp is None: return

        # Constants (Matching course_session.py)
        MISS_DRAIN    = 8.0
        GOOD_DRAIN    = 2.0
        GREAT_REGEN   = 0.5
        PERFECT_REGEN = 1.0

        drain_val = 0.0
        regen_val = 0.0

        if key == "PERFECT": regen_val = PERFECT_REGEN
        elif key == "GREAT": regen_val = GREAT_REGEN
        elif key == "GOOD":  drain_val = GOOD_DRAIN
        elif key == "MISS":  drain_val = MISS_DRAIN

        # Modifier adjustments
        if self.course_modifier:
            for modifier in self.course_modifier:
                mod_key = modifier[0]
                if mod_key == "mod_hp_boost":
                    regen_val *= 1.5
                elif mod_key == "mod_hp_regen":
                    regen_val *= 2.0
                elif mod_key == "mod_hp_fragile":
                    drain_val *= 2.0
                elif mod_key == "mod_hp_drain":
                    drain_val *= 1.5
                    regen_val *= 0.5
                elif mod_key == "mod_perfectionist":
                    if key != "PERFECT":
                        if key == "GREAT": drain_val += 1.5
                        elif key == "GOOD": drain_val += 2.0
                        elif key == "MISS": drain_val += 1.0

        self.course_hp += (regen_val - drain_val)
        self.course_hp = max(0.0, min(self.course_hp_max, self.course_hp))

        if self.course_hp <= 0 and not self.course_failed:
            self.course_failed = True
            self.state = "RESULT"
            pygame.mouse.set_visible(True)
            pygame.mixer.stop()
