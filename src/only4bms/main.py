import sys
import pygame

from only4bms.bms_parser import BMSParser
from only4bms.rhythm_game import RhythmGame
from only4bms.settings_menu import SettingsMenu
from only4bms.song_select_menu import SongSelectMenu
from pygame._sdl2.video import Window, Renderer

# ── Default settings ─────────────────────────────────────────────────────
DEFAULT_SETTINGS = {
    "fps": 144,
    "speed": 1.0,
    "volume": 0.2,
    "hit_window_mult": 1.0,
    "fullscreen": 1,
    "audio_freq": 44100,
    "audio_buffer": 1024,
    "audio_channels": 2,
}

MIXER_CHANNELS = 256


# ── Audio helpers ─────────────────────────────────────────────────────────

def _detect_audio_devices():
    """Return list of output device names, or ['Default'] if detection fails."""
    try:
        import pygame._sdl2.audio as sdl2_audio
        devices = list(sdl2_audio.get_audio_device_names(False))
        return devices if devices else ["Default"]
    except Exception:
        return ["Default"]


def _init_mixer(settings):
    """(Re)initialize the mixer using current settings and selected device."""
    pygame.mixer.quit()
    pygame.mixer.pre_init(
        frequency=int(settings["audio_freq"]),
        size=-16,
        channels=int(settings["audio_channels"]),
        buffer=int(settings["audio_buffer"]),
    )
    devices = settings.get("audio_devices", ["Default"])
    dev_idx = settings.get("audio_device_idx", 0)

    try:
        if devices[0] != "Default":
            pygame.mixer.init(devicename=devices[dev_idx])
        else:
            pygame.mixer.init()
    except Exception as e:
        print(f"Warning: mixer init failed ({e}), using default")
        pygame.mixer.init()

    pygame.mixer.set_num_channels(MIXER_CHANNELS)


def apply_display_mode(settings, window):
    """Set fullscreen or windowed mode using SDL2 Window."""
    if settings.get("fullscreen", 1):
        # We use (0,0) for native resolution if possible, or just set fullscreen
        window.set_fullscreen(True)
    else:
        window.set_fullscreen(False)
        window.size = (800, 600)
    window.show()


# ── Entry point ──────────────────────────────────────────────────────────

def main():
    settings = dict(DEFAULT_SETTINGS)

    # Pre-init audio and pygame
    pygame.mixer.pre_init(
        frequency=int(settings["audio_freq"]),
        size=-16,
        channels=int(settings["audio_channels"]),
        buffer=int(settings["audio_buffer"]),
    )
    pygame.init()

    # Detect audio devices
    settings["audio_devices"] = _detect_audio_devices()
    settings["audio_device_idx"] = 0
    _init_mixer(settings)

    # Detect monitor refresh rate (pygame-ce feature)
    try:
        settings["fps"] = pygame.display.get_desktop_refresh_rates()[0]
    except Exception:
        settings["fps"] = 60

    # Create SDL2 Window and Renderer
    # Note: pygame.init() must be called first
    # Create SDL2 Window and Renderer
    # Set hint for linear scaling (smoothes out pixels when upscaling)
    try:
        pygame.set_hint("SDL_RENDER_SCALE_QUALITY", "linear")
    except AttributeError:
        # Fallback for older versions or environment issues
        import os
        os.environ["SDL_RENDER_SCALE_QUALITY"] = "linear"
    
    window = Window("Only4BMS", size=(800, 600))
    renderer = Renderer(window)
    renderer.draw_blend_mode = 1
    
    apply_display_mode(settings, window)

    # Main loop
    while True:
        action, selected_song = SongSelectMenu(settings, renderer=renderer, window=window).run()

        if action == "QUIT" or not action:
            break

        if action == "SETTINGS":
            SettingsMenu(settings, renderer=renderer, window=window).run() # Pass window
            continue

        if action == "PLAY" and selected_song:
            _init_mixer(settings)
            apply_display_mode(settings, window)
            _play_song(selected_song, settings, renderer=renderer, window=window)

    pygame.quit()
    sys.exit()


def _play_song(filepath, settings, renderer=None, window=None):
    """Parse a BMS file and launch the rhythm game."""
    print(f"Loading {filepath}...")
    parser = BMSParser(filepath)
    notes, bgms, bgas, bmp_map = parser.parse()

    if not notes and not bgms:
        print("No notes or bgm parsed from file.")
        return

    metadata = {
        "artist": parser.artist,
        "bpm": parser.bpm,
        "level": parser.playlevel,
        "genre": parser.genre,
        "notes": parser.total_notes,
        "stagefile": parser.stagefile,
        "banner": parser.banner,
    }
    game = RhythmGame(
        notes, bgms, bgas, parser.wav_map, bmp_map,
        parser.title, settings, metadata=metadata,
        renderer=renderer, window=window
    )
    game.start()


if __name__ == "__main__":
    main()
