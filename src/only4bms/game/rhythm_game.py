import os
import json
import time
import pygame
import copy
import math
import numpy as np
from pygame._sdl2.video import Texture
from .constants import *
from .assets import AssetLoader
from .engine import GameEngine
from .renderer import GameRenderer

class RhythmGame:
    def __init__(self, notes_orig, bgms, bgas, wav_map, bmp_map, title, settings, visual_timing_map=None, mode='single', metadata=None, renderer=None, window=None, ai_difficulty='normal', note_mod='None'):
        self.mode = mode
        self.ai_difficulty = ai_difficulty
        self.renderer = renderer
        self.window = window
        self.width, self.height = window.size
        self.title = title
        self.settings = settings
        self.metadata = metadata or {}
        
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
        if note_mod != 'None':
            self._apply_note_mod(notes, note_mod)

        self.engine = GameEngine(notes, bgms, bgas, self.hw_mult, self._play_sound, self.set_judgment, max_time, visual_timing_map, last_note_time, self.on_ln_tick)
        
        if self.mode == 'ai_multi':
            from ..ai.inference import RhythmInference
            self.ai_model = RhythmInference(self.ai_difficulty)
            self.ai_notes = copy.deepcopy(notes) # AI gets the same modified notes
            self.ai_engine = GameEngine(self.ai_notes, [], [], self.hw_mult, lambda s: None, self.set_ai_judgment, max_time, visual_timing_map, last_note_time, self.on_ai_ln_tick)
            self.ai_lane_pressed = [False] * NUM_LANES

        # Presentation
        self.game_renderer = GameRenderer(renderer, (self.width, self.height), self.settings)
        self.keys = [pygame.K_d, pygame.K_f, pygame.K_j, pygame.K_k]
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
            self.ai_effects = []
            self.ai_hit_history = [] # List of (time_ms, err_ms, key)

    def _play_sound(self, sid):
        if sid in self.assets.sounds and self.assets.sounds[sid]:
            self.assets.sounds[sid].play()

    def set_judgment(self, key, lane=None, t=None, timing_diff=0):
        if t is None: t = (time.perf_counter() - self.start_time) * 1000.0
        j = JUDGMENT_DEFS[key]
        self.judgment_text = j["display"]
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
        if key in ("PERFECT", "GREAT"):
            self.combo += 1
            self.max_combo = max(self.max_combo, self.combo)
            self.combo_timer = t
        elif key == "MISS":
            self.combo = 0
        if lane is not None:
            self.effects.append({
                'lane': lane, 'radius': 30, 'color': j["color"], 'alpha': 255,
                'note_type': self.settings.get('note_type', 0)
            })

    def set_ai_judgment(self, key, lane, t=None, timing_diff=0):
        if t is None: t = (time.perf_counter() - self.start_time) * 1000.0
        j = JUDGMENT_DEFS[key]
        self.ai_judgment_text = j["display"]
        self.ai_judgment_key = key
        self.ai_judgment_color = j["color"]
        self.ai_judgment_timer = t
        self.ai_judgment_err = timing_diff
        self.ai_judgment_err_timer = t
        if not hasattr(self, 'ai_hit_history'): self.ai_hit_history = []
        if key != "MISS":
            self.ai_hit_history.append((t, timing_diff, key))
        else:
            self.ai_hit_history.append((t, 0, "MISS"))

        self.ai_judgments[key] += 1
        if key == "MISS": self.ai_combo = 0
        else:
            self.ai_combo += 1
            self.ai_max_combo = max(self.ai_max_combo, self.ai_combo)
            self.ai_combo_timer = t
        self.ai_effects.append({
            'lane': lane, 'radius': 30, 'color': j["color"], 'alpha': 255,
            'note_type': self.settings.get('ai_note_type', 0)
        })

    def on_ln_tick(self, t=None):
        if t is None: t = (time.perf_counter() - self.start_time) * 1000.0
        self.combo += 1
        self.max_combo = max(self.max_combo, self.combo)
        self.combo_timer = t
        # Refresh judgment timer slightly to keep it "active/glowing" during LNs
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
                self._pause()
                return
            if event.key == pygame.K_r: # Quick Retry
                self.needs_restart = True
                return
            if event.key == pygame.K_F1: # Increase Speed
                self.speed = min(5.0 * (self.height / BASE_H), self.speed + 0.1 * (self.height / BASE_H))
                self.settings['speed'] = self.speed / (self.height / BASE_H)
                return
            if event.key == pygame.K_F2: # Decrease Speed
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

    def _pause(self):
        self.paused_at = time.perf_counter()
        self.state = "PAUSED"
        pygame.mouse.set_visible(True)
        pygame.mixer.pause()

    def _resume(self):
        self.countdown_start = time.perf_counter()
        self.state = "COUNTDOWN"
        
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
                pygame.mixer.stop()
                return "RESTART"
            
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
                    elif self.state == "PLAYING":
                        self.handle_input(event)
                    elif self.state == "PAUSED":
                        self._handle_pause_input(event)
                    elif self.state == "RESULT":
                        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                            self.is_running = False
                
                # 1b. Update Game Game Logic (Simulated sub-step time)
                if self.state == "PLAYING":
                    # We use the midpoint of the sub-step for logic to balance jitter
                    sim_time_ms = (simulated_real_time - self.start_time) * 1000.0
                    
                    if self.mode == 'ai_multi':
                        self._update_ai(sim_time_ms)
                    if self.engine.update(sim_time_ms):
                        self.state = "RESULT"
                
                simulated_real_time += dt_logic
                accumulator -= dt_logic
                # Safety break to prevent "Spiral of Death"
                if time.perf_counter() - t_now > 0.05:
                    accumulator = 0 # Drop frames if we can't keep up
                    break 
            
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
                                    'note_type': self.settings.get('note_type', 0)
                                })
                        if self.mode == 'ai_multi':
                            for lane, note in enumerate(self.ai_engine.held_lns):
                                if note:
                                    self.ai_effects.append({
                                        'lane': lane, 'radius': 22, 'color': (0, 255, 255), 'alpha': 160,
                                        'note_type': self.settings.get('ai_note_type', 0)
                                    })
                    # Pass offset time to draw for visual adjustment
                    self._draw(now_ms + vis_offset)
                elif self.state == "PAUSED":
                    self._draw_paused()
                elif self.state == "COUNTDOWN":
                    self._draw_countdown()
                elif self.state == "RESULT":
                    self._draw_result(now_ms + vis_offset)

                self.renderer.present()
                last_render_time = time.perf_counter()

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

    def _draw(self, t):
        self.renderer.draw_color = (0, 0, 0, 255)
        self.renderer.clear()
        self.game_renderer.draw_bga(t, self.engine.current_bga_img, self.assets)
        
        # Player 1 View
        p1_state = self._get_draw_state('p1', t)
        self.game_renderer.draw_playing(t, p1_state)
        self.game_renderer.draw_effects(self.effects, self.lane_x, self.lane_w)

        if self.mode == 'ai_multi':
            # AI View
            ai_state = self._get_draw_state('ai', t)
            self.game_renderer.draw_playing(t, ai_state)
            self.game_renderer.draw_effects(self.ai_effects, self.p2_lane_x, self.lane_w)
            self.game_renderer.draw_score_bar(self.judgments, self.ai_judgments)

    def _get_draw_state(self, side, t):
        if side == 'p1':
            p1_state = {
                'lane_x': self.lane_x, 'notes': self.engine.notes, 'note_idx': self.engine.note_idx, 'lane_pressed': self.lane_pressed,
                'judgments': self.judgments, 'combo': self.combo, 
                'judgment_text': self.judgment_text, 'judgment_key': self.judgment_key,
                'judgment_color': self.judgment_color, 'judgment_timer': self.judgment_timer,
                'judgment_err': self.judgment_err, 'judgment_err_timer': self.judgment_err_timer,
                'jitter_history': self.jitter_history,
                'hit_history': self.hit_history,
                'max_time': self.engine.max_time,
                'total_notes': len(self.engine.notes),
                'combo_timer': self.combo_timer,
                'lane_total_w': self.lane_total_w, 'speed': self.speed, 'hw_mult': self.hw_mult,
                'held_lns': self.engine.held_lns, 'current_visual_time': self.engine.get_visual_time(t),
                'all_notes_passed': self.engine.all_notes_passed,
                'all_notes_passed_time': self.engine.all_notes_passed_time,
                'note_type': self.settings.get('note_type', 0)
            }
            if self.mode == 'ai_multi':
                p1_state.update({
                    'lane_x': self.p1_lane_x,
                    'ai_judgments': self.ai_judgments,
                    'ai_hit_history': getattr(self, 'ai_hit_history', []),
                })
            return p1_state
        else: # side == 'ai'
            return {
                'lane_x': self.p2_lane_x, 'notes': self.ai_notes, 'note_idx': self.ai_engine.note_idx, 'lane_pressed': self.ai_lane_pressed,
                'judgments': self.ai_judgments, 'combo': self.ai_combo, 
                'judgment_text': self.ai_judgment_text, 'judgment_key': getattr(self, 'ai_judgment_key', ''),
                'judgment_color': self.ai_judgment_color, 'judgment_timer': self.ai_judgment_timer,
                'judgment_err': getattr(self, 'ai_judgment_err', 0), 'judgment_err_timer': getattr(self, 'ai_judgment_err_timer', 0),
                'combo_timer': self.ai_combo_timer,
                'lane_total_w': self.lane_total_w, 'speed': self.speed, 'hw_mult': self.hw_mult,
                'held_lns': self.ai_engine.held_lns, 'current_visual_time': self.ai_engine.get_visual_time(t),
                'all_notes_passed': self.ai_engine.all_notes_passed,
                'all_notes_passed_time': self.ai_engine.all_notes_passed_time,
                'note_type': self.settings.get('ai_note_type', 0),
                'is_ai': True
            }

    def _draw_paused(self):
        self._draw((self.paused_at - self.start_time) * 1000.0) # Draw frozen background
        self.renderer.draw_color = (0, 0, 0, 150)
        self.renderer.fill_rect((0, 0, self.width, self.height))
        
        font = pygame.font.SysFont(None, int(72 * (self.height / 600.0)))
        surf = font.render("PAUSED", True, (255, 255, 255))
        self.renderer.blit(Texture.from_surface(self.renderer, surf), 
                           surf.get_rect(center=(self.width // 2, self.height // 2 - 80)))
        
        small_font = pygame.font.SysFont(None, int(32 * (self.height / 600.0)))
        hint1 = small_font.render("Press ESC / TAB to Resume", True, (200, 255, 200))
        self.renderer.blit(Texture.from_surface(self.renderer, hint1), 
                           hint1.get_rect(center=(self.width // 2, self.height // 2)))
        
        hint2 = small_font.render("Press Q or ENTER to Quit", True, (255, 200, 200))
        self.renderer.blit(Texture.from_surface(self.renderer, hint2), 
                           hint2.get_rect(center=(self.width // 2, self.height // 2 + 50)))

    def _handle_pause_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_TAB):
                self._resume()
            elif event.key in (pygame.K_q, pygame.K_RETURN, pygame.K_BACKSPACE):
                self.is_running = False

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
        font = pygame.font.SysFont(None, int(120 * (self.height / 600.0)))
        surf = font.render(str(val), True, (255, 255, 0))
        self.renderer.blit(Texture.from_surface(self.renderer, surf), 
                           surf.get_rect(center=(self.width // 2, self.height // 2)))

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
            'failed': False
        }
        self.game_renderer.draw_result(stats)

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
