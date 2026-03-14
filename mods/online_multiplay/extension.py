"""
OnlineGameExtension
===================
Handles all online_multi-specific logic: dual lane layout, network-driven
opponent engine, score sync, and result/playing HUD.

Moves every ``if self.mode == 'online_multi'`` branch out of RhythmGame core.
"""

import time
import pygame
from pygame._sdl2.video import Texture  # type: ignore

from only4bms.game.game_extension import GameExtension
from only4bms.game.constants import NUM_LANES, JUDGMENT_ORDER, JUDGMENT_DEFS
from .i18n import t as _t


_AI_DT = 1.0 / 120.0  # 120 Hz opponent engine update


class OnlineGameExtension(GameExtension):
    """
    Attached to a RhythmGame(mode='online_multi') instance.
    Drives the opponent engine from network state and renders the dual-player HUD.
    """

    def __init__(self):
        self._update_timer = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def attach(self, game) -> None:
        super().attach(game)
        import only4bms.i18n as _i18n
        w, h = game.window.size
        sy = h / 600.0
        self._font_lg = _i18n.font("hud_bold", sy, bold=True)
        self._font_sm = _i18n.font("menu_small", sy)
        self._sy = sy
        self._sx_ratio = w / 800.0
        self._width = w
        self._height = h

    def on_attach_init(self, game) -> None:
        """Set up dual lane layout, network manager, opponent engine, and judgment state."""
        from only4bms.core.network_manager import NetworkManager
        from only4bms.game.engine import GameEngine

        w, h = game.width, game.height

        # Dual lane layout: P1 on left quarter, P2 on right quarter
        p1_start_x = w // 4 - game.lane_total_w // 2
        game.p1_lane_x = [p1_start_x + i * game.lane_w for i in range(NUM_LANES)]
        p2_start_x = (w * 3) // 4 - game.lane_total_w // 2
        game.p2_lane_x = [p2_start_x + i * game.lane_w for i in range(NUM_LANES)]
        game.lane_x = game.p1_lane_x

        # Network manager and opponent engine
        game.net = NetworkManager()
        game.ai_notes = [n.copy() for n in game.engine.notes]
        game.ai_engine = GameEngine(
            game.ai_notes, [], [], game.hw_mult,
            lambda s: None,
            lambda *args: None,
            game.engine.max_time,
            game.visual_timing_map,
            game.engine.last_note_time,
            lambda *args: None,
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
    # Per-note — send score update to server
    # ------------------------------------------------------------------

    def on_judgment(self, key: str, lane: int, t_ms: float) -> None:
        game = self._game
        game.net.send_score(game.judgments, game.combo)

    # ------------------------------------------------------------------
    # Per-frame — sync opponent state from server at 120 Hz
    # ------------------------------------------------------------------

    def on_tick(self, sim_time_ms: float) -> None:
        game = self._game
        t_now = time.perf_counter()
        if t_now - self._update_timer < _AI_DT:
            return
        self._update_timer = t_now

        game.ai_engine.update(sim_time_ms)
        opp = game.net.opponent_state
        if opp:
            game.ai_judgments = opp.get('judgments', game.ai_judgments)
            new_combo = opp.get('combo', game.ai_combo)
            if new_combo > game.ai_combo:
                game.ai_judgment_text = "HIT"
                game.ai_judgment_color = (0, 255, 255)
                game.ai_judgment_timer = sim_time_ms
            elif new_combo == 0 and game.ai_combo > 0:
                game.ai_judgment_text = "MISS"
                game.ai_judgment_color = (255, 0, 0)
                game.ai_judgment_timer = sim_time_ms
            game.ai_combo = new_combo
            game.ai_max_combo = max(game.ai_max_combo, game.ai_combo)
            game.net.opponent_state = None

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

    def draw_overlay(self, renderer, window, game_state: dict, phase: str) -> None:
        if phase != "result":
            return

        stats = game_state

        def _s(v): return max(1, int(v * self._sy))
        def _sx(v): return max(1, int(v * self._sx_ratio))

        def calc_score(judgs):
            if not judgs: return 0
            return judgs.get("PERFECT", 0) * 1000 + judgs.get("GREAT", 0) * 500 + judgs.get("GOOD", 0) * 200

        def calc_ex(judgs):
            if not judgs: return 0
            return judgs.get("PERFECT", 0) * 2 + judgs.get("GREAT", 0)

        max_ex = max(1, stats.get('total_notes', 1) * 2)
        score_h = calc_score(stats['judgments'])
        score_ai = calc_score(stats.get('ai_judgments') or {})
        ex_ai = calc_ex(stats.get('ai_judgments') or {})
        ratio_ai = min(1.0, ex_ai / max_ex)

        # Win/lose banner (replaces the base "RESULT" title)
        if score_h > score_ai:
            win_txt, win_color = _t("mp_you_win"), (0, 255, 255)
        elif score_h < score_ai:
            win_txt, win_color = _t("mp_you_lose"), (255, 50, 50)
        else:
            win_txt, win_color = _t("mp_draw"), (255, 255, 0)

        renderer.draw_color = (10, 10, 20, 255)
        renderer.fill_rect((0, 0, self._width, _s(80)))

        win_surf = self._font_lg.render(win_txt, True, win_color)
        win_tex = Texture.from_surface(renderer, win_surf)
        win_tex.alpha = 255
        renderer.blit(win_tex, pygame.Rect(
            self._width // 2 - win_tex.width // 2, _s(10),
            win_tex.width, win_tex.height))

        # Opponent stats panel (right side)
        p2_x = _sx(450)
        y = _s(100)

        title_surf = self._font_sm.render(_t("mp_opponent"), True, (255, 100, 100))
        title_tex = Texture.from_surface(renderer, title_surf)
        title_tex.alpha = 255
        renderer.blit(title_tex, pygame.Rect(p2_x, y - _s(40), title_tex.width, title_tex.height))

        opp_judgments = stats.get('ai_judgments') or {k: 0 for k in JUDGMENT_ORDER}
        for key in JUDGMENT_ORDER:
            color = JUDGMENT_DEFS[key]["color"]
            row = self._font_sm.render(f"{key:<10} {opp_judgments.get(key, 0):>4}", False, color)
            row_tex = Texture.from_surface(renderer, row)
            row_tex.alpha = 255
            renderer.blit(row_tex, pygame.Rect(p2_x, y, row_tex.width, row_tex.height))
            y += _s(32)

        y += _s(20)
        import only4bms.i18n as _i18n
        score_lbl = f"{_i18n.get('score_label').format(val=f'{score_ai:,}')}"
        sc_surf = self._font_lg.render(score_lbl, True, (255, 100, 100))
        sc_tex = Texture.from_surface(renderer, sc_surf)
        sc_tex.alpha = 255
        renderer.blit(sc_tex, pygame.Rect(p2_x, y, sc_tex.width, sc_tex.height))

        y += _s(40)
        ex_lbl = _i18n.get('ex_label').format(ex=ex_ai, max=max_ex, pct=f"{ratio_ai * 100:.1f}")
        ex_surf = self._font_sm.render(ex_lbl, False, (255, 200, 200))
        ex_tex = Texture.from_surface(renderer, ex_surf)
        ex_tex.alpha = 255
        renderer.blit(ex_tex, pygame.Rect(p2_x, y, ex_tex.width, ex_tex.height))

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
            'ai_paused': False,
            'ai_restarted': False,
        }
