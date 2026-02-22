import time
import numpy as np
from .constants import JUDGMENT_DEFS, SONG_END_PADDING_MS

class GameEngine:
    def __init__(self, notes, bgms, bgas, hw_mult, play_sound_cb, set_judgment_cb, max_time):
        self.notes = notes
        self.bgms = bgms
        self.bgas = bgas
        self.hw_mult = hw_mult
        self.play_sound_cb = play_sound_cb
        self.set_judgment_cb = set_judgment_cb
        self.max_time = max_time
        
        self.current_bga_img = None
        self.state = "PLAYING"

    def process_hit(self, lane, current_time):
        max_window = JUDGMENT_DEFS["GOOD"]["threshold_ms"] * self.hw_mult
        closest, min_diff = None, float('inf')

        for note in self.notes:
            if note['lane'] == lane and 'hit' not in note and 'miss' not in note and not note.get('is_auto'):
                diff = abs(note['time_ms'] - current_time)
                if diff < min_diff and diff <= max_window:
                    min_diff = diff
                    closest = note

        if closest:
            closest['hit'] = True
            for sid in closest['sample_ids']:
                self.play_sound_cb(sid)

            for key in ("PERFECT", "GREAT", "GOOD"):
                if min_diff <= JUDGMENT_DEFS[key]["threshold_ms"] * self.hw_mult:
                    self.set_judgment_cb(key, lane)
                    return True
        return False

    def update(self, current_time):
        miss_window = JUDGMENT_DEFS["MISS"]["threshold_ms"] * self.hw_mult
        
        # Normal notes
        for note in self.notes:
            if 'hit' not in note and 'miss' not in note:
                if note.get('is_auto'):
                    if current_time >= note['time_ms']:
                        note['hit'] = True
                        for sid in note['sample_ids']:
                            self.play_sound_cb(sid)
                    continue

                if current_time - note['time_ms'] > miss_window:
                    note['miss'] = True
                    self.set_judgment_cb("MISS", note['lane'])

        # BGMs
        for bgm in self.bgms:
            if 'played' not in bgm and current_time >= bgm['time_ms']:
                bgm['played'] = True
                self.play_sound_cb(bgm['sample_id'])

        # BGAs
        for bga in self.bgas:
            if 'played' not in bga and current_time >= bga['time_ms']:
                bga['played'] = True
                self.current_bga_img = bga['bmp_id']

        # End check
        if current_time > self.max_time + SONG_END_PADDING_MS:
            self.state = "RESULT"
            return True
        return False
