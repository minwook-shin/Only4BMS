import os
import re

# Note: We now dynamically detect playable channels (11-1Z, 21-2Z)
# to compress any BMS (5-key, 7-key, 10-key, 14-key, etc.) into 4 lanes.
BGM_CHANNEL = '01'
BGA_CHANNEL = '04'
NUM_LANES = 4

# ── Audio extension fallbacks ─────────────────────────────────────────────
AUDIO_FALLBACK_EXTS = ('.ogg', '.mp3', '.WAV', '.OGG')

# ── Header tag patterns ───────────────────────────────────────────────────
_HEADER_TAGS = {
    '#TITLE':       'title',
    '#ARTIST':      'artist',
    '#PLAYLEVEL':   'playlevel',
    '#GENRE':       'genre',
    '#STAGEFILE':   'stagefile',
    '#BANNER':      'banner',
    '#TOTAL':       'total',
    '#PREVIEW':     'preview',
}
_BPM_TAG = '#BPM '
_NOTE_PATTERN = re.compile(r'#(\d{3})(1[1-9A-Z]|2[1-9A-Z]):(.+)')
_CHANNEL_PATTERN = re.compile(r'#(\d{3})([0-9A-Z]{2}):(.+)')
_WAV_PATTERN = re.compile(r'#WAV([0-9a-zA-Z]{2})\s+(.+)')
_BMP_PATTERN = re.compile(r'#BMP([0-9a-zA-Z]{2})\s+(.+)')
_MEASURE_LEN_PATTERN = re.compile(r'#(\d{3})02:(.+)')
_BPM_EXT_PATTERN = re.compile(r'#BPM([0-9a-zA-Z]{2})\s+(.+)')
_STOP_PATTERN = re.compile(r'#STOP([0-9a-zA-Z]{2})\s+(.+)')
_LNOBJ_TAG = '#LNOBJ '
_LNTYPE_TAG = '#LNTYPE '


