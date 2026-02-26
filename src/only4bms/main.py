import json
import os
import sys
import pygame
import time

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
    "audio_buffer": 128,
    "audio_channels": 2,
    "judge_delay": 10.0,
    "note_type": 0,
    "ai_note_type": 0,
    "input_polling_rate": 1000,
    "visual_offset": 0,
    "keys": [pygame.K_d, pygame.K_f, pygame.K_j, pygame.K_k],
    "joystick_keys": ["HAT_0_LEFT", "HAT_0_UP", "BTN_3", "BTN_1"], # D-pad Left/Up + Button Y/B
}

SETTINGS_FILE = "settings.json"

MIXER_CHANNELS = 256

_JOYSTICKS = [] # Prevent garbage collection
_REFRESHING_JOYSTICKS = False

def refresh_joysticks(force_reset=False):
    """Update the list of connected joysticks. force_reset=True will cycle the subsystem."""
    global _JOYSTICKS, _REFRESHING_JOYSTICKS
    if _REFRESHING_JOYSTICKS:
        return len(_JOYSTICKS)
    
    _REFRESHING_JOYSTICKS = True
    try:
        if force_reset:
            if pygame.joystick.get_init():
                pygame.joystick.quit()
        
        if not pygame.joystick.get_init():
            pygame.joystick.init()
            _JOYSTICKS.clear() # Subsystem reset means all old objects are dead
        
        count = pygame.joystick.get_count()
        new_joysticks = []
        
        for i in range(count):
            try:
                j = pygame.joystick.Joystick(i)
                iid = j.get_instance_id()
                
                # Try to find a matching existing object that is still healthy
                found = None
                for existing in _JOYSTICKS:
                    try:
                        if existing.get_init() and existing.get_instance_id() == iid:
                            found = existing
                            break
                    except Exception:
                        continue
                
                if found:
                    new_joysticks.append(found)
                else:
                    # New joystick or object was dead
                    # j.init() is deprecated in pygame-ce as Joystick(i) auto-inits
                    # Ping to ensure OS/XInput state is active
                    try:
                        j.get_button(0)
                        j.get_hat(0)
                    except Exception:
                        pass
                    new_joysticks.append(j)
            except Exception:
                continue
                
        _JOYSTICKS = new_joysticks
        return len(_JOYSTICKS)
    finally:
        _REFRESHING_JOYSTICKS = False


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
                
                # Migration: if joystick_keys contains integers, reset to new string-based defaults
                if "joystick_keys" in saved and any(isinstance(k, int) for k in saved["joystick_keys"]):
                    print("Migrating legacy joystick settings...")
                    saved["joystick_keys"] = DEFAULT_SETTINGS["joystick_keys"]
                
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
    # Set hints for maximum performance
    hints = {
        "SDL_RENDER_SCALE_QUALITY": "linear",
        "SDL_RENDER_BATCHING": "1",
        "SDL_AUDIO_RESAMPLING_MODE": "fast",
        "SDL_VIDEO_DOUBLE_BUFFER": "1",
        "SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS": "1",
        "SDL_XINPUT_ENABLED": "1"
    }
    
    for hint, value in hints.items():
        try:
            pygame.set_hint(hint, value)
        except AttributeError:
            import os
            # Fallback for older pygame/SDL versions
            env_key = hint if hint.startswith("SDL_") else f"SDL_HINT_{hint}"
            os.environ[env_key] = value
    
    window = Window("Only4BMS", size=(800, 600))
    renderer = Renderer(window, vsync=1)
    renderer.draw_blend_mode = 1
    
    apply_display_mode(settings, window)

    # Initialize Joysticks
    # Forced reset and multiple pumps at startup to stabilize pre-plugged devices
    pygame.event.pump()
    refresh_joysticks(force_reset=True)
    
    # Wait a bit and pump again to let SDL/OS catch up
    for _ in range(10):
        pygame.event.pump()
        time.sleep(0.02)
    refresh_joysticks()

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
                res = SongSelectMenu(settings, renderer=renderer, window=window, mode=mode).run()
                action, selected_song, ai_difficulty, note_mod = res

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
                    while True:
                        game = RhythmGame(
                            notes, bgms, bgas, parser.wav_map, bmp_map,
                            parser.title, settings, visual_timing_map=visual_timing_map, mode=mode, metadata=metadata,
                            renderer=renderer, window=window,
                            ai_difficulty=ai_difficulty, note_mod=note_mod
                        )
                        result = game.run()
                        if result != "RESTART":
                            break
                        # Restarting involves re-initializing mixer if needed or just re-running
                        _init_mixer(settings)


    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
