"""
AI Multi Mod for Only4BMS
==========================
Local 1 vs 1 battle against a PPO-trained AI opponent.

AI models live in this directory so users can inspect and swap them freely:
  model_normal.zip  — relaxed timing (30 ms jitter), mostly GREAT/PERFECT
  model_hard.zip    — near-perfect timing (2 ms jitter), very high accuracy

To replace a model, overwrite the corresponding .zip with a new
stable_baselines3 PPO model trained on RhythmEnv (see mods/ai_multi/train.py).

All song selection, BMS parsing, and game loop logic is self-contained here.
"""

MOD_ID          = "ai_multi"
MOD_NAME        = "AI Battle"
MOD_DESCRIPTION = "1 vs 1 battle against a local AI opponent."
MOD_VERSION     = "1.0.0"

_AI_MULTI_CHALLENGES = [
    {"id": "multi_win", "condition": {"must_win": True, "mode": "ai_multi"}},
    {"id": "you_are_already_dead", "condition": {"mode": "ai_multi", "ai_difficulty": "hard"}},
    {"id": "vibe_coding", "condition": {"mode": "ai_multi", "max_accuracy": 49.9, "ai_min_accuracy": 99.0, "must_clear": False}},
    {"id": "ai_needs_time", "condition": {"mode": "ai_multi", "ai_paused": True, "must_clear": False}},
    {"id": "ai_wants_retry", "condition": {"mode": "ai_multi", "ai_restarted": True, "must_clear": False}},
]


def get_display_name() -> str:
    from .i18n import t as _t
    return _t("menu_ai_multi")


def setup(ctx: dict) -> None:
    """Register ai_multi challenges and i18n strings into the host."""
    from .i18n import _STRINGS
    import only4bms.i18n as _host_i18n

    # Register all strings for every language defined in this mod
    for lang, strings in _STRINGS.items():
        _host_i18n.register_strings(lang, strings)

    # Register challenge definitions
    cm = ctx.get("challenge_manager")
    if cm:
        cm.register_challenges(_AI_MULTI_CHALLENGES)


def run(settings, renderer, window, **ctx):
    """
    Entry point called by main.py when the player selects 'AI Battle'.

    Parameters
    ----------
    settings : dict
        Shared settings dict (may be mutated by in-mod settings menu).
    renderer : pygame._sdl2.video.Renderer
        The SDL2 renderer shared across all scenes.
    window : pygame._sdl2.video.Window
        The SDL2 window.
    **ctx : dict
        Optional context injected by the host:
          - init_mixer_fn      : callable(settings) — reinitialise pygame mixer
          - save_settings_fn   : callable(settings) — persist settings to disk
          - challenge_manager  : ChallengeManager instance
    """
    from .extension import AiMultiExtension
    from only4bms.core.bms_parser import BMSParser
    from only4bms.game.rhythm_game import RhythmGame
    from only4bms.ui.song_select_menu import SongSelectMenu
    from only4bms.ui.settings_menu import SettingsMenu

    init_mixer_fn     = ctx.get("init_mixer_fn")
    save_settings_fn  = ctx.get("save_settings_fn")
    challenge_manager = ctx.get("challenge_manager")

    cached_songs = None  # First entry scans; re-entries reuse cache
    _ai_difficulties = ['normal', 'hard']
    _diff_idx = [settings.get('ai_diff_idx', 0)]  # list so closures can mutate

    def _ai_diff_label():
        from .i18n import t as _t
        val = _ai_difficulties[_diff_idx[0] % len(_ai_difficulties)]
        return f"{_t('ai_diff_label')}: {val.upper()}"

    def _ai_diff_toggle():
        _diff_idx[0] = (_diff_idx[0] + 1) % len(_ai_difficulties)
        settings['ai_diff_idx'] = _diff_idx[0]
        if save_settings_fn:
            save_settings_fn(settings)

    def _ai_note_label():
        from .i18n import t as _t
        val = "CIRCLE" if settings.get('ai_note_type', 0) == 1 else "BAR"
        return f"{_t('ai_note')}: {val}"

    def _ai_note_toggle():
        settings['ai_note_type'] = 1 if settings.get('ai_note_type', 0) == 0 else 0
        if save_settings_fn:
            save_settings_fn(settings)

    _extra_opts = [
        {'label_fn': _ai_note_label, 'action': 'AI_NOTE_TYPE', 'on_click': _ai_note_toggle},
    ]
    _extra_nav = [
        {'label_fn': _ai_diff_label, 'action': 'AI_DIFF', 'on_click': _ai_diff_toggle},
    ]

    while True:
        ssm = SongSelectMenu(
            settings, renderer=renderer, window=window,
            song_groups=cached_songs,
            extra_opts=_extra_opts,
            extra_nav_buttons=_extra_nav,
        )
        res = ssm.run()
        cached_songs = ssm.song_groups

        if challenge_manager and cached_songs:
            total_songs = sum(len(g.get('charts', [])) for g in cached_songs)
            challenge_manager.check_challenges({'mode': 'scan_complete', 'total_songs': total_songs})

        action, selected_song, note_mod = res
        ai_difficulty = _ai_difficulties[_diff_idx[0] % len(_ai_difficulties)]

        if action in ("QUIT", "MENU") or not action:
            break

        if action == "SETTINGS":
            SettingsMenu(settings, renderer=renderer, window=window).run()
            if save_settings_fn:
                save_settings_fn(settings)
            continue

        if action == "PLAY" and selected_song:
            if init_mixer_fn:
                init_mixer_fn(settings)

            print(f"Loading {selected_song}...")
            parser = BMSParser(selected_song)
            notes, bgms, bgas, bmp_map, visual_timing_map, measures = parser.parse()

            if not notes and not bgms:
                print("No notes or bgm parsed from file.")
                continue

            metadata = {
                "artist": parser.artist,
                "bpm": parser.bpm,
                "level": parser.playlevel,
                "genre": parser.genre,
                "notes": parser.total_notes,
                "stagefile": parser.stagefile,
                "banner": parser.banner,
                "total": parser.total,
                "lanes_compressed": parser.lanes_compressed,
            }

            while True:
                game = RhythmGame(
                    notes, bgms, bgas, parser.wav_map, bmp_map,
                    parser.title, settings,
                    visual_timing_map=visual_timing_map,
                    measures=measures,
                    mode='ai_multi',
                    metadata=metadata,
                    renderer=renderer,
                    window=window,
                    note_mod=note_mod,
                    challenge_manager=challenge_manager,
                    extension=AiMultiExtension(ai_difficulty),
                )
                result = game.run()
                if isinstance(result, dict) and result.get('newly_completed'):
                    print(f"Newly completed challenges: {[c['id'] for c in result['newly_completed']]}")
                if result.get('action') != "RESTART":
                    break
                if init_mixer_fn:
                    init_mixer_fn(settings)
