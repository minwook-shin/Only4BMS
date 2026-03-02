"""
CourseSession
=============
Encapsulates a single course-mode run:  stage loop → intermission → repeat.

Features:
  - HP bar that drains on MISSes and regenerates on PERFECTs.
  - FAIL if HP hits 0.
  - Per-stage Buff / Debuff system (first stage always gives bonus).
  - Audio waveform visualizer for the black-background loading/intermission screens.

Usage (from main.py):
    from only4bms.game.course_session import CourseSession
    CourseSession(settings, renderer, window, difficulty, duration_ms, paths).run()
"""

import os
import math
import random
import time

import pygame
from pygame._sdl2.video import Texture  # type: ignore

import only4bms.i18n as i18n
from only4bms.core.bms_parser import BMSParser
from only4bms.game.rhythm_game import RhythmGame


# ── Rank thresholds (EX-accuracy based) ─────────────────────────────────────
_RANK_THRESHOLDS = [
    (99, "SSS"), (97, "SS"), (94, "S"),
    (88, "A"),   (80, "B"),  (70, "C"),
    (60, "D"),
]

# ── HP constants ─────────────────────────────────────────────────────────────
HP_MAX          = 100.0
HP_MISS_DRAIN   = 8.0   # HP lost per MISS
HP_GOOD_DRAIN   = 2.0   # HP lost per GOOD
HP_GREAT_REGEN  = 0.5   # HP gained per GREAT
HP_PERFECT_REGEN = 1.0  # HP gained per PERFECT

# ── Modifier catalog ─────────────────────────────────────────────────────────
# Each entry: (key, is_buff, hp_mult, speed_mult, window_mult, description_key)
_MODIFIERS = [
    # ── Buffs ──
    ("mod_hp_boost",     True,  1.5,  1.0, 1.0, "buff_hp_boost"),
    ("mod_hp_regen",     True,  1.0,  1.0, 1.0, "buff_hp_regen"),
    ("mod_window_wide",  True,  1.0,  1.0, 1.2, "buff_window_wide"),
    ("mod_speed_slow",   True,  1.0,  0.8, 1.0, "buff_speed_slow"),
    # ── Debuffs ──
    ("mod_hp_fragile",   False, 1.0,  1.0, 1.0, "debuff_hp_fragile"),
    ("mod_window_tight", False, 1.0,  1.0, 0.8, "debuff_window_tight"),
    ("mod_speed_fast",   False, 1.0,  1.2, 1.0, "debuff_speed_fast"),
    ("mod_hp_drain",     False, 0.5,  1.0, 1.0, "debuff_hp_drain"),
    ("mod_perfectionist",False, 1.0,  1.0, 1.0, "debuff_perfectionist"),
]
_FIRST_STAGE_MOD = ("mod_hp_boost", True, 1.5, 1.0, 1.0, "buff_hp_boost")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _calc_score_and_rank(judgments: dict):
    """Return (score 0-1_000_000, rank str, acc float, ex int, max_ex int)."""
    total_j = sum(judgments.values())
    ex      = judgments.get("PERFECT", 0) * 2 + judgments.get("GREAT", 0)
    max_ex  = total_j * 2
    score   = int(ex / max_ex * 1_000_000) if max_ex > 0 else 0
    acc     = (ex / max_ex * 100) if max_ex > 0 else 0.0
    rank    = "F"
    for threshold, letter in _RANK_THRESHOLDS:
        if acc >= threshold:
            rank = letter
            break
    return score, rank, acc, ex, max_ex


