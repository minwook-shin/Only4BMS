import os
import random
import wave
import numpy as np

import only4bms.i18n as i18n

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
        # Mix of high-pitched short pulse and noise for a keyboard "clack"
        noise = np.random.uniform(-1, 1, len(t)) * 0.5
        pulse = np.sin(2 * np.pi * freq * t) * 0.5
        audio = noise + pulse
    else:
        audio = np.sin(2 * np.pi * freq * t)

    if wave_type in ('kick', 'clack'):
        envelope = np.exp(-t * (30 if wave_type == 'kick' else 80))
    elif wave_type == 'noise':
        envelope = np.exp(-t * 20)
    else:
        # Synth envelope
        envelope = np.exp(-t * 3)
        
    audio = audio * envelope * volume
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

    # Force regeneration of key_tap if we want to hear the new sound
    tap_path = os.path.join(template_dir, "key_tap.wav")
    if os.path.exists(tap_path):
        try: os.remove(tap_path)
        except: pass

    # Generate procedural WAV assets if they don't exist
    _generate_wav(os.path.join(template_dir, "kick_soft.wav"), 80, 0.5, 'kick', volume=0.4)
    _generate_wav(os.path.join(template_dir, "snare_soft.wav"), 400, 0.3, 'noise', volume=0.15)
    _generate_wav(os.path.join(template_dir, "hat_soft.wav"), 800, 0.1, 'noise', volume=0.08)
    
    # Improved keyboard-like clack (sharper attack, lower volume)
    _generate_wav(tap_path, 2500, 0.05, 'clack', volume=0.12)

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
    wavs = [
        ("01", "kick_soft.wav"),
        ("02", "snare_soft.wav"),
        ("03", "hat_soft.wav"),
        ("10", "key_tap.wav"),
    ]
    
    for wid, wname in wavs:
        header += f"#WAV{wid} {wname}\n"
    header += "\n"

    ms_per_measure = (240.0 / bpm) * 1000.0
    num_measures = int(duration_ms / ms_per_measure) + 1
    
    chart_data = ""
    # Unified universal tap sound for all difficulties (cleaner audio feedback)
    synths = ["10"]
    lanes = ["11", "12", "13", "14"] # 4-Key bounds in standard mapping
    ln_lanes = ["51", "52", "53", "54"] # 4-Key bounds for LN

    def get_empty_measure():
        d = {l: ["00"] * 16 for l in lanes}
        d.update({ln: ["00"] * 16 for ln in ln_lanes})
        d["08"] = ["00"] * 16 # For BPM changes
        d["01"] = ["00"] * 16 # For BGM kick
        return d

    for m in range(num_measures + 2):
        measure_str = f"{m:03d}"
        m_data = get_empty_measure()
        
        if m < 2:
            # 2 measures of empty space for countdown break
            chart_data += f"#{measure_str}01:00\n" # dummy bgm tick
            continue
            
        m_data["01"][0] = "01"
        m_data["01"][4] = "02"
        m_data["01"][8] = "01"
        m_data["01"][12] = "02"
        
        # Inject BPM variations (Ultra-Smooth transition with ±15% caps)
        if has_sv and m > 2:
            # Shift frequency by difficulty
            freq = 4 if difficulty == "INTERMEDIATE" else 2
            if m % freq == 0:
                is_speed_up = random.random() < 0.5
                if is_speed_up:
                    # Ultra-Smooth Ramp Up: 8 steps spread across the measure
                    m_data["08"][0] = "21"
                    m_data["08"][2] = "22"
                    m_data["08"][4] = "24"
                    m_data["08"][6] = "26"
                    m_data["08"][8] = "28" # Max (1.15x)
                    # Gentle return to normal
                    m_data["08"][12] = "24"
                    m_data["08"][14] = "21"
                else:
                    # Ultra-Smooth Ramp Down: 8 steps spread across the measure
                    m_data["08"][0] = "11"
                    m_data["08"][2] = "12"
                    m_data["08"][4] = "14"
                    m_data["08"][6] = "16"
                    m_data["08"][8] = "18" # Max (0.85x)
                    # Gentle return to normal
                    m_data["08"][12] = "14"
                    m_data["08"][14] = "11"
            else:
                # Reset to normal BPM at the start of non-SV measures
                # This must be at pos=0.0 to ensure 예고 line color resets
                m_data["08"][0] = "00"
        
        if difficulty == "BEGINNER":
            # True Novice: 1 active lane, sparsely placed 4th notes
            active = random.choice(lanes)
            rhythm_type = random.choice(["4th", "sparse"])
            if rhythm_type == "4th":
                for step in [0, 4, 8, 12]:
                    m_data[active][step] = random.choice(synths)
            else: # sparse
                m_data[active][random.choice([0, 8])] = random.choice(synths)

        elif difficulty == "INTERMEDIATE":
            # Intermediate: 8th-note density, no sparse beginner patterns
            pattern_type = random.choice([
                "chords_8th", "trill_8th", "stairs_8th",
                "jack_8th", "combo_fill", "ln_dense", "alternating_8th"
            ])
            # ln_dense fallback when LN not enabled
            if pattern_type == "ln_dense" and not has_ln:
                pattern_type = "alternating_8th"

            if pattern_type == "ln_dense":
                # LN holding one lane + dense 8th fill on others
                ln_idx = random.randint(0, 3)
                m_data[ln_lanes[ln_idx]][0]  = random.choice(synths)
                m_data[ln_lanes[ln_idx]][14] = random.choice(synths)
                avail = [lanes[i] for i in range(4) if i != ln_idx]
                for step in range(0, 16, 2):
                    if random.random() < 0.7:
                        m_data[random.choice(avail)][step] = random.choice(synths)

            elif pattern_type == "chords_8th":
                # Singles / 2-note chords every 8th note
                for step in range(0, 16, 2):
                    chord = random.sample(lanes, random.choice([1, 1, 2]))
                    for l in chord: m_data[l][step] = random.choice(synths)

            elif pattern_type == "trill_8th":
                # Fast 8th-note trill between 2 lanes
                tl = random.sample(lanes, 2)
                for i, step in enumerate(range(0, 16, 2)):
                    m_data[tl[i % 2]][step] = random.choice(synths)

            elif pattern_type == "stairs_8th":
                # Non-sequential 8-step pattern — rejects 3+ consecutive ascending/descending
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
                    m_data[lanes[seq[i]]][i * 2] = random.choice(synths)

            elif pattern_type == "jack_8th":
                # One lane plays every 8th; another lane fills occasionally
                jack = random.choice(lanes)
                fill = random.choice([l for l in lanes if l != jack])
                for step in range(0, 16, 2):
                    m_data[jack][step] = random.choice(synths)
                    if step % 4 == 0 and random.random() < 0.4:
                        m_data[fill][step] = random.choice(synths)

            elif pattern_type == "combo_fill":
                # First half: cross pattern (non-sequential), second half: chords
                cross = random.choice([[0,2,1,3], [3,1,2,0], [1,3,0,2], [2,0,3,1]])
                for i, step in enumerate(range(0, 8, 2)):
                    m_data[lanes[cross[i]]][step] = random.choice(synths)
                for step in range(8, 16, 2):
                    chord = random.sample(lanes, random.choice([1, 2]))
                    for l in chord: m_data[l][step] = random.choice(synths)

            else:  # alternating_8th
                # Left pair / right pair alternating every 8th note
                left  = [lanes[0], lanes[1]]
                right = [lanes[2], lanes[3]]
                for i, step in enumerate(range(0, 16, 2)):
                    side = left if i % 2 == 0 else right
                    m_data[random.choice(side)][step] = random.choice(synths)
                    if random.random() < 0.25:  # occasional double
                        m_data[random.choice(side)][step] = random.choice(synths)


        else:  # ADVANCED
            # 10 distinct pattern types, weighted away from repetition
            pattern_types = [
                "stream_random",       # true random 16ths
                "stream_jump",         # 16ths with chord jumps
                "jacks",               # same-lane repeats
                "trill_fast",          # rapid 2-lane trill
                "complex_stairs",      # non-linear stair
                "hand_stream",         # chord + 16th mix
                "ln_stream",           # LN + stream
                "burst_rest",          # dense burst then rest
                "chord_rush",          # all-chord measure
                "split_hands",         # left/right hand alternating patterns
            ]
            pattern_type = random.choice(pattern_types)
            
            # If LN disabled, skip LN pattern
            if pattern_type == "ln_stream" and not has_ln:
                pattern_type = random.choice(["stream_random", "jacks", "complex_stairs"])

            if pattern_type == "ln_stream":
                ln1 = random.randint(0, 1)
                ln2 = random.randint(2, 3)
                m_data[ln_lanes[ln1]][0] = random.choice(synths)
                m_data[ln_lanes[ln1]][8] = random.choice(synths)
                m_data[ln_lanes[ln2]][4] = random.choice(synths)
                m_data[ln_lanes[ln2]][12] = random.choice(synths)
                avail = [lanes[i] for i in range(4) if i not in (ln1, ln2)]
                for step in range(0, 16, 2):
                    if m_data[ln_lanes[ln1]][step] == "00" and m_data[ln_lanes[ln2]][step] == "00":
                        m_data[random.choice(avail)][step] = random.choice(synths)

            elif pattern_type == "stream_random":
                # True random: pick any lane per step, but weight AWAY from last 2
                history = []
                for step in range(16):
                    avail = list(range(4))
                    # Remove last lane from candidates most of the time
                    if len(history) >= 1 and history[-1] in avail and random.random() < 0.7:
                        avail.remove(history[-1])
                    # Also remove 2nd-to-last sometimes (prevent back-n-forth)
                    if len(history) >= 2 and history[-2] in avail and random.random() < 0.3:
                        avail.remove(history[-2])
                    chosen = random.choice(avail)
                    m_data[lanes[chosen]][step] = random.choice(synths)
                    history.append(chosen)

            elif pattern_type == "stream_jump":
                # 16th stream but every 4 steps add a chord
                history = []
                for step in range(16):
                    avail = list(range(4))
                    if history and history[-1] in avail and random.random() < 0.6:
                        avail.remove(history[-1])
                    chosen = random.choice(avail)
                    m_data[lanes[chosen]][step] = random.choice(synths)
                    if step % 4 == 0:  # Add chord partner
                        others = [i for i in range(4) if i != chosen]
                        m_data[lanes[random.choice(others)]][step] = random.choice(synths)
                    history.append(chosen)

            elif pattern_type == "jacks":
                # 3-8 consecutive hits on same lane, fill rest randomly
                jack_lane = random.randint(0, 3)
                start = random.choice([0, 2, 4])
                length = random.randint(3, 6)
                for step in range(start, min(start + length, 16)):
                    m_data[lanes[jack_lane]][step] = random.choice(synths)
                # Fill some other steps
                for step in range(16):
                    if m_data[lanes[jack_lane]][step] == "00" and random.random() < 0.3:
                        others = [lanes[i] for i in range(4) if i != jack_lane]
                        m_data[random.choice(others)][step] = random.choice(synths)

            elif pattern_type == "trill_fast":
                # super-fast 2-lane 16th trill, randomly pick the pair
                pair = random.sample(range(4), 2)
                for step in range(16):
                    m_data[lanes[pair[step % 2]]][step] = random.choice(synths)

            elif pattern_type == "complex_stairs":
                # Generate 8 unique non-linear stair patterns
                templates = [
                    [0,2,1,3,0,2,1,3],
                    [3,1,2,0,3,1,2,0],
                    [0,3,1,2,3,0,2,1],
                    [1,0,3,2,1,0,3,2],
                    [2,3,0,1,2,3,0,1],
                    [3,0,2,1,0,3,1,2],
                    [1,3,0,2,3,1,0,2],
                    [2,0,3,1,0,2,3,1],
                ]
                pts = random.choice(templates)
                # Random start offset to further vary
                offset = random.randint(0, 3)
                for i in range(8):
                    lane_idx = (pts[i] + offset) % 4
                    step = i * 2
                    m_data[lanes[lane_idx]][step] = random.choice(synths)

            elif pattern_type == "hand_stream":
                # 8th-note chords on beat positions, 16th singles on off-positions
                for step in range(16):
                    if step % 4 == 0:  # On beat: 2-note chord
                        chord = random.sample(lanes, 2)
                        for c in chord: m_data[c][step] = random.choice(synths)
                    elif step % 2 == 0:  # Off-beat 8th: single note
                        m_data[random.choice(lanes)][step] = random.choice(synths)
                    else:  # 16th: occasional single
                        if random.random() < 0.6:
                            m_data[random.choice(lanes)][step] = random.choice(synths)

            elif pattern_type == "burst_rest":
                # Dense burst of 6-10 notes, rest of measure empty
                burst_len = random.randint(6, 10)
                start = random.randint(0, max(0, 16 - burst_len))
                end = min(start + burst_len, 16)  # clamp
                history = []
                for step in range(start, end):
                    avail = list(range(4))
                    if history and history[-1] in avail and random.random() < 0.65:
                        avail.remove(history[-1])
                    chosen = random.choice(avail)
                    m_data[lanes[chosen]][step] = random.choice(synths)
                    history.append(chosen)

            elif pattern_type == "chord_rush":
                # Every other step throws 2-note chords
                for step in range(0, 16, 2):
                    chord = random.sample(lanes, random.choice([1, 2, 2]))
                    for c in chord: m_data[c][step] = random.choice(synths)

            elif pattern_type == "split_hands":
                # Left hand (lanes 0,1) alternates with right hand (lanes 2,3) each 8th note
                left = [lanes[0], lanes[1]]
                right = [lanes[2], lanes[3]]
                for step in range(0, 16, 2):
                    hand = left if (step // 2) % 2 == 0 else right
                    # Optionally double up
                    picks = random.sample(hand, random.choice([1, 1, 2]))
                    for l in picks: m_data[l][step] = random.choice(synths)


        # Write lines to chart
        all_channels = ["01", "08"] + lanes + ln_lanes
        for ch in all_channels:
            ch_data_str = "".join(m_data[ch])
            if any(x != "00" for x in m_data[ch]):
                chart_data += f"#{measure_str}{ch}:{ch_data_str}\n"
    
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(header + chart_data)
    
    return out_path, desc_str
