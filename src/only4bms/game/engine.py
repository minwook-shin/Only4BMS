import time
import numpy as np
from .constants import JUDGMENT_DEFS, SONG_END_PADDING_MS

LN_COMBO_TICK_MS = 80

class GameEngine:
    def __init__(self, notes, bgms, bgas, hw_mult, play_sound_cb, set_judgment_cb, max_time, visual_timing_map=None, last_note_time=0, on_ln_tick_cb=None):
        self.notes = notes
        self.bgms = bgms
        self.bgas = bgas
        self.hw_mult = hw_mult
        self.play_sound_cb = play_sound_cb
        self.set_judgment_cb = set_judgment_cb
        self.on_ln_tick_cb = on_ln_tick_cb
        self.max_time = max_time
        self.last_note_time = last_note_time
        self.visual_timing_map = visual_timing_map or [(0.0, 0.0, 1.0)]
        self.current_visual_time = 0.0
        
        self.current_bga_img = None
        self.state = "PLAYING"
        self.held_lns = [None] * 4 # lane -> active LN note
        self.bgm_idx = 0
        self.bga_idx = 0
        self.note_idx = 0
        self.all_notes_passed = False
        self.all_notes_passed_time = None
        self.ln_tick_timer = 0.0
        self.last_note_time_per_lane = [-9999.0] * 4 # lane -> time of last processed note
        
        # Pre-calculate Jack (Holding Hit) adjacencies for visualization
        last_t_per_lane = [-9999.0] * 4
        last_v_t_per_lane = [-9999.0] * 4
        for note in self.notes:
            if not note.get('is_auto'):
                lane = note['lane']
                t = note['time_ms']
                v_t = note.get('visual_time_ms', t)
                if t - last_t_per_lane[lane] <= 150:
                    note['jack_prev_v_time'] = last_v_t_per_lane[lane]
                last_t_per_lane[lane] = note.get('end_time_ms', t)
                last_v_t_per_lane[lane] = note.get('visual_end_time_ms', note.get('end_time_ms', v_t))

    def process_hit(self, lane, current_time):
        max_window = JUDGMENT_DEFS["GOOD"]["threshold_ms"] * self.hw_mult
        closest, min_diff = None, float('inf')

        # Optimization: Only search from note_idx within a window
        for i in range(self.note_idx, len(self.notes)):
            note = self.notes[i]
            if note['time_ms'] - current_time > max_window: break # Too far in future
            
            if note['lane'] == lane and 'hit' not in note and 'miss' not in note and not note.get('is_auto'):
                diff = abs(note['time_ms'] - current_time)
                if diff < min_diff and diff <= max_window:
                    min_diff = diff
                    closest = note

        if closest:
            closest['hit'] = True
            for sid in closest['sample_ids']:
                self.play_sound_cb(sid)

            timing_diff = current_time - closest['time_ms'] # Positive means LATE, Negative means FAST
            for key in ("PERFECT", "GREAT", "GOOD"):
                if min_diff <= JUDGMENT_DEFS[key]["threshold_ms"] * self.hw_mult:
                    self.set_judgment_cb(key, lane, current_time, timing_diff)
                    self.last_note_time_per_lane[lane] = closest['time_ms']
                    if closest.get('is_ln'):
                        self.held_lns[lane] = closest
                        closest['start_judgment'] = key
                    return True
        return False

    def process_release(self, lane, current_time):
        """Handle key release for long notes with full judgment range."""
        note = self.held_lns[lane]
        if not note:
            return

        diff = abs(note['end_time_ms'] - current_time)
        max_window = JUDGMENT_DEFS["GOOD"]["threshold_ms"] * self.hw_mult
        
        # If released too early (outside window)
        if note['end_time_ms'] - current_time > max_window:
            note['miss'] = True
            self.set_judgment_cb("MISS", lane, current_time, 0)
        else:
            # Lenient release: ignore exact timing, use the judgment from the start hit
            judgment = note.get('start_judgment', 'PERFECT')
            timing_diff = current_time - note['end_time_ms']
            self.set_judgment_cb(judgment, lane, current_time, timing_diff)
            self.last_note_time_per_lane[lane] = note['end_time_ms']
            # Play release sounds if defined
            for sid in note.get('end_sample_ids', []):
                self.play_sound_cb(sid)
        
        self.held_lns[lane] = None
    
    def get_visual_time(self, current_real_time):
        """Calculate visual time (scroll position) from real time."""
        # Find segment in visual_timing_map where start_real <= current_real_time
        # [(start_real, start_visual, factor), ...] sorted by start_real
        best_seg = self.visual_timing_map[0]
        for seg in self.visual_timing_map:
            if seg[0] <= current_real_time:
                best_seg = seg
            else:
                break
        
        start_real, start_visual, factor = best_seg
        return start_visual + (current_real_time - start_real) * factor

    def get_observation(self, current_time, lane, jitter=0.0, is_pressed=False):
        """Constructs a 3-feature observation for the AI model."""
        miss_window = JUDGMENT_DEFS["MISS"]["threshold_ms"] * self.hw_mult
        active_notes = [
            n for n in self.notes 
            if 'hit' not in n and 'miss' not in n and (n['time_ms'] - current_time) <= 1000.0
        ]
        
        obs = np.ones(3, dtype=np.float32) # Default far away
        ttns = []
        for n in active_notes:
            if n['lane'] == lane:
                p_ttn = (n['time_ms'] - current_time)
                if jitter > 0: p_ttn += np.random.normal(0, jitter)
                if p_ttn >= -miss_window:
                    ttns.append(p_ttn)
        ttns.sort()
        if ttns: obs[0] = ttns[0] / 1000.0
        if len(ttns) > 1: obs[1] = ttns[1] / 1000.0
        obs[2] = float(is_pressed)
        return obs

    def update(self, current_time, lane_presses=None):
        if lane_presses is None: lane_presses = [False] * 4
        self.current_visual_time = self.get_visual_time(current_time)
        miss_window = JUDGMENT_DEFS["MISS"]["threshold_ms"] * self.hw_mult
        
        # Normal notes (Optimized index check)
        while self.note_idx < len(self.notes):
            note = self.notes[self.note_idx]
            
            # If note is already processed, move index
            if 'hit' in note or 'miss' in note:
                self.note_idx += 1
                continue
                
            # Check for auto-play or miss
            if note.get('is_auto'):
                if current_time >= note['time_ms']:
                    note['hit'] = True
                    for sid in note['sample_ids']:
                        self.play_sound_cb(sid)
                    self.note_idx += 1
                    # Do NOT break; check next note immediately
                else:
                    break # Future auto-note
            elif current_time - note['time_ms'] > miss_window:
                note['miss'] = True
                self.set_judgment_cb("MISS", note['lane'], current_time, 0)
                self.note_idx += 1
                # Do NOT break; check next note
            elif current_time >= note['time_ms'] and self.held_lns[note['lane']] is not None:
                # Overlap with held LN: Treat as PERFECT hit
                note['hit'] = True
                for sid in note['sample_ids']:
                    self.play_sound_cb(sid)
                self.set_judgment_cb("PERFECT", note['lane'], current_time, 0)
                self.last_note_time_per_lane[note['lane']] = note['time_ms']
                self.note_idx += 1
                # Do NOT break
            elif lane_presses[note['lane']] and abs(current_time - note['time_ms']) <= 40:
                # Holding Hit Logic:
                # If key is held AND this note is very close to the previous note in the same lane (Jack)
                # Adjacency threshold = 150ms
                if note['time_ms'] - self.last_note_time_per_lane[note['lane']] <= 150:
                    note['hit'] = True
                    for sid in note['sample_ids']:
                        self.play_sound_cb(sid)
                    self.set_judgment_cb("PERFECT", note['lane'], current_time, 0)
                    self.last_note_time_per_lane[note['lane']] = note['time_ms']
                    if note.get('is_ln'):
                        self.held_lns[note['lane']] = note
                        note['start_judgment'] = "PERFECT"
                    self.note_idx += 1
                else:
                    break
            else:
                # This note is in the future and not auto-playable
                break

        # Long notes - check for overdue release
        for lane, note in enumerate(self.held_lns):
            if note:
                miss_limit = note['end_time_ms'] + (JUDGMENT_DEFS["GOOD"]["threshold_ms"] * self.hw_mult)
                if current_time > miss_limit:
                    judgment = note.get('start_judgment', 'PERFECT')
                    self.set_judgment_cb(judgment, lane, current_time, 0)
                    for sid in note.get('end_sample_ids', []):
                        self.play_sound_cb(sid)
                    self.held_lns[lane] = None

        # Long Note Combo Ticks (CATCH UP logic)
        if any(self.held_lns):
            # If we jumped a lot of time, we might need multiple ticks
            while current_time - self.ln_tick_timer >= LN_COMBO_TICK_MS:
                self.ln_tick_timer += LN_COMBO_TICK_MS # Step forward precisely
                if self.on_ln_tick_cb:
                    self.on_ln_tick_cb(self.ln_tick_timer)
        else:
            self.ln_tick_timer = current_time

        # BGMs (Optimized index check)
        while self.bgm_idx < len(self.bgms):
            bgm = self.bgms[self.bgm_idx]
            if current_time >= bgm['time_ms']:
                self.play_sound_cb(bgm['sample_id'])
                self.bgm_idx += 1
            else:
                break

        # BGAs (Optimized index check)
        while self.bga_idx < len(self.bgas):
            bga = self.bgas[self.bga_idx]
            if current_time >= bga['time_ms']:
                self.current_bga_img = bga['bmp_id']
                self.bga_idx += 1
            else:
                break

        # Judgment update for all notes passed
        if not self.all_notes_passed and current_time > self.last_note_time + miss_window:
            self.all_notes_passed = True
            self.all_notes_passed_time = current_time

        # End check
        if current_time > self.max_time + SONG_END_PADDING_MS:
            self.state = "RESULT"
            return True
        return False
