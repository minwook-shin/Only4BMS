"""
GameExtension — Mod hook interface for RhythmGame
===================================================
Mods that need in-game integration (HUD overlays, network sync, custom fail
conditions, etc.) subclass :class:`GameExtension` and pass an instance to
``RhythmGame(extension=...)``.

All methods have default no-op implementations so subclasses only override
what they need.

Public attributes available via ``self._game`` after :meth:`attach`:
  _game.renderer, _game.window         — SDL2 renderer / window
  _game.width, _game.height            — window size in pixels
  _game.judgments                      — dict of current judgment counts
  _game.combo, _game.max_combo         — combo tracking
  _game.mode                           — 'single' | 'ai_multi' | 'online_multi'
  _game.state                          — 'PLAYING' | 'PAUSED' | 'RESULT'
  _game.ai_judgments, _game.ai_engine  — opponent data (set by on_attach_init)
"""


class GameExtension:
    """Base class for mod extensions attached to a RhythmGame session."""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def attach(self, game) -> None:
        """Called once at the end of ``RhythmGame.__init__``.
        Store a reference to the game so callbacks can read game state.
        """
        self._game = game

    def on_attach_init(self, game) -> None:
        """Called immediately after :meth:`attach`.

        Override to set up mode-specific game state: dual lane layouts,
        opponent engines, judgment dicts, network connections, etc.
        Anything that needs to live on the ``game`` object and depends on the
        extension being present should be initialised here rather than in
        ``RhythmGame.__init__``.
        """

    # ------------------------------------------------------------------
    # Per-note hooks
    # ------------------------------------------------------------------

    def on_judgment(self, key: str, lane: int, t_ms: float) -> None:
        """Called after each note judgment.

        Parameters
        ----------
        key   : 'PERFECT' | 'GREAT' | 'GOOD' | 'MISS'
        lane  : 0-based lane index, or -1 for LN-release judgments
        t_ms  : song-relative time in milliseconds
        """

    # ------------------------------------------------------------------
    # Per-frame hooks
    # ------------------------------------------------------------------

    def on_tick(self, sim_time_ms: float) -> None:
        """Called once per render frame while state == 'PLAYING'.
        Use this for network polling, AI updates, time-based effects, etc.
        """

    def should_abort(self) -> bool:
        """Return True to immediately end the current song (transitions to
        RESULT).  Use this to implement fail-on-HP-zero, etc.
        """
        return False

    # ------------------------------------------------------------------
    # Input event hooks
    # ------------------------------------------------------------------

    def on_pause(self) -> None:
        """Called when the player pauses the game (ESC / TAB).
        Use this to record that the player paused for challenge tracking, etc.
        """

    def on_restart(self) -> None:
        """Called when the player requests a quick restart (R key),
        before ``needs_restart`` is set on the game.
        Use this to run challenge checks, record restart state, etc.
        """

    # ------------------------------------------------------------------
    # Rendering hooks (called around the base game render)
    # ------------------------------------------------------------------

    def draw_background(self, renderer, window) -> None:
        """Draw behind the BGA / notes.
        Called after ``renderer.clear()`` but before ``draw_bga()``.
        Use this for animated backgrounds when no BGA is present.
        """

    def get_opponent_ln_effects(self, game, frame_count: int) -> list:
        """Return a list of effect dicts to append for the opponent's held LNs.

        Each dict follows the same schema as entries in ``game.effects``::

            {'lane': int, 'radius': int, 'color': tuple, 'alpha': int,
             'note_type': int}

        ``lane`` should be offset by ``NUM_LANES`` so the effect renders on
        the opponent side.  Default: empty list (no opponent LN effects).
        """
        return []

    def get_all_lanes(self, game) -> list:
        """Return the full lane-position list used when drawing hit effects.

        For single-player this is just ``game.lane_x``.  Dual-player
        extensions should return ``game.p1_lane_x + game.p2_lane_x`` so
        that effects on the opponent side are positioned correctly.
        """
        return game.lane_x

    def get_p1_lane_x(self, game) -> list:
        """Return the lane_x list to use for the P1 draw state.

        Default returns ``game.lane_x`` (centred, single-player).
        Dual-player extensions should return ``game.p1_lane_x``.
        """
        return game.lane_x

    def get_p1_draw_extras(self, game) -> dict:
        """Return extra key/value pairs to merge into the P1 draw-state dict.

        Dual-player extensions use this to inject ``ai_judgments`` and
        ``ai_hit_history`` so the renderer can display the opponent's score
        alongside the player's.  Default: empty dict.
        """
        return {}

    def draw_mid_hud(self, renderer, window, t: float, game,
                     p1_ratio: float, max_ex: int,
                     gy: int, gw: int, gh: int, ga: int) -> None:
        """Draw the performance gauge(s) and any opponent panel.

        Called from ``RhythmGame._draw()`` after P1 effects have been
        rendered.  The default implementation draws a single-player EX-ratio
        gauge to the left of the player's lane column.

        Dual-player extensions override this to draw the P1 gauge in the
        correct position, render the opponent's note field, and draw a second
        gauge for the opponent.

        Parameters
        ----------
        renderer  : SDL2 renderer
        window    : SDL2 window
        t         : current song time in ms (visual, with offset applied)
        game      : the RhythmGame instance
        p1_ratio  : player EX ratio in [0, 1]
        max_ex    : maximum possible EX score
        gy, gw, gh: gauge top-y, width, height in screen pixels
        ga        : gauge alpha (0-255, fades after last note)
        """
        gx = game.lane_x[0] - gw - game.game_renderer._sx(10)
        game.game_renderer.draw_vertical_gauge(gx, gy, gw, gh, p1_ratio, (0, 255, 255), ga)

    def draw_overlay(self, renderer, window, game_state: dict, phase: str) -> None:
        """Draw on top of the game frame, before ``renderer.present()``.

        Parameters
        ----------
        renderer   : pygame._sdl2.video.Renderer
        window     : pygame._sdl2.video.Window
        game_state : ``_get_draw_state('p1', t)`` dict while playing,
                     or ``get_stats()`` dict during result phase
        phase      : 'playing' | 'paused' | 'result'
        """

    # ------------------------------------------------------------------
    # Stats contribution
    # ------------------------------------------------------------------

    def get_extra_stats(self) -> dict:
        """Extra key/value pairs merged into ``RhythmGame.get_stats()``
        before the dict is returned to callers (e.g. challenge checks).

        Common keys:  'failed' (bool), 'hp' (float), 'must_win' (bool),
                      'ai_accuracy' (float), 'ai_paused' (bool),
                      'ai_restarted' (bool)
        """
        return {}