def _pick_mods(stage_num: int, difficulty: str):
    """Return a list of random modifier tuples based on stage and difficulty."""
    if difficulty == "ORDEAL":
        # All debuffs EXCEPT mod_speed_fast
        return [m for m in _MODIFIERS if not m[1] and m[0] != "mod_speed_fast"]
        
    if stage_num == 1:
        return [_FIRST_STAGE_MOD]
    
    mods = []
    buffs = [m for m in _MODIFIERS if m[1]]
    debuffs = [m for m in _MODIFIERS if not m[1]]
    
    if difficulty == "BEGINNER":
        # Always 1-2 buffs, no debuffs
        mods.append(random.choice(buffs))
        if random.random() < 0.3: # 30% chance for a second buff
            m2 = random.choice(buffs)
            if m2 not in mods: mods.append(m2)
            
    elif difficulty == "INTERMEDIATE":
        # 40% buff, 40% debuff, 20% None
        r = random.random()
        if r < 0.40:
            mods.append(random.choice(buffs))
        elif r < 0.80:
            mods.append(random.choice(debuffs))
        
        # Chance for an extra random mod (buff or debuff)
        if random.random() < 0.25:
            extra = random.choice(_MODIFIERS)
            if extra not in mods: mods.append(extra)
            
    elif difficulty == "ADVANCED":
        # Always at least one debuff
        mods.append(random.choice(debuffs))
        # Always a second random debuff
        m2 = random.choice(debuffs)
        if m2 not in mods: mods.append(m2)
    
    return mods if mods else None


def _pick_note_mod() -> str:
    """45% Mirror, 15% Random, 40% None."""
    r = random.random()
    if r < 0.45: return "Mirror"
    if r < 0.60: return "Random"
    return "None"


def _mod_idx(mod: str) -> int:
    return {"Mirror": 1, "Random": 2}.get(mod, 0)


# ── HP delta from a stage's judgments ────────────────────────────────────────

def _calc_hp_delta(judgments: dict, modifiers: list) -> float:
    """Calculate net HP change.  modifiers may be a list of modifier tuples."""
    miss    = judgments.get("MISS", 0)
    good    = judgments.get("GOOD", 0)
    great   = judgments.get("GREAT", 0)
    perfect = judgments.get("PERFECT", 0)

    drain = miss * HP_MISS_DRAIN + good * HP_GOOD_DRAIN
    regen = great * HP_GREAT_REGEN + perfect * HP_PERFECT_REGEN

    # Modifier adjustments
    if modifiers:
        for modifier in modifiers:
            key = modifier[0]
            if key == "mod_hp_boost":
                regen *= 1.5
            elif key == "mod_hp_regen":
                regen *= 2.0
            elif key == "mod_hp_fragile":
                drain *= 2.0
            elif key == "mod_hp_drain":
                drain *= 1.5
                regen *= 0.5
            elif key == "mod_perfectionist":
                drain += judgments.get("GREAT", 0) * 1.5 + judgments.get("GOOD", 0) * 2.0 + judgments.get("MISS", 0) * 1.0

    return regen - drain


# ─────────────────────────────────────────────────────────────────────────────
# Waveform visualizer (for loading / intermission screens)
# ─────────────────────────────────────────────────────────────────────────────

