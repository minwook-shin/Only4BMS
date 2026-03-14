"""
Online Multiplay Mod for Only4BMS
===================================
Real-time 1 vs 1 online multiplayer via Socket.IO.

The host selects a song and match settings (speed, modifiers, buffs/debuffs).
Guests download the song from the server and join the lobby.
Both players play simultaneously; live score is synced over the network.

Requires a running Only4BMS multiplayer server.
See MULTIPLAYER_API.md for the server specification.

All UI/lobby code is self-contained in this mod package:
  multiplayer_menu.py — lobby, song select, match settings, download screens

Host APIs used (from only4bms):
  only4bms.core.bms_parser.BMSParser
  only4bms.core.network_manager.NetworkManager  (singleton, also used by RhythmGame)
  only4bms.game.rhythm_game.RhythmGame
  only4bms.i18n
  only4bms.paths
"""

MOD_ID = "online_multiplay"
MOD_NAME = "Online Multiplay"
MOD_DESCRIPTION = "1 vs 1 real-time multiplayer. Connect to a server and battle."
MOD_VERSION = "1.0.0"


def get_display_name() -> str:
    from .i18n import t as _t
    return _t("menu_online_multi")


def run(settings, renderer, window, **ctx):
    """
    Entry point called by main.py when the player selects 'Online Multiplay'.

    Parameters
    ----------
    settings : dict
        Shared settings dict.
    renderer : pygame._sdl2.video.Renderer
        The SDL2 renderer shared across all scenes.
    window : pygame._sdl2.video.Window
        The SDL2 window.
    **ctx : dict
        Optional context injected by the host:
          - init_mixer_fn  : callable(settings) — reinitialise pygame mixer
          - challenge_manager : ChallengeManager instance
    """
    from .multiplayer_menu import MultiplayerMenu
    from .extension import OnlineGameExtension
    from only4bms.core.network_manager import NetworkManager
    from only4bms.core.bms_parser import BMSParser
    from only4bms.game.rhythm_game import RhythmGame

    init_mixer_fn = ctx.get("init_mixer_fn")
    challenge_manager = ctx.get("challenge_manager")

    while True:
        mp_menu = MultiplayerMenu(settings, renderer=renderer, window=window)
        action, selected_song = mp_menu.run()

        if action in ("QUIT", "MENU") or not action:
            break

        if action == "START_MULTI" and selected_song:
            # Reset ready flag so next round starts cleanly
            NetworkManager()._ready_sent = False

            if init_mixer_fn:
                init_mixer_fn(settings)

            print(f"Loading {selected_song}...")
            parser = BMSParser(selected_song)
            notes, bgms, bgas, bmp_map, visual_timing_map, measures = parser.parse()

            if not notes and not bgms:
                print("No notes or bgm parsed from file.")
                break

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

            match_settings = NetworkManager().match_settings or {}
            match_settings_obj = settings.copy()

            if "speed" in match_settings:
                match_settings_obj["speed"] = float(match_settings["speed"])

            p1_modifiers = set(match_settings.get("modifiers", []))

            game = RhythmGame(
                notes, bgms, bgas, parser.wav_map, bmp_map,
                parser.title, match_settings_obj,
                visual_timing_map=visual_timing_map,
                measures=measures,
                mode="online_multi",
                metadata=metadata,
                renderer=renderer,
                window=window,
                ai_difficulty="normal",
                note_mod="None",
                challenge_manager=challenge_manager,
                p1_modifiers=p1_modifiers,
                extension=OnlineGameExtension(),
            )
            game.run()
            # Loop back to multiplayer menu (lobby re-entry)
