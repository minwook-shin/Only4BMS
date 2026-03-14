"""
AiMultiExtension
================
Handles all ai_multi-specific logic: dual lane layout, AI engine,
AI judgment tracking, AI inference update loop, and dual-player HUD.

Moves every ``if self.mode == 'ai_multi'`` branch out of RhythmGame core.
"""

import time
import numpy as np

from .game_extension import GameExtension
from .constants import NUM_LANES, JUDGMENT_ORDER, JUDGMENT_DEFS
from only4bms.i18n import get as _t


_AI_DT = 1.0 / 120.0  # 120 Hz AI update


class AiMultiExtension(GameExtension):
    """
    Attached to a RhythmGame(mode='ai_multi') instance.
    Drives the local AI opponent and owns all dual-player rendering.
    """

    def __init__(self, ai_difficulty: str = 'normal'):
        self._difficulty = ai_difficulty
        self._paused = False
        self._restarted = False
        self._update_timer = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_attach_init(self, game) -> None:
        """Set up dual lane layout, AI model, AI engine, and judgment state."""
        from only4bms.ai.inference import RhythmInference
        from .engine import GameEngine

        w, h = game.width, game.height

        # Dual lane layout: P1 on left quarter, P2 on right quarter
        p1_start_x = w // 4 - game.lane_total_w // 2
        game.p1_lane_x = [p1_start_x + i * game.lane_w for i in range(NUM_LANES)]
        p2_start_x = (w * 3) // 4 - game.lane_total_w // 2
        game.p2_lane_x = [p2_start_x + i * game.lane_w for i in range(NUM_LANES)]
        game.lane_x = game.p1_lane_x

        # AI model (drives the opponent)
        self._ai_model = RhythmInference(self._difficulty)

        # AI engine (mirrors P1's chart; runs on the same notes, different engine)
        game.ai_notes = [n.copy() for n in game.engine.notes]
        game.ai_engine = GameEngine(
            game.ai_notes, [], [], game.hw_mult,
            lambda s: None,
            self._set_ai_judgment,
            game.engine.max_time,
            game.visual_timing_map,
            game.engine.last_note_time,
            self._on_ai_ln_tick,
        )
        game.ai_lane_pressed = [False] * NUM_LANES

        # Opponent judgment / display state
        game.ai_judgments = {k: 0 for k in JUDGMENT_ORDER}
        game.ai_combo = 0
        game.ai_max_combo = 0
        game.ai_judgment_text = ""
        game.ai_judgment_key = ""
        game.ai_judgment_timer = 0
        game.ai_combo_timer = 0
        game.ai_judgment_color = (255, 255, 255)
        game.ai_hit_history = []

    # ------------------------------------------------------------------
    # Input event hooks
    # ------------------------------------------------------------------

    def on_pause(self) -> None:
        self._paused = True

    def on_restart(self) -> None:
        self._restarted = True
        game = self._game
        if game.challenge_manager and not game._challenge_checked:
            game.challenge_manager.check_challenges(game.get_stats())
            game._challenge_checked = True

    # ------------------------------------------------------------------
    # Per-frame — AI inference at 120 Hz
    # ------------------------------------------------------------------

    def on_tick(self, sim_time_ms: float) -> None:
        t_now = time.perf_counter()
        if t_now - self._update_timer < _AI_DT:
            return
        self._update_timer = t_now
        self._update_ai(sim_time_ms)

    def _update_ai(self, current_time: float) -> None:
        game = self._game
        game.ai_engine.update(current_time)

        ai_jitter = 30.0 if self._difficulty == 'normal' else 2.0

        for lane in range(NUM_LANES):
            obs = game.ai_engine.get_observation(
                current_time, lane,
                jitter=ai_jitter,
                is_pressed=game.ai_lane_pressed[lane],
            )
            act = self._ai_model.predict(obs, deterministic=True)
            pressed = bool(int(act) if np.isscalar(act) else int(act.item()))
            if pressed:
                game.ai_engine.process_hit(lane, current_time)
            game.ai_lane_pressed[lane] = pressed

        game.ai_engine.update(current_time, game.ai_lane_pressed)

    # ------------------------------------------------------------------
    # AI judgment callbacks (passed to ai_engine as callbacks)
    # ------------------------------------------------------------------

    def _set_ai_judgment(self, key, lane, t=None, timing_diff=0) -> None:
        game = self._game
        if t is None:
            t = (time.perf_counter() - game.start_time) * 1000.0
        j = JUDGMENT_DEFS[key]
        _I18N = {
            "PERFECT": "judgment_perfect", "GREAT": "judgment_great",
            "GOOD": "judgment_good", "MISS": "judgment_miss",
        }
        game.ai_judgment_text = _t(_I18N.get(key, key))
        game.ai_judgment_key = key
        game.ai_judgment_color = j["color"]
        game.ai_judgment_timer = t
        if key != "MISS":
            game.ai_hit_history.append((t, timing_diff, key))
            game.effects.append({
                'lane': lane + NUM_LANES,
                'radius': 22,
                'color': j["color"],
                'alpha': 160,
                'note_type': game.ai_note_type,
            })
        else:
            game.ai_hit_history.append((t, 0, "MISS"))
        game.ai_judgments[key] += 1
        if key == "MISS":
            game.ai_combo = 0
        else:
            game.ai_combo += 1
            game.ai_max_combo = max(game.ai_max_combo, game.ai_combo)
            game.ai_combo_timer = t

    def _on_ai_ln_tick(self, t=None) -> None:
        game = self._game
        if t is None:
            t = (time.perf_counter() - game.start_time) * 1000.0
        game.ai_combo += 1
        game.ai_max_combo = max(game.ai_max_combo, game.ai_combo)
        game.ai_combo_timer = t
        game.ai_judgment_timer = t

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------

    def get_opponent_ln_effects(self, game, frame_count: int) -> list:
        if frame_count % 8 != 0:
            return []
        effects = []
        for lane, note in enumerate(game.ai_engine.held_lns):
            if note:
                effects.append({
                    'lane': lane + NUM_LANES,
                    'radius': 22,
                    'color': (0, 255, 255),
                    'alpha': 160,
                    'note_type': game.ai_note_type,
                })
        return effects

    def get_all_lanes(self, game) -> list:
        return game.p1_lane_x + game.p2_lane_x

    def get_p1_lane_x(self, game) -> list:
        return game.p1_lane_x

    def get_p1_draw_extras(self, game) -> dict:
        return {
            'ai_judgments': game.ai_judgments,
            'ai_hit_history': game.ai_hit_history,
        }

    def draw_mid_hud(self, renderer, window, t: float, game,
                     p1_ratio: float, max_ex: int,
                     gy: int, gw: int, gh: int, ga: int) -> None:
        gr = game.game_renderer

        # P1 gauge — right of P1 lanes
        gx_p1 = game.p1_lane_x[-1] + game.lane_w + gr._sx(5)
        gr.draw_vertical_gauge(gx_p1, gy, gw, gh, p1_ratio, (0, 255, 255), ga)

        # Opponent note field
        ai_state = game._get_draw_state('ai', t)
        gr.draw_playing(t, ai_state)
        gr.draw_score_bar(game.judgments, game.ai_judgments)

        # Opponent gauge — left of P2 lanes
        ai_ex = game.ai_judgments["PERFECT"] * 2 + game.ai_judgments["GREAT"]
        ai_ratio = min(1.0, ai_ex / max_ex)
        gx_ai = game.p2_lane_x[0] - gw - gr._sx(5)
        gr.draw_vertical_gauge(gx_ai, gy, gw, gh, ai_ratio, (255, 80, 80), ga)

    # ------------------------------------------------------------------
    # Stats contribution
    # ------------------------------------------------------------------

    def get_extra_stats(self) -> dict:
        game = self._game
        max_ex = max(1, game.total_judgments * 2)
        p1_ex = game.judgments.get("PERFECT", 0) * 2 + game.judgments.get("GREAT", 0)
        ai_ex = game.ai_judgments.get("PERFECT", 0) * 2 + game.ai_judgments.get("GREAT", 0)
        return {
            'ai_accuracy': (ai_ex / max_ex) * 100.0,
            'must_win': p1_ex > ai_ex,
            'failed': False,
            'ai_paused': self._paused,
            'ai_restarted': self._restarted,
        }
