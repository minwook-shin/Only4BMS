import gymnasium as gym
from gymnasium import spaces
import numpy as np

# A simplified headless environment representing the 4-lane rhythm game.
class RhythmEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, parser=None, hw_mult=1.0, jitter=0.0):
        super().__init__()
        self.parser = parser
        self.hw_mult = hw_mult
        self.jitter = jitter
        
        # Determine if we're in random curriculum mode or fixed song mode
        self.fixed_notes = None
        if parser:
            # Flatten all parser notes into a single lane benchmark
            self.fixed_notes = sorted(parser.notes, key=lambda x: x['time_ms'])
        
        self.perfect_window = 40 * hw_mult
        self.great_window = 100 * hw_mult
        self.good_window = 200 * hw_mult
        self.miss_window = 200 * hw_mult
        
        self.observation_space = spaces.Box(low=-1.0, high=1.0, shape=(3,), dtype=np.float32)
        self.action_space = spaces.Discrete(2)
        
        self.current_time = 0.0
        self.step_dt = 16.0 
        self.max_time = 0.0
        self.lane_pressed = 0.0

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        
        if self.fixed_notes:
            # Deep copy to ensure 'hit'/'miss' states don't persist
            self.notes = [n.copy() for n in self.fixed_notes]
        else:
            # Use provided seed or fallback to a fixed seed for training consistency
            gen_seed = seed if seed is not None else 42
            self.notes = self._generate_random_track(seed=gen_seed)
        
        self.max_time = max((n['time_ms'] for n in self.notes), default=0.0) + 1000.0
        self.current_time = 0.0
        self.lane_pressed = 0.0
        return self._get_obs(), {}

    def _generate_random_track(self, duration_ms=60000, seed=None):
        """
        Generates a rhythmic track. If seed is provided, it uses a deterministic 
        training curriculum to ensure consistent AI behavior across runs.
        """
        notes = []
        import random
        rng = random.Random(seed)
        
        time_ms = 1000.0
        
        while time_ms < duration_ms:
            # Curriculum: 
            # 0-30% duration: Foundation (Simple 4th/8th notes)
            # 30-70% duration: Complexity (Bursts and Syncopation)
            # 70-100% duration: High-speed / Dense
            
            progress = time_ms / duration_ms
            pattern_roll = rng.random()
            
            if progress < 0.3:
                # Basic Timing Foundation
                notes.append({'time_ms': time_ms})
                time_ms += rng.randint(400, 800)
            elif progress < 0.7:
                # Diverse Patterns
                if pattern_roll < 0.4:
                    # High-speed Bursts
                    num_burst = rng.randint(3, 8)
                    burst_delay = rng.choice([80, 125, 166]) 
                    for _ in range(num_burst):
                        if time_ms >= duration_ms: break
                        notes.append({'time_ms': time_ms})
                        time_ms += burst_delay
                    time_ms += rng.randint(400, 800)
                elif pattern_roll < 0.7:
                    # Syncopated
                    num_sync = rng.randint(4, 6)
                    base_delay = rng.randint(250, 400)
                    for i in range(num_sync):
                        if time_ms >= duration_ms: break
                        notes.append({'time_ms': time_ms})
                        time_ms += base_delay * (0.5 if i % 2 == 0 else 1.5)
                    time_ms += rng.randint(400, 600)
                else:
                    notes.append({'time_ms': time_ms})
                    time_ms += rng.randint(300, 600)
            else:
                # Stress Testing / High Density
                if pattern_roll < 0.6:
                    # Continuous Stream
                    num_stream = rng.randint(10, 20)
                    delay = rng.choice([125, 166, 200])
                    for _ in range(num_stream):
                        if time_ms >= duration_ms: break
                        notes.append({'time_ms': time_ms})
                        time_ms += delay
                    time_ms += 400
                else:
                    notes.append({'time_ms': time_ms})
                    time_ms += rng.randint(150, 300)
                
        return sorted(notes, key=lambda x: x['time_ms'])

    def step(self, action):
        reward = 0.0
        action = int(action)
        
        # Process misses
        for note in self.notes:
            if 'hit' not in note and 'miss' not in note:
                if self.current_time - note['time_ms'] > self.miss_window:
                    note['miss'] = True
                    reward -= 1.0
                    
        was_pressed = self.lane_pressed
        self.lane_pressed = float(action)
        
        if action == 1 and was_pressed == 0.0:
            closest = None
            min_diff = float('inf')
            for note in self.notes:
                if 'hit' not in note and 'miss' not in note:
                    diff = abs(note['time_ms'] - self.current_time)
                    if diff <= self.good_window and diff < min_diff:
                        min_diff = diff
                        closest = note
            if closest:
                closest['hit'] = True
                if min_diff <= self.perfect_window:
                    reward += 10.0
                elif min_diff <= self.great_window:
                    reward += 3.0
                elif min_diff <= self.good_window:
                    reward += 0.5
            else:
                reward -= 1.0  # Big penalty for pressing randomly
        elif action == 1 and was_pressed == 1.0:
            reward -= 1.0  # Huge penalty for holding (forces tapping)
        else:
            reward += 0.01
            
        self.current_time += self.step_dt
        done = self.current_time >= self.max_time
        return self._get_obs(), reward, done, False, {}

    def _get_obs(self):
        obs = np.ones(3, dtype=np.float32)
        notes_in_lane = []
        for note in self.notes:
            if 'hit' not in note and 'miss' not in note:
                time_to_note = note['time_ms'] - self.current_time
                
                # Apply Human Jitter (Perception Noise)
                if self.jitter > 0:
                    noise = np.random.normal(0, self.jitter)
                    time_to_note += noise
                
                if -self.miss_window <= time_to_note <= 1000.0:
                    notes_in_lane.append(time_to_note)
        
        notes_in_lane.sort()
        if len(notes_in_lane) > 0:
            obs[0] = notes_in_lane[0] / 1000.0
        if len(notes_in_lane) > 1:
            obs[1] = notes_in_lane[1] / 1000.0
        obs[2] = self.lane_pressed
        return obs