class BMSParser:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.bms_dir = os.path.dirname(filepath)

        with open(filepath, 'rb') as f:
            import hashlib
            self.hash = hashlib.md5(f.read()).hexdigest()

        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            self.lines = f.read().split('\n')

        # Metadata
        self.title = "Unknown"
        self.artist = "Unknown"
        self.bpm = 120.0
        self.playlevel = "0"
        self.genre = "Unknown"
        self.stagefile = None  # cover image path
        self.banner = None
        self.total = 200.0 # Default total
        self.preview = None # preview audio path
        self.total_notes = 0

        # Asset maps
        self.wav_map = {}   # wav_id → filepath
        self.bmp_map = {}   # bmp_id → filepath
        self.ln_obj = None  # LNOBJ id
        self.ln_type = 1    # LNTYPE (1 is standard toggle)
        self.bpm_map = {}   # bpm_id → bpm_value
        self.stop_map = {}  # stop_id → stop_value
        self.visual_timing_map = []  # [(real_time, visual_time, factor)]

        # Parsed output
        self.notes = []     # [{time_ms, lane, sample_ids}]
        self.bgms = []      # [{time_ms, sample_id}]
        self.bgas = []      # [{time_ms, bmp_id}]
        self.measure_lengths = {}  # measure → length ratio
        self.measures = []  # [{measure, real_time, visual_time}]

    # ── Quick metadata scan (no full parse) ──────────────────────────────

    def get_metadata(self):
        """Parse only header metadata and count playable notes."""
        self._parse_header(metadata_only=True)
        # Ensure we at least try to find a background even if tags are missing
        if not self.stagefile:
            self.stagefile = self._resolve_image_path(None)
        if not self.banner:
            self.banner = self._resolve_image_path(None)
            
        return (self.title, self.artist, self.bpm, self.playlevel, 
                self.genre, self.total_notes, self.preview, self.stagefile, self.banner, self.hash)

    # ── Full parse ───────────────────────────────────────────────────────

    def parse(self):
        """Parse the entire BMS file: header, channels, notes, BGM, BGA."""
        self._parse_header(metadata_only=False)
        self._parse_channels()
        self._resolve_wav_paths()
        return self.notes, self.bgms, self.bgas, self.bmp_map, self.visual_timing_map, self.measures

    # ── Internal: header ─────────────────────────────────────────────────

    def _parse_header(self, metadata_only=False):
        """Parse header tags. If metadata_only, skip WAV/BMP definitions."""
        for line in self.lines:
            line = line.strip()
            if not line:
                continue

            # Standard string tags
            line_upper = line.upper()
            found_tag = False
            parts = line.split(None, 1)
            if len(parts) >= 2:
                tag, val = parts[0].upper(), parts[1]
                for prefix, attr in _HEADER_TAGS.items():
                    if tag == prefix.upper():
                        # Resolve image/audio paths to absolute
                        if attr in ('stagefile', 'banner'):
                            val = self._resolve_image_path(os.path.join(self.bms_dir, val.strip()))
                        elif attr == 'preview':
                            val = os.path.join(self.bms_dir, val.strip())
                        
                        if attr == 'total':
                            try:
                                setattr(self, attr, float(val))
                            except: pass
                        else:
                            setattr(self, attr, val)
                        found_tag = True
                        break
            
            if found_tag:
                continue

            # BPM
            if line_upper.startswith(_BPM_TAG.upper()):
                try:
                    self.bpm = float(line.split(' ')[1])
                except (ValueError, IndexError):
                    pass
            # Count notes (metadata mode)
            elif metadata_only and _NOTE_PATTERN.match(line):
                m = _NOTE_PATTERN.match(line)
                if m:
                    data = m.group(3)
                    events = [data[i:i+2] for i in range(0, len(data), 2)]
                    self.total_notes += sum(1 for e in events if e != '00')
            # WAV definitions
            elif line_upper.startswith('#WAV'):
                m = _WAV_PATTERN.match(line)
                if m:
                    self.wav_map[m.group(1).upper()] = os.path.join(self.bms_dir, m.group(2).strip())
            # BMP definitions
            elif line_upper.startswith('#BMP'):
                m = _BMP_PATTERN.match(line)
                if m:
                    self.bmp_map[m.group(1).upper()] = os.path.join(self.bms_dir, m.group(2).strip())
            # Measure length
            elif re.match(r'#\d{3}02:', line):
                m = _MEASURE_LEN_PATTERN.match(line)
                if m:
                    try:
                        self.measure_lengths[int(m.group(1))] = float(m.group(2))
                    except ValueError:
                        pass
            # LNOBJ
            elif line_upper.startswith(_LNOBJ_TAG.upper()):
                self.ln_obj = line.split(' ', 1)[1].strip().upper()
            # LNTYPE
            elif line_upper.startswith(_LNTYPE_TAG.upper()):
                try:
                    self.ln_type = int(line.split(' ', 1)[1].strip())
                except ValueError:
                    pass
            # BPM definitions (#BPMxx)
            elif line_upper.startswith('#BPM'):
                m = _BPM_EXT_PATTERN.match(line)
                if m:
                    try:
                        self.bpm_map[m.group(1).upper()] = float(m.group(2))
                    except ValueError:
                        pass
            # STOP definitions (#STOPxx)
            elif line_upper.startswith('#STOP'):
                m = _STOP_PATTERN.match(line)
                if m:
                    try:
                        self.stop_map[m.group(1).upper()] = float(m.group(2))
                    except ValueError:
                        pass

    # ── Internal: channels & note assignment ─────────────────────────────

    def _parse_channels(self):
        """Process channel data into timed notes, BGMs, and BGAs."""
        # 1. Collect all raw events
        events_by_measure = {} # measure -> {channel -> {pos -> ev}}
        max_measure = 0
        for line in self.lines:
            m_match = _CHANNEL_PATTERN.match(line.strip())
            if not m_match:
                continue
            measure, ch, data = int(m_match.group(1)), m_match.group(2), m_match.group(3)
            max_measure = max(max_measure, measure)
            evs = [data[i:i+2] for i in range(0, len(data), 2)]
            n = len(evs)
            
            for i, ev in enumerate(evs):
                if ev == '00': continue
                pos = i / n
                # Use a list to support multiple events at the same position (layering)
                events_by_measure.setdefault(measure, {}).setdefault(ch, {}).setdefault(pos, []).append(ev)

        # 2. Integrate timing (BPM & Stops) to find event times and measure starts
        initial_bpm = self.bpm
        current_bpm = self.bpm
        current_real_time = 0.0
        current_visual_time = 0.0
        event_timings = {} # (measure, ch, pos) -> (real_time, visual_time)
        
        # Segment: (start_real, start_visual, speed_factor)
        self.visual_timing_map = [(0.0, 0.0, 1.0)]
        self.measures = []

        for m in range(max_measure + 1):
            # Record each measure's start time and current BPM for bar-line rendering
            self.measures.append({
                'measure': m,
                'real_time_ms': current_real_time,
                'visual_time_ms': current_visual_time,
                'bpm': current_bpm
            })
            
            m_len = self.measure_lengths.get(m, 1.0)
            m_data = events_by_measure.get(m, {})
            all_positions = sorted(set(pos for ch_data in m_data.values() for pos in ch_data))
            
            last_pos = 0.0
            for pos in all_positions:
                delta_beats = (pos - last_pos) * 4.0 * m_len
                delta_real_ms = delta_beats * (60_000.0 / current_bpm)
                delta_visual_ms = delta_beats * (60_000.0 / initial_bpm)
                
                current_real_time += delta_real_ms
                current_visual_time += delta_visual_ms
                
                for ch, ch_data in m_data.items():
                    if pos in ch_data:
                        event_timings[(m, ch, pos)] = (current_real_time, current_visual_time)
                
                # Apply Timing Changes (BPM/Stop)
                timing_changed = False
                if '03' in m_data and pos in m_data['03']: # BPM Change (hex)
                    try:
                        current_bpm = int(m_data['03'][pos][0], 16)
                        timing_changed = True
                    except ValueError: pass
                if '08' in m_data and pos in m_data['08']: # Ext BPM
                    bpm_id = m_data['08'][pos][0].upper()
                    if bpm_id in self.bpm_map:
                        current_bpm = self.bpm_map[bpm_id]
                        timing_changed = True
                
                if timing_changed:
                    self.visual_timing_map.append((current_real_time, current_visual_time, current_bpm / initial_bpm))
                    if pos == 0.0:
                        self.measures[-1]['bpm'] = current_bpm

                if '09' in m_data and pos in m_data['09']: # STOP
                    stop_id = m_data['09'][pos][0].upper()
                    if stop_id in self.stop_map:
                        stop_val = self.stop_map[stop_id]
                        stop_ms = (stop_val / 192.0) * (4.0 * 60_000.0 / current_bpm)
                        # Freeze scroll: factor becomes 0
                        self.visual_timing_map.append((current_real_time, current_visual_time, 0.0))
                        current_real_time += stop_ms
                        # Resume scroll
                        self.visual_timing_map.append((current_real_time, current_visual_time, current_bpm / initial_bpm))
                
                last_pos = pos
            
            # Finish the measure
            delta_to_end_beats = (1.0 - last_pos) * 4.0 * m_len
            current_real_time += delta_to_end_beats * (60_000.0 / current_bpm)
            current_visual_time += delta_to_end_beats * (60_000.0 / initial_bpm)

        # 3. Process events into grouped notes using calculated timings
        grouped_notes = {}  # time_ms → [note_data_with_v_time]
        for t_key in sorted(event_timings):
            m, ch, pos = t_key
            real_time, visual_time = event_timings[t_key]
            ev_list = events_by_measure[m][ch][pos]
            
            for ev in ev_list:
                is_playable = (ch.startswith('1') or ch.startswith('2') or 
                               ch.startswith('5') or ch.startswith('6')) and ch[1] != '0'
                
                if is_playable:
                    grouped_notes.setdefault(real_time, []).append({'ch': ch, 'ev': ev, 'v_time_ms': visual_time})
                elif ch == BGM_CHANNEL:
                    self.bgms.append({'time_ms': real_time, 'sample_id': ev})
                elif ch == BGA_CHANNEL:
                    self.bgas.append({'time_ms': real_time, 'bmp_id': ev})

        # Smart lane assignment
        last_lane_time = [-1000.0] * NUM_LANES
        open_lns = {} # ch -> {note_index}
        last_note_idx_by_ch = {} # ch -> note_index

        for t in sorted(grouped_notes):
            for data in grouped_notes[t]:
                ch, ev = data['ch'], data['ev']
                
                # Handling LN End (if LNOBJ or LN channel toggle)
                if self.ln_obj and ev == self.ln_obj and (ch.startswith('1') or ch.startswith('2')):
                        note_idx = last_note_idx_by_ch[ch]
                        self.notes[note_idx]['end_time_ms'] = t
                        self.notes[note_idx]['visual_end_time_ms'] = data['v_time_ms']
                        self.notes[note_idx]['is_ln'] = True
                        self.notes[note_idx].setdefault('end_sample_ids', []).append(ev)
                        # Release the lane
                        lane = self.notes[note_idx]['lane']
                        last_lane_time[lane] = t
                        continue
                
                if ch in open_lns and (ch.startswith('5') or ch.startswith('6')):
                    note_idx = open_lns.pop(ch)
                    self.notes[note_idx]['end_time_ms'] = t
                    self.notes[note_idx]['visual_end_time_ms'] = data['v_time_ms']
                    self.notes[note_idx]['is_ln'] = True
                    self.notes[note_idx].setdefault('end_sample_ids', []).append(ev)
                    # Release the lane
                    lane = self.notes[note_idx]['lane']
                    last_lane_time[lane] = t
                    continue

                # Pick the lane idle for the longest
                best = max(range(NUM_LANES), key=lambda l: t - last_lane_time[l])
                
                # Check if we should start an LN
                is_ln_start = bool(ch.startswith('5') or ch.startswith('6'))
                
                # Merge into existing note at same time AND lane if possible (includes multi-note stacks)
                merged = False
                # Search backwards for a note at same time and lane
                for i in range(len(self.notes)-1, -1, -1):
                    prev_note = self.notes[i]
                    if abs(prev_note['time_ms'] - t) > 0.1: break # Too far back
                    if prev_note['lane'] == best and 'end_time_ms' not in prev_note:
                        prev_note['sample_ids'].append(ev)
                        last_note_idx_by_ch[ch] = i
                        merged = True
                        break
                
                if not merged:
                    note_idx = len(self.notes)
                    self.notes.append({
                        'time_ms': t, 
                        'visual_time_ms': data['v_time_ms'],
                        'lane': best, 
                        'sample_ids': [ev]
                    })
                    
                    # Track end time for lane assignment if it's an LN
                    if is_ln_start:
                        open_lns[ch] = note_idx
                        # We'll update last_lane_time[best] once we know the end_time_ms
                        # For now, mark it as "very busy"
                        last_lane_time[best] = t + 999999.0 
                    else:
                        last_lane_time[best] = t
                    
                    last_note_idx_by_ch[ch] = note_idx

        # Close any dangling LNs (graceful failure)
        for ch, idx in open_lns.items():
            self.notes[idx]['end_time_ms'] = self.notes[idx]['time_ms'] + 100
            self.notes[idx]['visual_end_time_ms'] = self.notes[idx]['visual_time_ms'] + 100
            self.notes[idx]['is_ln'] = True

        # Tag Auto-Notes: If a note is within 20ms of previous note in SAME lane, mark as auto.
        # This prevents 4-lane compressed charts from being physically impossible.
        self.notes.sort(key=lambda x: (x['lane'], x['time_ms']))
        for i in range(1, len(self.notes)):
            prev = self.notes[i-1]
            curr = self.notes[i]
            if curr['lane'] == prev['lane'] and (curr['time_ms'] - prev['time_ms'] < 30.0):
                curr['is_auto'] = True

        # Sort by time
        self.notes.sort(key=lambda x: x['time_ms'])
        self.bgms.sort(key=lambda x: x['time_ms'])
        self.bgas.sort(key=lambda x: x['time_ms'])

    # ── Internal: resolve wav file paths ─────────────────────────────────

    def _resolve_image_path(self, path):
        """Resolve image paths with case-insensitivity and extension fallback."""
        if path and os.path.exists(path):
            return path
            
        parent = self.bms_dir
        if path:
            base = os.path.splitext(path)[0]
            fname_base = os.path.basename(base).lower()
            parent = os.path.dirname(path)
        else:
            fname_base = None

        try:
            files = os.listdir(parent)
            # 1. Try to match the specified name (case-insensitive)
            if fname_base:
                for f in files:
                    f_base, f_ext = os.path.splitext(f)
                    if f_base.lower() == fname_base and f_ext.lower() in ('.png', '.jpg', '.jpeg', '.bmp'):
                        return os.path.join(parent, f)
            
            # 2. Fallback: Search for common cover filenames in the directory
            cover_names = ('folder', 'cover', 'stagefile', 'banner', 'title', 'jacket', 'bg')
            for f in files:
                f_base, f_ext = os.path.splitext(f)
                if f_base.lower() in cover_names and f_ext.lower() in ('.png', '.jpg', '.jpeg', '.bmp'):
                    return os.path.join(parent, f)
        except:
            pass
        return path

    def _resolve_wav_paths(self):
        """Resolve WAV paths, trying common alternative extensions if missing."""
        resolved = {}
        for wav_id, path in self.wav_map.items():
            if os.path.exists(path):
                resolved[wav_id] = path
            else:
                base = os.path.splitext(path)[0]
                for ext in AUDIO_FALLBACK_EXTS:
                    alt = base + ext
                    if os.path.exists(alt):
                        resolved[wav_id] = alt
                        break
                else:
                    resolved[wav_id] = path  # keep original for graceful failure
        self.wav_map = resolved
