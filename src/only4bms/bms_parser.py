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
    '#TITLE ':    'title',
    '#ARTIST ':   'artist',
    '#PLAYLEVEL ':'playlevel',
    '#GENRE ':    'genre',
    '#STAGEFILE ':'stagefile',
    '#BANNER ':   'banner',
}
_BPM_TAG = '#BPM '
_NOTE_PATTERN = re.compile(r'#(\d{3})(1[1-9A-Z]|2[1-9A-Z]):(.+)')
_CHANNEL_PATTERN = re.compile(r'#(\d{3})([0-9A-Z]{2}):(.+)')
_WAV_PATTERN = re.compile(r'#WAV([0-9a-zA-Z]{2})\s+(.+)')
_BMP_PATTERN = re.compile(r'#BMP([0-9a-zA-Z]{2})\s+(.+)')
_MEASURE_LEN_PATTERN = re.compile(r'#(\d{3})02:(.+)')


class BMSParser:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.bms_dir = os.path.dirname(filepath)

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
        self.total_notes = 0

        # Asset maps
        self.wav_map = {}   # wav_id → filepath
        self.bmp_map = {}   # bmp_id → filepath

        # Parsed output
        self.notes = []     # [{time_ms, lane, sample_ids}]
        self.bgms = []      # [{time_ms, sample_id}]
        self.bgas = []      # [{time_ms, bmp_id}]
        self.measure_lengths = {}  # measure → length ratio

    # ── Quick metadata scan (no full parse) ──────────────────────────────

    def get_metadata(self):
        """Parse only header metadata and count playable notes."""
        self._parse_header(metadata_only=True)
        return self.title, self.artist, self.bpm, self.playlevel, self.genre, self.total_notes

    # ── Full parse ───────────────────────────────────────────────────────

    def parse(self):
        """Parse the entire BMS file: header, channels, notes, BGM, BGA."""
        self._parse_header(metadata_only=False)
        self._parse_channels()
        self._resolve_wav_paths()
        return self.notes, self.bgms, self.bgas, self.bmp_map

    # ── Internal: header ─────────────────────────────────────────────────

    def _parse_header(self, metadata_only=False):
        """Parse header tags. If metadata_only, skip WAV/BMP definitions."""
        for line in self.lines:
            line = line.strip()
            if not line:
                continue

            # Standard string tags
            for prefix, attr in _HEADER_TAGS.items():
                if line.startswith(prefix):
                    val = line.split(' ', 1)[1]
                    # Resolve image paths to absolute
                    if attr in ('stagefile', 'banner'):
                        val = os.path.join(self.bms_dir, val.strip())
                    setattr(self, attr, val)
                    break
            else:
                # BPM
                if line.startswith(_BPM_TAG):
                    try:
                        self.bpm = float(line.split(' ')[1])
                    except ValueError:
                        pass
                # Count notes (metadata mode)
                elif metadata_only:
                    m = _NOTE_PATTERN.match(line)
                    if m:
                        data = m.group(3)
                        events = [data[i:i+2] for i in range(0, len(data), 2)]
                        self.total_notes += sum(1 for e in events if e != '00')
                # WAV definitions
                elif line.startswith('#WAV'):
                    m = _WAV_PATTERN.match(line)
                    if m:
                        self.wav_map[m.group(1).upper()] = os.path.join(self.bms_dir, m.group(2).strip())
                # BMP definitions
                elif line.startswith('#BMP'):
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

    # ── Internal: channels & note assignment ─────────────────────────────

    def _parse_channels(self):
        """Process channel data into timed notes, BGMs, and BGAs."""
        ms_per_measure = 240_000 / self.bpm
        events_by_measure = {}
        max_measure = 0

        # Collect raw events
        for line in self.lines:
            m = _CHANNEL_PATTERN.match(line.strip())
            if not m:
                continue
            measure, channel, data = int(m.group(1)), m.group(2), m.group(3)
            max_measure = max(max_measure, measure)
            events_by_measure.setdefault(measure, []).append({
                'channel': channel,
                'events': [data[i:i+2] for i in range(0, len(data), 2)],
            })

        # Build measure start times
        measure_starts = {}
        t = 0.0
        for m in range(max_measure + 1):
            measure_starts[m] = t
            t += ms_per_measure * self.measure_lengths.get(m, 1.0)

        # Process events into grouped notes
        grouped_notes = {}  # time_ms → [sample_ids]

        for measure, channel_events in events_by_measure.items():
            start = measure_starts[measure]
            duration = ms_per_measure * self.measure_lengths.get(measure, 1.0)

            for ce in channel_events:
                ch, events = ce['channel'], ce['events']
                n = len(events)
                for i, ev in enumerate(events):
                    if ev == '00':
                        continue
                    event_time = start + duration * (i / n)

                    # Playable channels: 11-1Z (Player 1), 21-2Z (Player 2)
                    if (ch.startswith('1') or ch.startswith('2')) and ch[1] != '0':
                        grouped_notes.setdefault(event_time, []).append(ev)
                    elif ch == BGM_CHANNEL:
                        self.bgms.append({'time_ms': event_time, 'sample_id': ev})
                    elif ch == BGA_CHANNEL:
                        self.bgas.append({'time_ms': event_time, 'bmp_id': ev})

        # Smart lane assignment (distribute to least-recently-used lanes)
        last_lane_time = [-1000.0] * NUM_LANES

        for t in sorted(grouped_notes):
            remaining = list(grouped_notes[t])
            while remaining:
                # Pick the lane idle for the longest
                best = max(range(NUM_LANES), key=lambda l: t - last_lane_time[l])
                sid = remaining.pop(0)

                # Merge into existing note at same time+lane if possible
                if self.notes and self.notes[-1]['time_ms'] == t and self.notes[-1]['lane'] == best:
                    self.notes[-1]['sample_ids'].append(sid)
                else:
                    self.notes.append({'time_ms': t, 'lane': best, 'sample_ids': [sid]})
                    last_lane_time[best] = t

        # Sort by time
        self.notes.sort(key=lambda x: x['time_ms'])
        self.bgms.sort(key=lambda x: x['time_ms'])
        self.bgas.sort(key=lambda x: x['time_ms'])

    # ── Internal: resolve wav file paths ─────────────────────────────────

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
