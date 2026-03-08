import os
import random
import wave
import numpy as np

import only4bms.i18n as i18n

# ── A minor pentatonic frequencies across octaves ──────────────────────────
# A, C, D, E, G
_PENTA = {
    1: [55.0, 65.41, 73.42, 82.41, 98.0],
    2: [110.0, 130.81, 146.83, 164.81, 196.0],
    3: [220.0, 261.63, 293.66, 329.63, 392.0],
    4: [440.0, 523.25, 587.33, 659.25, 784.0],
}

# ── Master sound table ─────────────────────────────────────────────────────
# (wav_id, filename, freq, duration, wave_type, volume)
_SOUND_TABLE = [
    # BGM percussion
    ("01", "kick.wav",       80,    0.5,  'kick',       0.9),
    ("02", "snare.wav",      400,   0.3,  'noise',      0.7),
    ("03", "hat_closed.wav", 800,   0.1,  'noise',      0.5),
    ("04", "hat_open.wav",   6000,  0.25, 'hihat_open', 0.5),
    # Sub bass (octave 1)
    *[("%02X" % (0x10 + i), f"bass_{i}.wav", _PENTA[1][i], 0.8, 'sub_bass', 0.85) for i in range(5)],
    # Bass pluck (octave 2)
    *[("%02X" % (0x15 + i), f"bpluck_{i}.wav", _PENTA[2][i], 0.2, 'pluck', 0.7) for i in range(5)],
    # Lead low (octave 3)
    *[("1%s" % chr(65 + i), f"lead_lo_{i}.wav", _PENTA[3][i], 0.25, 'synth_lead', 0.65) for i in range(5)],
    # Lead high (octave 4)
    *[("1%s" % chr(70 + i), f"lead_hi_{i}.wav", _PENTA[4][i], 0.25, 'synth_lead', 0.65) for i in range(5)],
    # Arp pluck (octave 4)
    *[("%02X" % (0x20 + i), f"arp_{i}.wav", _PENTA[4][i], 0.15, 'pluck', 0.7) for i in range(5)],
    # Chord stab (octave 3)
    *[("%02X" % (0x25 + i), f"chord_{i}.wav", _PENTA[3][i], 0.2, 'chord_stab', 0.6) for i in range(5)],
    # FX
    ("2A", "fx_riser_lo.wav",  400, 0.3, 'fx_riser',  0.5),
    ("2B", "fx_riser_hi.wav",  600, 0.3, 'fx_riser',  0.5),
    ("2C", "fx_impact_lo.wav", 80,  0.2, 'fx_impact', 0.7),
    ("2D", "fx_impact_hi.wav", 120, 0.2, 'fx_impact', 0.7),
]


def _build_sound_palette():
    """Return categorized WAV ID groups for note assignment."""
    return {
        'bass':       ["%02X" % (0x10 + i) for i in range(5)],
        'bass_pluck': ["%02X" % (0x15 + i) for i in range(5)],
        'lead_lo':    ["1%s" % chr(65 + i) for i in range(5)],
        'lead_hi':    ["1%s" % chr(70 + i) for i in range(5)],
        'arp':        ["%02X" % (0x20 + i) for i in range(5)],
        'chord':      ["%02X" % (0x25 + i) for i in range(5)],
        'fx_riser':   ["2A", "2B"],
        'fx_impact':  ["2C", "2D"],
        'hat_open':   ["04"],
    }