class _WaveViz:
    """Draws a calm sine-wave animation on a pygame.Surface."""

    def __init__(self, w: int, h: int):
        self.w = w
        self.h = h
        # Multiple wave layers with different parameters
        self._layers = [
            dict(amp=h * 0.08, freq=2.0, speed=0.6,  phase=0.0, color=(0, 180, 255, 60)),
            dict(amp=h * 0.05, freq=3.5, speed=1.1,  phase=1.0, color=(0, 255, 180, 45)),
            dict(amp=h * 0.12, freq=1.2, speed=0.35, phase=2.5, color=(60, 120, 255, 30)),
        ]
        self._t = 0.0

    def update(self, dt: float):
        self._t += dt
        for L in self._layers:
            L["phase"] += L["speed"] * dt

    def draw(self, surf: pygame.Surface, cx: int, cy: int, half_w: int):
        """Draw waveform centred at (cx, cy) spanning ±half_w pixels."""
        for L in self._layers:
            pts = []
            steps = max(4, half_w // 2)
            for i in range(steps + 1):
                x = cx - half_w + i * (half_w * 2 // steps)
                angle = (i / steps) * L["freq"] * math.pi * 2 + L["phase"]
                y = int(cy + math.sin(angle) * L["amp"])
                pts.append((x, y))
            if len(pts) >= 2:
                pygame.draw.lines(surf, L["color"], False, pts, 2)


# ─────────────────────────────────────────────────────────────────────────────
# HP bar rendering helper
# ─────────────────────────────────────────────────────────────────────────────

def _draw_hp_bar(surf: pygame.Surface, x: int, y: int, w: int, h: int, ratio: float):
    """Draw a horizontal HP bar onto *surf*.  ratio ∈ [0, 1]."""
    # Background
    pygame.draw.rect(surf, (40, 10, 10, 200), (x, y, w, h), border_radius=4)
    # Fill
    fill_w = max(0, int(w * ratio))
    if fill_w:
        r = int(255 * (1.0 - ratio))
        g = int(200 * ratio)
        fill_col = (r, g, 40, 220)
        pygame.draw.rect(surf, fill_col, (x, y, fill_w, h), border_radius=4)
    # Border + glow
    border_col = (200, 80, 80, 180) if ratio < 0.25 else (80, 200, 120, 160)
    pygame.draw.rect(surf, border_col, (x, y, w, h), 2, border_radius=4)


# ─────────────────────────────────────────────────────────────────────────────
# CourseSession
# ─────────────────────────────────────────────────────────────────────────────

class CourseSession:
    """Runs the complete course mode session for a single difficulty/duration."""

    def __init__(self, settings, renderer, window, difficulty: str,
                 duration_ms: int, paths, init_mixer_fn=None):
        self.settings       = settings
        self.renderer       = renderer
        self.window         = window
        self.difficulty     = difficulty
        self.duration_ms    = duration_ms
        self._init_mixer    = init_mixer_fn or (lambda s: None)

        self.template_dir   = os.path.join(paths.DATA_PATH, ".temp_course")
        self.temp_bms_path  = os.path.join(self.template_dir, "temp_course.bms")
        os.makedirs(self.template_dir, exist_ok=True)

        # Progress state
        self.stage_num    = 0
        self.total_score  = 0
        self.best_score   = 0
        self.stage_scores: list[int] = []
        self.stage_ranks:  list[str] = []
        self.current_note_mod = "None"

        # HP
        self.hp           = HP_MAX
        self.hp_max       = HP_MAX

        # Current-stage modifier (tuple or None)
        self.current_modifier = None

        # Waveform visualizer
        W, H = window.size
        self._wave = _WaveViz(W, H)
        self._wave_last_t = time.perf_counter()

        # i18n motivation pool
        self._mot_pool = [
            i18n.get("course_mot_1"),
            i18n.get("course_mot_2"),
            i18n.get("course_mot_3"),
            i18n.get("course_mot_4"),
            i18n.get("course_mot_5"),
        ]

    # ── Public entry ─────────────────────────────────────────────────────────

    def run(self):
        from only4bms.game.course_generator import generate_random_course

        next_desc = ""
        is_first  = True
        # Modifier for the very first stage (always the HP boost bonus)
        next_modifier = _pick_mods(1, self.difficulty)

        while True:
            # 1. Generate (or re-use already-generated) BMS file
            if is_first:
                print(f"Course Mode - Generating procedural course ({self.difficulty})...")
                try:
                    _, next_desc = generate_random_course(
                        self.duration_ms, self.temp_bms_path,
                        self.template_dir, difficulty=self.difficulty)
                except Exception as e:
                    print(f"[CourseSession] Error generating course: {e}")
                    return
                is_first = False

            # 2. Apply modifier for this stage
            self.current_modifier = next_modifier
            self.stage_num += 1

            # 2a. Loading splash (shows incoming modifier)
            self._draw_loading(next_desc)

            # 3. Parse & play (with speed/window adjustments from modifier)
            try:
                parser = BMSParser(self.temp_bms_path)
                notes, bgms, bgas, bmp_map, visual_map, measures = parser.parse()
                if not notes and not bgms:
                    continue

                metadata = {
                    "artist": parser.artist, "bpm": parser.bpm,
                    "level": parser.playlevel, "genre": parser.genre,
                    "notes": len(notes), "stagefile": parser.stagefile,
                    "banner": parser.banner, "total": parser.total,
                }

                s = dict(self.settings)
                s["note_mod_idx"] = _mod_idx(self.current_note_mod)

                # Apply speed / hit-window multipliers from modifier
                if self.current_modifier:
                    for mod in self.current_modifier:
                        _, _, _, s_mult, w_mult, _ = mod
                        if s_mult != 1.0:
                            s["speed"] = s.get("speed", 1.0) * s_mult
                        if w_mult != 1.0:
                            s["hit_window_mult"] = s.get("hit_window_mult", 1.0) * w_mult

                self._init_mixer(s)
                game = RhythmGame(
                    notes, bgms, bgas, parser.wav_map, bmp_map,
                    parser.title, s,
                    visual_timing_map=visual_map, measures=measures, mode="single",
                    metadata=metadata,
                    renderer=self.renderer, window=self.window,
                    course_hp=self.hp, course_hp_max=self.hp_max,
                    course_modifier=self.current_modifier,
                )
                res = game.run()
                if isinstance(res, dict):
                    res = res.get("action", "QUIT")

            except Exception as e:
                print(f"[CourseSession] Error during stage: {e}")
                return

            if res == "QUIT":
                return

            # 4. Score + rank + HP update
            stage_score, stage_rank, acc, j_ex, j_max = _calc_score_and_rank(game.judgments)
            self.stage_scores.append(stage_score)
            self.stage_ranks.append(stage_rank)
            self.total_score += stage_score
            self.best_score   = max(self.best_score, stage_score)

            # Use the real-time HP updated in RhythmGame
            hp_before = self.hp
            self.hp   = game.course_hp
            hp_delta  = self.hp - hp_before

            # 5. FAIL check
            if self.hp <= 0:
                self._draw_fail_screen(self.stage_num, stage_score, stage_rank)
                return

            # 6. Prepare next stage (note mod + modifier + chart) before intermission
            next_note_mod = _pick_note_mod()
            self.current_note_mod = next_note_mod
            next_modifier = _pick_mods(self.stage_num + 1, self.difficulty)

            try:
                from only4bms.game.course_generator import generate_random_course
                _, next_desc = generate_random_course(
                    self.duration_ms, self.temp_bms_path,
                    self.template_dir, difficulty=self.difficulty)
            except Exception:
                pass

            # 7. Intermission screen
            if not self._intermission(
                stage_num=self.stage_num,
                stage_score=stage_score, stage_rank=stage_rank,
                acc=acc, judgments=game.judgments,
                hp_delta=hp_delta,
                next_desc=next_desc,
                next_note_mod=next_note_mod,
                next_modifier=next_modifier,
            ):
                return   # player chose to quit

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _wave_tick(self, surf: pygame.Surface):
        """Advance and draw the waveform onto surf."""
        now = time.perf_counter()
        dt  = now - self._wave_last_t
        self._wave_last_t = now
        self._wave.update(dt)
        W, H = surf.get_size()
        self._wave.draw(surf, W // 2, H // 2 + int(H * 0.08), W // 2 - 40)

    def _modifier_labels(self, modifiers: list) -> list[tuple[str, bool]]:
        """Return a list of (label, is_buff) for active modifiers."""
        if not modifiers:
            return [(i18n.get("course_no_modifier"), False)]
        
        results = []
        for mod in modifiers:
            key, is_buff, *_rest, desc_key = mod
            results.append((i18n.get(desc_key), is_buff))
        return results

    def _draw_loading(self, next_desc: str = ""):
        W, H = self.window.size
        sy = H / 600.0
        surf = pygame.Surface((W, H), pygame.SRCALPHA)
        surf.fill((10, 10, 20))

        self._wave_tick(surf)

        f1   = i18n.font("menu_title", sy, bold=True)
        f_sm = i18n.font("menu_small", sy)

        # Title
        t1 = f1.render(
            i18n.get("loading").format(status=i18n.get("status_gen_bms")),
            True, (0, 255, 200))
        surf.blit(t1, ((W - t1.get_width()) // 2, H // 2 - int(sy * 40)))

        # HP bar
        hp_ratio = self.hp / self.hp_max
        bar_w = int(W * 0.45)
        bar_h = int(sy * 18)
        bar_x = (W - bar_w) // 2
        bar_y = H // 2 + int(sy * 20)
        _draw_hp_bar(surf, bar_x, bar_y, bar_w, bar_h, hp_ratio)
        hp_lab = f_sm.render(f"HP  {int(self.hp)}/{int(self.hp_max)}", True, (200, 200, 200))
        surf.blit(hp_lab, (bar_x, bar_y - int(sy * 22)))

        # Modifier badges (plural)
        if self.stage_num > 0 and self.current_modifier:
            labels = self._modifier_labels(self.current_modifier)
            y_mb = bar_y + bar_h + int(sy * 12)
            for txt, is_buff in labels:
                col = (100, 255, 120) if is_buff else (255, 100, 100)
                if not self.current_modifier: col = (140, 140, 140)
                m_surf = f_sm.render(i18n.get("course_modifier_prefix") + txt, True, col)
                surf.blit(m_surf, ((W - m_surf.get_width()) // 2, y_mb))
                y_mb += sy * 24

        # Note mod
        if self.stage_num > 0:
            col = (180, 100, 255) if self.current_note_mod != "None" else (100, 120, 100)
            nm_text = i18n.get("course_note_mod_none") if self.current_note_mod == "None" else i18n.get("course_note_mod").format(mod=self.current_note_mod)
            tm  = f_sm.render(nm_text, True, col)
            surf.blit(tm, (20, 20))

        self.renderer.clear()
        tex = Texture.from_surface(self.renderer, surf)
        self.renderer.blit(tex, pygame.Rect(0, 0, W, H))
        self.renderer.present()

    def _intermission(self, *, stage_num, stage_score, stage_rank, acc,
                      judgments, hp_delta, next_desc, next_note_mod, next_modifier) -> bool:
        """Draw the between-stage result screen.  Returns True to continue, False to quit."""
        W, H   = self.window.size
        sy     = H / 600.0
        mot    = random.choice(self._mot_pool)
        hp_ratio = self.hp / self.hp_max

        running   = True
        continue_ = True

        while running:
            # ── Timing for waveform ─────────────────────────────────────────
            surf = pygame.Surface((W, H), pygame.SRCALPHA)
            surf.fill((15, 15, 25))

            self._wave_tick(surf)

            f_title = i18n.font("menu_title", sy, bold=True)
            f_body  = i18n.font("menu_option", sy * 0.9)
            f_sm    = i18n.font("menu_small", sy)
            f_xs    = i18n.font("menu_small", sy * 0.85)

            def blit_cx(surf_s, y):
                surf.blit(surf_s, ((W - surf_s.get_width()) // 2, int(y)))

            # STAGE N CLEAR [RANK]
            blit_cx(f_title.render(
                i18n.get("course_stage_clear").format(n=stage_num, rank=stage_rank),
                True, (0, 255, 200)), H * 0.09)

            # Score row
            blit_cx(f_body.render(
                i18n.get("course_stat_row").format(score=stage_score, total=self.total_score, best=self.best_score),
                True, (255, 230, 100)), H * 0.22)

            # Accuracy + judgments
            blit_cx(f_sm.render(
                i18n.get("course_acc_row").format(
                    acc=acc, p=judgments.get('PERFECT',0), g=judgments.get('GREAT',0), m=judgments.get('MISS',0)),
                True, (180, 220, 180)), H * 0.32)

            # ── HP bar ──────────────────────────────────────────────────────
            bar_w = int(W * 0.40)
            bar_h = int(sy * 16)
            bar_x = (W - bar_w) // 2
            bar_y = int(H * 0.405)
            # HP delta label
            if hp_delta >= 0:
                delta_str = f"HP  {int(self.hp)}/{int(self.hp_max)}  (+{hp_delta:.0f})"
                delta_col = (100, 255, 130)
            else:
                delta_str = f"HP  {int(self.hp)}/{int(self.hp_max)}  ({hp_delta:.0f})"
                delta_col = (255, 120, 80)
            hp_info = f_sm.render(delta_str, True, delta_col)
            surf.blit(hp_info, ((W - hp_info.get_width()) // 2, bar_y - int(sy * 22)))
            _draw_hp_bar(surf, bar_x, bar_y, bar_w, bar_h, hp_ratio)

            # Motivational quote
            blit_cx(f_body.render(mot, True, (255, 180, 80)), H * 0.50)

            # ── NEXT STAGE ──────────────────────────────────────────────────
            blit_cx(f_sm.render(i18n.get("course_next_stage_label"), True, (150, 150, 200)), H * 0.575)

            # Next desc (truncate to 88% width)
            desc = next_desc
            max_w = int(W * 0.88)
            while f_body.size(desc)[0] > max_w and len(desc) > 8:
                desc = desc[:-1]
            if desc != next_desc:
                desc += "..."
            blit_cx(f_body.render(desc, True, (200, 200, 255)), H * 0.635)

            # Next modifier banners (plural)
            next_labels = self._modifier_labels(next_modifier)
            y_nb = H * 0.70
            for label_txt, is_buff in next_labels:
                prefix = i18n.get("course_buff_prefix") if is_buff else i18n.get("course_debuff_prefix")
                if not next_modifier: prefix = ""
                banner_text = f"{prefix}  {label_txt}" if prefix else label_txt
                col = (100, 255, 150) if is_buff else (255, 130, 130)
                if not next_modifier: col = (120, 120, 130)
                blit_cx(f_sm.render(banner_text, True, col), y_nb)
                y_nb += sy * 24

            # Next note mod badge
            note_mod_col   = (200, 80, 255) if next_note_mod != "None" else (100, 140, 100)
            nm_label_val = next_note_mod.upper() if next_note_mod != "None" else i18n.get("none").upper()
            note_mod_label = i18n.get("course_note_mod").format(mod=nm_label_val)
            blit_cx(f_xs.render(note_mod_label, True, note_mod_col), H * 0.78)

            # Continue hint
            blit_cx(f_sm.render(i18n.get("course_continue_hint"), True, (120, 120, 130)), H * 0.90)

            # ── Present ─────────────────────────────────────────────────────
            self.renderer.clear()
            tex = Texture.from_surface(self.renderer, surf)
            self.renderer.blit(tex, pygame.Rect(0, 0, W, H))
            self.renderer.present()

            # ── Events ──────────────────────────────────────────────────────
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running    = False
                    continue_  = False
                elif e.type == pygame.KEYDOWN:
                    if e.key in (pygame.K_RETURN, pygame.K_SPACE):
                        running = False
                    elif e.key in (pygame.K_q, pygame.K_ESCAPE):
                        running   = False
                        continue_ = False
                elif e.type == pygame.JOYBUTTONDOWN:
                    if e.button == 0:
                        running = False
                    elif e.button == 1:
                        running   = False
                        continue_ = False

            time.sleep(0.016)  # ~60fps cap for intermission

        return continue_

    def _draw_fail_screen(self, stage_num: int, last_score: int, last_rank: str):
        """Show a FAIL / GAME OVER screen and wait for input."""
        W, H = self.window.size
        sy   = H / 600.0

        running = True
        while running:
            surf = pygame.Surface((W, H), pygame.SRCALPHA)
            surf.fill((20, 5, 5))

            self._wave_tick(surf)

            f_title = i18n.font("menu_title", sy, bold=True)
            f_body  = i18n.font("menu_option", sy)
            f_sm    = i18n.font("menu_small", sy)

            def blit_cx(s, y):
                surf.blit(s, ((W - s.get_width()) // 2, int(y)))

            blit_cx(f_title.render(i18n.get("course_fail"), True, (255, 50, 50)), H * 0.20)
            blit_cx(f_body.render(
                i18n.get("course_fail_stats").format(n=stage_num, total=self.total_score),
                True, (255, 200, 80)), H * 0.40)
            blit_cx(f_body.render(
                i18n.get("course_last_stage_info").format(score=last_score, rank=last_rank),
                True, (200, 180, 255)), H * 0.52)
            blit_cx(f_sm.render(i18n.get("course_fail_hint"), True, (120, 120, 130)), H * 0.80)

            self.renderer.clear()
            tex = Texture.from_surface(self.renderer, surf)
            self.renderer.blit(tex, pygame.Rect(0, 0, W, H))
            self.renderer.present()

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN:
                    if e.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE):
                        running = False
                elif e.type == pygame.JOYBUTTONDOWN:
                    running = False

            time.sleep(0.016)
