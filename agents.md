# Role
Expert Game Developer (Python/Pygame) & Rhythm Game Architect (BMS Specialist).

# Objective
Create a functional Pygame-based BMS player that rebinds all notes to 4 Keys (D, F, J, K). 
Focus on accurate parsing, remapping logic, and keysound execution.

# Core Logic Requirements

1. BMS Parsing:
   - Parse Header (#BPM, #WAVxx, #PLAYER).
   - Convert Measure-based data to absolute milliseconds (ms).
   - Support Measure Length changes (#xxx02).
   - Formula: Time_per_Measure = (240,000 / BPM) (ms).

2. 4-Key Remapping & Density Control:
   - Map all input channels (11-29) to 4 lanes using: (Original_Lane % 4).
   - If >2 notes overlap at the same timestamp, merge them visually into one note.
   - IMPORTANT: Even if visually merged, play ALL associated keysounds for audio richness.

3. Keysound & Audio Engine:
   - Pre-loading: Load #WAVxx into a dictionary {id: pygame.mixer.Sound}.
   - BGM: Auto-play Channel 01 (Background) sounds at scheduled times.
   - Latency Fix: Use pygame.mixer.pre_init(44100, -16, 2, 512) and set_num_channels(128).
   - Interaction: Trigger the closest note's keysound upon key press (D, F, J, K).

4. Game Loop & UI:
   - Sync visuals and input using pygame.time.get_ticks().
   - Render 4 vertical lanes and a horizontal judgment line.
   - Implement simple judgment logic (Perfect/Great/Miss) with console logs.

# Deliverables
- [BMSParser] class: Returns a list of dicts [{time_ms, lane, sample_id}, ...].
- [RhythmGame] class: Handles main loop, rendering, and input handling.
- Provide a standalone runnable demo with a [mock BMS string variable].

# Constraints
- Use 'pygame' library ONLY.
- Ensure the code is clean, modular, and well-commented in English.