def _pick_note_sound(palette, lane_idx, step, measure_num, phrase):
    """Pick a WAV ID based on lane, beat position, and musical phrase state."""
    root = phrase['root_idx']
    style = phrase['style']
    pitch_idx = (root + step // 4) % 5

    if lane_idx == 0:  # Bass register
        if step % 8 == 0:
            return palette['bass'][pitch_idx]
        return palette['bass_pluck'][pitch_idx]

    elif lane_idx == 1:  # Mid-low: lead / chord
        if step % 4 == 0 and (style == 'future_bass' or random.random() < 0.4):
            return palette['chord'][pitch_idx]
        return palette['lead_lo'][(pitch_idx + 1) % 5]

    elif lane_idx == 2:  # Mid-high: lead / arp
        if style == 'arp' or step % 2 == 0:
            arp_idx = (pitch_idx + step // 2) % 5
            return palette['arp'][arp_idx]
        return palette['lead_hi'][pitch_idx]

    else:  # lane 3: High / FX
        if step == 0 and random.random() < 0.15:
            return random.choice(palette['fx_impact'])
        if step % 2 != 0:
            return palette['arp'][(pitch_idx + 2) % 5]
        return palette['lead_hi'][(pitch_idx + 3) % 5]


def _ns(palette, lane, lanes, step, m, phrase):
    """Shorthand: resolve lane string to index and pick note sound."""
    return _pick_note_sound(palette, lanes.index(lane), step, m, phrase)


def _generate_wav(filename, freq, duration_sec, wave_type='sine', samplerate=44100, volume=0.5):
    if os.path.exists(filename):
        return

    t = np.linspace(0, duration_sec, int(samplerate * duration_sec), endpoint=False)

    if wave_type == 'sine':
        audio = np.sin(2 * np.pi * freq * t)
    elif wave_type == 'square':
        audio = np.sign(np.sin(2 * np.pi * freq * t))
    elif wave_type == 'kick':
        freq_env = np.exp(-t * 30) * freq
        audio = np.sin(2 * np.pi * freq_env * t)
    elif wave_type == 'noise':
        audio = np.random.uniform(-1, 1, len(t))
    elif wave_type == 'clack':
        noise = np.random.uniform(-1, 1, len(t)) * 0.5
        pulse = np.sin(2 * np.pi * freq * t) * 0.5
        audio = noise + pulse
    elif wave_type == 'sub_bass':
        # Saw-based bass with harmonics — blends with synth_lead/pluck palette
        saw = 2.0 * ((t * freq) % 1.0) - 1.0
        saw2 = 2.0 * ((t * freq * 2.005) % 1.0) - 1.0  # octave up, slight detune
        audio = saw * 0.6 + saw2 * 0.3
        # Soft clip for warmth (tanh distortion)
        audio = np.tanh(audio * 2.0) * 0.7
    elif wave_type == 'synth_lead':
        # Detuned supersaw: 3 slightly detuned sawtooth waves
        saw1 = 2.0 * ((t * freq) % 1.0) - 1.0
        saw2 = 2.0 * ((t * freq * 1.005) % 1.0) - 1.0
        saw3 = 2.0 * ((t * freq * 0.995) % 1.0) - 1.0
        audio = (saw1 + saw2 + saw3) / 3.0
    elif wave_type == 'pluck':
        # Short pluck: sine + 2nd harmonic, fast decay
        audio = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(4 * np.pi * freq * t)
    elif wave_type == 'chord_stab':
        # Root + major 3rd + 5th
        audio = (np.sin(2 * np.pi * freq * t) +
                 np.sin(2 * np.pi * freq * 1.26 * t) +
                 np.sin(2 * np.pi * freq * 1.5 * t)) / 3.0
    elif wave_type == 'fx_riser':
        # Frequency sweep upward
        sweep = np.linspace(freq, freq * 4, len(t))
        audio = np.sin(2 * np.pi * np.cumsum(sweep) / samplerate)
    elif wave_type == 'fx_impact':
        # Noise burst + low sine
        audio = np.random.uniform(-1, 1, len(t)) * 0.6 + np.sin(2 * np.pi * freq * t) * 0.4
    elif wave_type == 'hihat_open':
        # Longer noise with bandpass-like shaping
        audio = np.random.uniform(-1, 1, len(t))
        # Simple highpass: subtract smoothed version
        kernel_size = max(1, int(samplerate * 0.001))
        if kernel_size > 1:
            smooth = np.convolve(audio, np.ones(kernel_size) / kernel_size, mode='same')
            audio = audio - smooth * 0.5
    else:
        audio = np.sin(2 * np.pi * freq * t)

    # Envelopes per wave type
    if wave_type == 'kick':
        envelope = np.exp(-t * 30)
    elif wave_type == 'clack':
        envelope = np.exp(-t * 80)
    elif wave_type == 'noise':
        envelope = np.exp(-t * 20)
    elif wave_type == 'sub_bass':
        # Slower decay for sustained bass body
        attack = np.minimum(t / 0.005, 1.0)
        envelope = attack * np.exp(-t * 2.5)
    elif wave_type == 'synth_lead':
        # ADSR-like: fast attack, decay to sustain, then release
        attack = np.minimum(t / 0.01, 1.0)
        release = np.exp(-np.maximum(t - 0.15, 0) * 6)
        envelope = attack * release
    elif wave_type == 'pluck':
        envelope = np.exp(-t * 15)
    elif wave_type == 'chord_stab':
        envelope = np.exp(-t * 8)
    elif wave_type == 'fx_riser':
        # Ramp up then sharp cut
        envelope = np.minimum(t / (duration_sec * 0.8), 1.0)
    elif wave_type == 'fx_impact':
        envelope = np.exp(-t * 25)
    elif wave_type == 'hihat_open':
        envelope = np.exp(-t * 6)
    else:
        envelope = np.exp(-t * 3)

    audio = audio * envelope * volume
    # Clip to prevent overflow before int16 conversion
    audio = np.clip(audio, -1.0, 1.0)
    audio = np.int16(audio * 32767)

    with wave.open(filename, 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(samplerate)
        w.writeframes(audio.tobytes())


def generate_random_course(duration_ms, out_path, template_dir, difficulty="BEGINNER"):
    """
    Generates a procedural 4-key BMS chart based on the selected difficulty.
    The chart lasts approximately `duration_ms`.
    Returns (out_path, description).
    """
    if not os.path.exists(template_dir):
        os.makedirs(template_dir, exist_ok=True)
    if not os.path.exists(os.path.dirname(out_path)):
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # Force regeneration of all procedural WAV assets
    for entry in _SOUND_TABLE:
        wav_path = os.path.join(template_dir, entry[1])
        if os.path.exists(wav_path):
            try: os.remove(wav_path)
            except: pass

    # Generate all WAV assets
    for wav_id, fname, freq, dur, wtype, vol in _SOUND_TABLE:
        _generate_wav(os.path.join(template_dir, fname), freq, dur, wtype, volume=vol)

    # Sound palette and phrase state
    palette = _build_sound_palette()
    phrase = {
        'root_idx': 0,
        'style': random.choice(['trap', 'future_bass', 'arp']),
    }

    has_ln = False
    has_sv = False
    desc_str = ""

    # Base BPM changes per difficulty to increase baseline physical demand
    if difficulty == "BEGINNER":
        bpm = random.randint(80, 110)
        desc_str = i18n.get("gen_beg_desc").format(bpm=bpm)
    elif difficulty == "INTERMEDIATE":
        bpm = random.randint(120, 160)
        has_ln = random.random() < 0.3
        has_sv = False # Removed SV for Intermediate
        desc_str = i18n.get("gen_int_desc").format(bpm=bpm)
    elif difficulty == "ADVANCED":
        bpm = random.randint(160, 200)
        has_ln = random.random() < 0.5
        has_sv = random.random() < 0.4
        desc_str = i18n.get("gen_adv_desc").format(bpm=bpm)
    elif difficulty == "ORDEAL":
        bpm = random.randint(180, 220)
        has_ln = True
        has_sv = True
        desc_str = i18n.get("gen_ord_desc").format(bpm=bpm)
    else:
        # Fallback for any unknown difficulty
        bpm = 150
        desc_str = i18n.get("gen_custom_trial").format(bpm=bpm)

    if has_ln: desc_str += i18n.get("gen_ln")
    if has_sv: desc_str += i18n.get("gen_sv")

    header = f"""#PLAYER 1
#GENRE AI COURSE ({difficulty})
#TITLE Procedural Training
#ARTIST AI Generator
#BPM {bpm}
#BPM {bpm}
#BPM00 {bpm}
#BPM11 {bpm * 0.98:.2f}
#BPM12 {bpm * 0.96:.2f}
#BPM13 {bpm * 0.94:.2f}
#BPM14 {bpm * 0.92:.2f}
#BPM15 {bpm * 0.90:.2f}
#BPM16 {bpm * 0.88:.2f}
#BPM17 {bpm * 0.86:.2f}
#BPM18 {bpm * 0.85:.2f}
#BPM21 {bpm * 1.02:.2f}
#BPM22 {bpm * 1.04:.2f}
#BPM23 {bpm * 1.06:.2f}
#BPM24 {bpm * 1.08:.2f}
#BPM25 {bpm * 1.10:.2f}
#BPM26 {bpm * 1.12:.2f}
#BPM27 {bpm * 1.14:.2f}
#BPM28 {bpm * 1.15:.2f}
#PLAYLEVEL {'1' if difficulty=='BEGINNER' else '5' if difficulty=='INTERMEDIATE' else '10'}
"""
    for wav_id, fname, *_ in _SOUND_TABLE:
        header += f"#WAV{wav_id} {fname}\n"
    header += "\n"

    ms_per_measure = (240.0 / bpm) * 1000.0
    num_measures = int(duration_ms / ms_per_measure) + 1

    chart_data = ""
    lanes = ["11", "12", "13", "14"]  # 4-Key bounds in standard mapping
    ln_lanes = ["51", "52", "53", "54"]  # 4-Key bounds for LN

    def get_empty_measure():
        d = {l: ["00"] * 16 for l in lanes}
        d.update({ln: ["00"] * 16 for ln in ln_lanes})
        d["08"] = ["00"] * 16  # For BPM changes
        d["01"] = ["00"] * 16  # For BGM
        return d

    def ns(lane, step):
        """Pick note sound for a lane string at a given step."""
        return _pick_note_sound(palette, lanes.index(lane), step, m, phrase)

    def ns_idx(lane_idx, step):
        """Pick note sound for a lane index at a given step."""
        return _pick_note_sound(palette, lane_idx, step, m, phrase)

    for m in range(num_measures + 2):
        measure_str = f"{m:03d}"
        m_data = get_empty_measure()

        if m < 2:
            # 2 measures of empty space for countdown break
            chart_data += f"#{measure_str}01:00\n"
            continue

        # Update phrase state
        if (m - 2) % 4 == 0:
            phrase['root_idx'] = (phrase['root_idx'] + 2) % 5
        if (m - 2) % 8 == 0:
            phrase['style'] = random.choice(['trap', 'future_bass', 'arp'])

        # ── BGM drum pattern ──────────────────────────────────────────
        m_data["01"][0]  = "01"  # kick
        m_data["01"][4]  = "02"  # snare
        m_data["01"][8]  = "01"  # kick
        m_data["01"][12] = "02"  # snare

        # Hi-hat 8th notes on even measures
        if m % 2 == 0:
            for s in [2, 6, 10, 14]:
                m_data["01"][s] = "03"

        # Open hat accent every 4 measures
        if m % 4 == 2:
            m_data["01"][6] = "04"

        # FX riser on phrase transitions
        if m >= 2 and (m - 2) % 4 == 3:
            m_data["01"][12] = random.choice(palette['fx_riser'])

        # Inject BPM variations (Ultra-Smooth transition with ±15% caps)
        if has_sv and m > 2:
            # Shift frequency by difficulty
            freq = 4 if difficulty == "INTERMEDIATE" else 2
            if m % freq == 0:
                is_speed_up = random.random() < 0.5
                if is_speed_up:
                    m_data["08"][0] = "21"
                    m_data["08"][2] = "22"
                    m_data["08"][4] = "24"
                    m_data["08"][6] = "26"
                    m_data["08"][8] = "28"
                    m_data["08"][12] = "24"
                    m_data["08"][14] = "21"
                else:
                    m_data["08"][0] = "11"
                    m_data["08"][2] = "12"
                    m_data["08"][4] = "14"
                    m_data["08"][6] = "16"
                    m_data["08"][8] = "18"
                    m_data["08"][12] = "14"
                    m_data["08"][14] = "11"
            else:
                m_data["08"][0] = "00"

        # ── Note patterns ─────────────────────────────────────────────
        if difficulty == "BEGINNER":
            active = random.choice(lanes)
            rhythm_type = random.choice(["4th", "sparse"])
            if rhythm_type == "4th":
                for step in [0, 4, 8, 12]:
                    m_data[active][step] = ns(active, step)
            else:
                step = random.choice([0, 8])
                m_data[active][step] = ns(active, step)

        elif difficulty == "INTERMEDIATE":
            pattern_type = random.choice([
                "chords_8th", "trill_8th", "stairs_8th",
                "jack_8th", "combo_fill", "ln_dense", "alternating_8th"
            ])
            if pattern_type == "ln_dense" and not has_ln:
                pattern_type = "alternating_8th"

            if pattern_type == "ln_dense":
                ln_idx = random.randint(0, 3)
                m_data[ln_lanes[ln_idx]][0]  = ns_idx(ln_idx, 0)
                m_data[ln_lanes[ln_idx]][14] = ns_idx(ln_idx, 14)
                avail = [lanes[i] for i in range(4) if i != ln_idx]
                for step in range(0, 16, 2):
                    if random.random() < 0.7:
                        l = random.choice(avail)
                        m_data[l][step] = ns(l, step)

            elif pattern_type == "chords_8th":
                for step in range(0, 16, 2):
                    chord = random.sample(lanes, random.choice([1, 1, 2]))
                    for l in chord:
                        m_data[l][step] = ns(l, step)

            elif pattern_type == "trill_8th":
                tl = random.sample(lanes, 2)
                for i, step in enumerate(range(0, 16, 2)):
                    l = tl[i % 2]
                    m_data[l][step] = ns(l, step)

            elif pattern_type == "stairs_8th":
                def _has_long_run(seq, run=3):
                    for i in range(len(seq) - run + 1):
                        sub = seq[i:i+run]
                        diffs = [sub[j+1]-sub[j] for j in range(len(sub)-1)]
                        if all(d == 1 for d in diffs) or all(d == -1 for d in diffs):
                            return True
                    return False
                order = list(range(4))
                for _ in range(30):
                    random.shuffle(order)
                    seq = order + order[::-1]
                    if not _has_long_run(seq):
                        break
                for i in range(8):
                    lane_idx = seq[i]
                    step = i * 2
                    m_data[lanes[lane_idx]][step] = ns_idx(lane_idx, step)

            elif pattern_type == "jack_8th":
                jack = random.choice(lanes)
                fill = random.choice([l for l in lanes if l != jack])
                for step in range(0, 16, 2):
                    m_data[jack][step] = ns(jack, step)
                    if step % 4 == 0 and random.random() < 0.4:
                        m_data[fill][step] = ns(fill, step)

            elif pattern_type == "combo_fill":
                cross = random.choice([[0,2,1,3], [3,1,2,0], [1,3,0,2], [2,0,3,1]])
                for i, step in enumerate(range(0, 8, 2)):
                    m_data[lanes[cross[i]]][step] = ns_idx(cross[i], step)
                for step in range(8, 16, 2):
                    chord = random.sample(lanes, random.choice([1, 2]))
                    for l in chord:
                        m_data[l][step] = ns(l, step)

            else:  # alternating_8th
                left  = [lanes[0], lanes[1]]
                right = [lanes[2], lanes[3]]
                for i, step in enumerate(range(0, 16, 2)):
                    side = left if i % 2 == 0 else right
                    l = random.choice(side)
                    m_data[l][step] = ns(l, step)
                    if random.random() < 0.25:
                        l2 = random.choice(side)
                        m_data[l2][step] = ns(l2, step)

        else:  # ADVANCED / ORDEAL
            pattern_types = [
                "stream_random", "stream_jump", "jacks",
                "trill_fast", "complex_stairs", "hand_stream",
                "ln_stream", "burst_rest", "chord_rush", "split_hands",
            ]
            pattern_type = random.choice(pattern_types)

            if pattern_type == "ln_stream" and not has_ln:
                pattern_type = random.choice(["stream_random", "jacks", "complex_stairs"])

            if pattern_type == "ln_stream":
                ln1 = random.randint(0, 1)
                ln2 = random.randint(2, 3)
                m_data[ln_lanes[ln1]][0]  = ns_idx(ln1, 0)
                m_data[ln_lanes[ln1]][8]  = ns_idx(ln1, 8)
                m_data[ln_lanes[ln2]][4]  = ns_idx(ln2, 4)
                m_data[ln_lanes[ln2]][12] = ns_idx(ln2, 12)
                avail = [lanes[i] for i in range(4) if i not in (ln1, ln2)]
                for step in range(0, 16, 2):
                    if m_data[ln_lanes[ln1]][step] == "00" and m_data[ln_lanes[ln2]][step] == "00":
                        l = random.choice(avail)
                        m_data[l][step] = ns(l, step)

            elif pattern_type == "stream_random":
                history = []
                for step in range(16):
                    avail = list(range(4))
                    if len(history) >= 1 and history[-1] in avail and random.random() < 0.7:
                        avail.remove(history[-1])
                    if len(history) >= 2 and history[-2] in avail and random.random() < 0.3:
                        avail.remove(history[-2])
                    chosen = random.choice(avail)
                    m_data[lanes[chosen]][step] = ns_idx(chosen, step)
                    history.append(chosen)

            elif pattern_type == "stream_jump":
                history = []
                for step in range(16):
                    avail = list(range(4))
                    if history and history[-1] in avail and random.random() < 0.6:
                        avail.remove(history[-1])
                    chosen = random.choice(avail)
                    m_data[lanes[chosen]][step] = ns_idx(chosen, step)
                    if step % 4 == 0:
                        others = [i for i in range(4) if i != chosen]
                        other = random.choice(others)
                        m_data[lanes[other]][step] = ns_idx(other, step)
                    history.append(chosen)

            elif pattern_type == "jacks":
                jack_lane = random.randint(0, 3)
                start = random.choice([0, 2, 4])
                length = random.randint(3, 6)
                for step in range(start, min(start + length, 16)):
                    m_data[lanes[jack_lane]][step] = ns_idx(jack_lane, step)
                for step in range(16):
                    if m_data[lanes[jack_lane]][step] == "00" and random.random() < 0.3:
                        others = [i for i in range(4) if i != jack_lane]
                        other = random.choice(others)
                        m_data[lanes[other]][step] = ns_idx(other, step)

            elif pattern_type == "trill_fast":
                pair = random.sample(range(4), 2)
                for step in range(16):
                    idx = pair[step % 2]
                    m_data[lanes[idx]][step] = ns_idx(idx, step)

            elif pattern_type == "complex_stairs":
                templates = [
                    [0,2,1,3,0,2,1,3], [3,1,2,0,3,1,2,0],
                    [0,3,1,2,3,0,2,1], [1,0,3,2,1,0,3,2],
                    [2,3,0,1,2,3,0,1], [3,0,2,1,0,3,1,2],
                    [1,3,0,2,3,1,0,2], [2,0,3,1,0,2,3,1],
                ]
                pts = random.choice(templates)
                offset = random.randint(0, 3)
                for i in range(8):
                    lane_idx = (pts[i] + offset) % 4
                    step = i * 2
                    m_data[lanes[lane_idx]][step] = ns_idx(lane_idx, step)

            elif pattern_type == "hand_stream":
                for step in range(16):
                    if step % 4 == 0:
                        chord = random.sample(range(4), 2)
                        for c in chord:
                            m_data[lanes[c]][step] = ns_idx(c, step)
                    elif step % 2 == 0:
                        c = random.randint(0, 3)
                        m_data[lanes[c]][step] = ns_idx(c, step)
                    else:
                        if random.random() < 0.6:
                            c = random.randint(0, 3)
                            m_data[lanes[c]][step] = ns_idx(c, step)

            elif pattern_type == "burst_rest":
                burst_len = random.randint(6, 10)
                start = random.randint(0, max(0, 16 - burst_len))
                end = min(start + burst_len, 16)
                history = []
                for step in range(start, end):
                    avail = list(range(4))
                    if history and history[-1] in avail and random.random() < 0.65:
                        avail.remove(history[-1])
                    chosen = random.choice(avail)
                    m_data[lanes[chosen]][step] = ns_idx(chosen, step)
                    history.append(chosen)

            elif pattern_type == "chord_rush":
                for step in range(0, 16, 2):
                    chord = random.sample(range(4), random.choice([1, 2, 2]))
                    for c in chord:
                        m_data[lanes[c]][step] = ns_idx(c, step)

            elif pattern_type == "split_hands":
                for step in range(0, 16, 2):
                    if (step // 2) % 2 == 0:
                        hand = [0, 1]
                    else:
                        hand = [2, 3]
                    picks = random.sample(hand, random.choice([1, 1, 2]))
                    for idx in picks:
                        m_data[lanes[idx]][step] = ns_idx(idx, step)

        # Write lines to chart
        all_channels = ["01", "08"] + lanes + ln_lanes
        for ch in all_channels:
            ch_data_str = "".join(m_data[ch])
            if any(x != "00" for x in m_data[ch]):
                chart_data += f"#{measure_str}{ch}:{ch_data_str}\n"

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(header + chart_data)

    return out_path, desc_str
