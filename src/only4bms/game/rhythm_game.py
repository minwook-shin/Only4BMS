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
    def __init__(self, notes, bgms, bgas, wav_map, bmp_map, title, settings, mode='single', metadata=None, renderer=None, window=None, ai_difficulty='normal'):
        self.mode = mode
        self.ai_difficulty = ai_difficulty
        self.renderer = renderer
        self.window = window
        self.width, self.height = window.size
        self.title = title
        self.settings = settings
        self.metadata = metadata or {}
        
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
        max_time = max((n['time_ms'] for n in notes), default=0)
        self.engine = GameEngine(notes, bgms, bgas, self.hw_mult, self._play_sound, self.set_judgment, max_time)
        
        if self.mode == 'ai_multi':
            from ..ai.inference import RhythmInference
            self.ai_model = RhythmInference(self.ai_difficulty)
            self.ai_notes = copy.deepcopy(notes)
            self.ai_engine = GameEngine(self.ai_notes, [], [], self.hw_mult, lambda s: None, self.set_ai_judgment, max_time)
            self.ai_lane_pressed = [False] * NUM_LANES

        # Presentation
        self.game_renderer = GameRenderer(renderer, (self.width, self.height))
        self.keys = [pygame.K_d, pygame.K_f, pygame.K_j, pygame.K_k]
        self.clock = pygame.time.Clock()
        
        # State Tracking
        self.start_time = 0
        self.state = "PLAYING" # PLAYING, PAUSED, COUNTDOWN, RESULT
        self.paused_at = 0
        self.countdown_start = 0
        
        self.judgments = {k: 0 for k in JUDGMENT_ORDER}
        self.combo = 0
        self.max_combo = 0
        self.judgment_text = ""
        self.judgment_timer = 0
        self.judgment_color = (255, 255, 255)
        self.lane_pressed = [False] * NUM_LANES
        self.effects = []

        if self.mode == 'ai_multi':
            self.ai_judgments = {k: 0 for k in JUDGMENT_ORDER}
            self.ai_combo = 0
            self.ai_max_combo = 0
            self.ai_judgment_text = ""
            self.ai_judgment_timer = 0
            self.ai_judgment_color = (255, 255, 255)
            self.ai_effects = []

    def _play_sound(self, sid):
        if sid in self.assets.sounds and self.assets.sounds[sid]:
            self.assets.sounds[sid].play()

    def set_judgment(self, key, lane=None):
        j = JUDGMENT_DEFS[key]
        self.judgment_text = j["display"]
        self.judgment_color = j["color"]
        self.judgment_timer = pygame.time.get_ticks()
        self.judgments[key] += 1
        if key in ("PERFECT", "GREAT"):
            self.combo += 1
            self.max_combo = max(self.max_combo, self.combo)
        elif key == "MISS":
            self.combo = 0
        if lane is not None:
            self.effects.append({'lane': lane, 'radius': 30, 'color': j["color"], 'alpha': 255})

    def set_ai_judgment(self, key, lane):
        j = JUDGMENT_DEFS[key]
        self.ai_judgment_text = j["display"]
        self.ai_judgment_color = j["color"]
        self.ai_judgment_timer = pygame.time.get_ticks()
        self.ai_judgments[key] += 1
        if key == "MISS": self.ai_combo = 0
        else:
            self.ai_combo += 1
            self.ai_max_combo = max(self.ai_max_combo, self.ai_combo)
        self.ai_effects.append({'lane': lane, 'radius': 30, 'color': j["color"], 'alpha': 255})

    def handle_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE or event.key == pygame.K_TAB:
                self._pause()
                return
            for i, k in enumerate(self.keys):
                if event.key == k:
                    self.lane_pressed[i] = True
                    delay = self.settings.get('judge_delay', 30.0)
                    t = (time.perf_counter() - self.start_time) * 1000.0 - delay
                    self.engine.process_hit(i, t)
        elif event.type == pygame.KEYUP:
            for i, k in enumerate(self.keys):
                if event.key == k: self.lane_pressed[i] = False

    def _pause(self):
        self.paused_at = time.perf_counter()
        self.state = "PAUSED"
        pygame.mouse.set_visible(True)
        pygame.mixer.pause()

    def _resume(self):
        self.countdown_start = time.perf_counter()
        self.state = "COUNTDOWN"

    def run(self):
        self.start_time = time.perf_counter()
        self.is_running = True
        while self.is_running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: self.is_running = False
                elif self.state == "PLAYING": self.handle_input(event)
                elif self.state == "PAUSED": self._handle_pause_input(event)
                elif self.state == "RESULT":
                    if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                        self.is_running = False
            
            if self.state == "PLAYING":
                now = (time.perf_counter() - self.start_time) * 1000.0
                if self.mode == 'ai_multi': self._update_ai(now)
                if self.engine.update(now): self.state = "RESULT"
                self._draw(now)
            elif self.state == "PAUSED": self._draw_paused()
            elif self.state == "COUNTDOWN": self._draw_countdown()
            elif self.state == "RESULT": self._draw_result()

            self.renderer.present()
            self.clock.tick(self.settings.get('fps', 144))

    def _update_ai(self, current_time):
        miss_window = JUDGMENT_DEFS["MISS"]["threshold_ms"] * self.hw_mult
        self.ai_engine.update(current_time)
        
        # AI Perception
        ai_jitter = 30.0 if self.ai_difficulty == 'normal' else 2.0
        ai_actions = [0] * NUM_LANES
        for lane in range(NUM_LANES):
            obs = np.ones(3, dtype=np.float32)
            ttns = []
            for n in self.ai_notes:
                if n['lane'] == lane and 'hit' not in n and 'miss' not in n:
                    p_ttn = (n['time_ms'] - current_time) + np.random.normal(0, ai_jitter)
                    if -miss_window <= p_ttn <= 1000.0: ttns.append(p_ttn)
            ttns.sort()
            if ttns: obs[0] = ttns[0] / 1000.0
            if len(ttns) > 1: obs[1] = ttns[1] / 1000.0
            obs[2] = float(self.ai_lane_pressed[lane])
            
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
        p1_state = self._get_draw_state('p1')
        self.game_renderer.draw_playing(t, p1_state)
        self.game_renderer.draw_effects(self.effects, self.lane_x, self.lane_w)

        if self.mode == 'ai_multi':
            # AI View
            ai_state = self._get_draw_state('ai')
            self.game_renderer.draw_playing(t, ai_state)
            self.game_renderer.draw_effects(self.ai_effects, self.p2_lane_x, self.lane_w)
            self.game_renderer.draw_score_bar(self.judgments, self.ai_judgments)

    def _get_draw_state(self, side):
        if side == 'p1':
            return {
                'lane_x': self.lane_x, 'notes': self.engine.notes, 'lane_pressed': self.lane_pressed,
                'judgments': self.judgments, 'combo': self.combo, 'judgment_text': self.judgment_text,
                'judgment_color': self.judgment_color, 'judgment_timer': self.judgment_timer,
                'lane_total_w': self.lane_total_w, 'speed': self.speed, 'hw_mult': self.hw_mult
            }
        else:
            return {
                'lane_x': self.p2_lane_x, 'notes': self.ai_notes, 'lane_pressed': self.ai_lane_pressed,
                'judgments': self.ai_judgments, 'combo': self.ai_combo, 'judgment_text': self.ai_judgment_text,
                'judgment_color': self.ai_judgment_color, 'judgment_timer': self.ai_judgment_timer,
                'lane_total_w': self.lane_total_w, 'speed': self.speed, 'hw_mult': self.hw_mult
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

    def _draw_result(self):
        stats = {
            'mode': self.mode, 'title': self.title, 'metadata': self.metadata,
            'judgments': self.judgments, 'max_combo': self.max_combo,
            'ai_judgments': getattr(self, 'ai_judgments', None), 'ai_max_combo': getattr(self, 'ai_max_combo', 0),
            'cover_texture': self.assets.cover_texture
        }
        self.game_renderer.draw_result(stats)
