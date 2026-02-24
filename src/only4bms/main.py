import json
import os
import sys
import pygame

from only4bms.core.bms_parser import BMSParser
from only4bms.game.rhythm_game import RhythmGame
from only4bms.ui.main_menu import MainMenu
from only4bms.ui.settings_menu import SettingsMenu
from only4bms.ui.song_select_menu import SongSelectMenu
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
    "judge_delay": 30.0,
    "note_type": 0,
    "ai_note_type": 0,
}

SETTINGS_FILE = "settings.json"

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


def load_settings():
    """Load settings from JSON, merging with defaults."""
    settings = dict(DEFAULT_SETTINGS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                saved = json.load(f)
                settings.update(saved)
        except Exception as e:
            print(f"Warning: Failed to load settings ({e})")
    return settings


def save_settings(settings):
    """Save current settings to JSON (excluding runtime-only keys)."""
    # Filter out keys starting with _ (internal/runtime)
    to_save = {k: v for k, v in settings.items() if not k.startswith("_")}
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(to_save, f, indent=4)
    except Exception as e:
        print(f"Error saving settings: {e}")


# ── Entry point ──────────────────────────────────────────────────────────

def main():
    settings = load_settings()

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
        menu_action = MainMenu(settings, renderer=renderer, window=window).run()

        if menu_action == "QUIT":
            break

        if menu_action == "SETTINGS":
            SettingsMenu(settings, renderer=renderer, window=window).run()
            save_settings(settings)
            continue

        if menu_action in ("SINGLE", "AI_MULTI"):
            mode = 'ai_multi' if menu_action == "AI_MULTI" else 'single'
            
            while True:
                action, selected_song, ai_difficulty = SongSelectMenu(settings, renderer=renderer, window=window, mode=mode).run()

                if action in ("QUIT", "MENU") or not action:
                    break

                if action == "SETTINGS":
                    SettingsMenu(settings, renderer=renderer, window=window).run()
                    save_settings(settings)
                    continue

                if action == "PLAY" and selected_song:
                    _init_mixer(settings)
                    apply_display_mode(settings, window)
                    # _play_song(selected_song, settings, mode=mode, renderer=renderer, window=window) # Original call
                    
                    # Inlined _play_song logic with new RhythmGame instantiation
                    print(f"Loading {selected_song}...")
                    parser = BMSParser(selected_song)
                    notes, bgms, bgas, bmp_map, visual_timing_map = parser.parse()

                    if not notes and not bgms:
                        print("No notes or bgm parsed from file.")
                        continue # Go back to song select

                    metadata = {
                        "artist": parser.artist,
                        "bpm": parser.bpm,
                        "level": parser.playlevel,
                        "genre": parser.genre,
                        "notes": parser.total_notes,
                        "stagefile": parser.stagefile,
                        "banner": parser.banner,
                        "total": parser.total,
                    }
                    game = RhythmGame(
                        notes, bgms, bgas, parser.wav_map, bmp_map,
                        parser.title, settings, visual_timing_map=visual_timing_map, mode=mode, metadata=metadata,
                        renderer=renderer, window=window,
                        ai_difficulty=ai_difficulty # New argument
                    )
                    game.run()


    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
