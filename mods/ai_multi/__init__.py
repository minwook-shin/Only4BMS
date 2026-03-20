"""
AI Multi Mod for Only4BMS
==========================
Local 1 vs 1 battle against a PPO-trained AI opponent.

AI models live in this directory so users can inspect and swap them freely:
  model_normal.zip  — relaxed timing (30 ms jitter), mostly GREAT/PERFECT
  model_hard.zip    — near-perfect timing (2 ms jitter), very high accuracy

To replace a model, overwrite the corresponding .zip with a new
stable_baselines3 PPO model trained on RhythmEnv (see src/only4bms/ai/).

All song selection, BMS parsing, and game loop logic is self-contained here.
"""

MOD_ID          = "ai_multi"
MOD_NAME        = "AI Battle"
MOD_DESCRIPTION = "1 vs 1 battle against a local AI opponent."
MOD_VERSION     = "1.0.0"


def get_display_name() -> str:
    from only4bms.i18n import get as _t
    return _t("menu_ai_multi")


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

    while True:
        ssm = SongSelectMenu(
            settings, renderer=renderer, window=window,
            mode='ai_multi', song_groups=cached_songs,
        )
        res = ssm.run()
        cached_songs = ssm.song_groups

        if challenge_manager and cached_songs:
            total_songs = sum(len(g.get('charts', [])) for g in cached_songs)
            challenge_manager.check_challenges({'mode': 'scan_complete', 'total_songs': total_songs})

        action, selected_song, ai_difficulty, note_mod = res

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
                    ai_difficulty=ai_difficulty,
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
