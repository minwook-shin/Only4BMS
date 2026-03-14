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

_SYNC_TIMEOUT = 10.0   # seconds to wait for opponent to finish loading


def _sync_before_game(net, renderer, window, settings):
    """Exchange 'in-game ready' signals with the opponent.

    Both players call this after all assets are loaded (BMS parsed, keysounds
    decoded, RhythmGame constructed).  Notes don't scroll until both sides have
    confirmed readiness, eliminating the loading-time desync.

    The handshake uses the existing sync_score → opponent_score socket path so
    no server changes are required.

    Waits at most _SYNC_TIMEOUT seconds; if the opponent never responds the
    game starts anyway to avoid an indefinite hang.
    """
    import time
    import pygame
    from pygame._sdl2.video import Texture
    import only4bms.i18n as _i18n
    from .i18n import t as _t

    # Reset and signal
    net.opponent_in_game = False
    net.send_in_game_ready()

    w, h = window.size
    sy = h / 600.0
    font = _i18n.font("menu_option", sy)
    small_font = _i18n.font("menu_small", sy)

    screen = pygame.Surface((w, h))
    tex = None
    clock = pygame.time.Clock()
    deadline = time.time() + _SYNC_TIMEOUT

    while not net.opponent_in_game and time.time() < deadline:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return  # bail out; game loop will handle it

        rem = max(0.0, deadline - time.time())
        screen.fill((10, 10, 20))

        msg = font.render(_t("mp_loading_sync"), True, (0, 255, 200))
        screen.blit(msg, msg.get_rect(center=(w // 2, h // 2)))

        dots = "." * (int(time.time() * 2) % 4)
        sub = small_font.render(f"{rem:.0f}s{dots}", True, (100, 100, 120))
        screen.blit(sub, sub.get_rect(center=(w // 2, h // 2 + int(44 * sy))))

        if tex is None:
            tex = Texture.from_surface(renderer, screen)
        else:
            tex.update(screen)
        renderer.clear()
        renderer.blit(tex, pygame.Rect(0, 0, w, h))
        renderer.present()
        clock.tick(500)  # ~2ms polling so the waiting player exits quickly

    # Grace period: the player who was waiting exits this loop up to ~2ms after
    # the player who just finished loading.  Sleeping a fixed window ensures both
    # arrive at game.run() within ~2ms of each other rather than up to 33ms apart.
    import time as _time
    _time.sleep(0.15)


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

            net = NetworkManager()

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

            # ── Pre-game sync barrier ────────────────────────────────────
            # All assets (BMS, keysounds, textures) are loaded at this point.
            # Exchange a ready signal so both players enter game.run() at the
            # same moment, regardless of how long each took to load.
            _sync_before_game(net, renderer, window, settings)

            game.run()
            # Loop back to multiplayer menu (lobby re-entry)
