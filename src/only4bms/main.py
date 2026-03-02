import pygame  # Must be first — prevents macOS dylib conflicts with numpy/BLAS
import json
import os
import sys
import time
from only4bms import paths, i18n
from only4bms.game.challenge import ChallengeManager

# ── Early Initialization ──────────────────────────────────────────────────
# On macOS, complex libraries like OpenCV (cv2) or Torch can shadow DLLs 
# needed by pygame-ce (like libintl). We load settings and init the mixer 
# FIRST, before any other project-level imports.
def _early_load_settings():
    try:
        if os.path.exists(paths.SETTINGS_FILE):
            with open(paths.SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except: pass
    return {}

_early_cfg = _early_load_settings()

if sys.platform == "win32":
    os.environ["SDL_AUDIODRIVER"] = "wasapi"

pygame.mixer.pre_init(
    frequency=int(_early_cfg.get("audio_freq", 44100)),
    size=-16,
    channels=int(_early_cfg.get("audio_channels", 2)),
    buffer=int(_early_cfg.get("audio_buffer", 128)),
)
pygame.init() # Initialize core modules early

# Performance & Stability Tuning (Post-Init)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE" # Prevent OpenMP runtime conflict
import torch
torch.set_num_threads(1) # Minimize threading overhead/conflicts

# Now safe to import project modules
from only4bms.core.bms_parser import BMSParser
from only4bms.game.rhythm_game import RhythmGame
from only4bms.ui.main_menu import MainMenu
from only4bms.ui.settings_menu import SettingsMenu
from only4bms.ui.song_select_menu import SongSelectMenu
from only4bms import i18n
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
    "judge_delay": 0.0,
    "note_type": 0,
    "ai_note_type": 0,
    "input_polling_rate": 1000,
    "visual_offset": 0,
    "language": "auto",
    "keys": [pygame.K_d, pygame.K_f, pygame.K_j, pygame.K_k],
    "joystick_keys": ["HAT_0_LEFT", "HAT_0_UP", "BTN_3", "BTN_1"], # D-pad Left/Up + Button Y/B
}


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
        window.set_fullscreen(True)
    else:
        window.set_fullscreen(False)
        window.set_windowed()
        window.size = (800, 600)
        window.position = pygame.WINDOWPOS_CENTERED
    window.show()

def _create_mock_bms(song_dir):
    """Creates a dummy BMS file for first-time users."""
    mock_bms_content = """#PLAYER 1
#GENRE TUTORIAL
#TITLE Welcome to Only4BMS!
#ARTIST Only4BMS Team
#BPM 120
#PLAYLEVEL 1
#LNTYPE 1
#00111:0101010101010101
#00112:0101010101010101
#00113:0101010101010101
#00114:0101010101010101
#WAV01 silence.wav
#WAV02 clap.wav
#00101:01
#00201:02
#00301:01
#00401:02
"""
    mock_bms_path = os.path.join(song_dir, "welcome.bms")
    mock_wav_path1 = os.path.join(song_dir, "silence.wav")
    mock_wav_path2 = os.path.join(song_dir, "clap.wav")

    try:
        with open(mock_bms_path, "w", encoding="shift_jis") as f: # BMS files often use shift_jis
            f.write(mock_bms_content)
        # Create dummy wav files (empty files are fine for this purpose)
        with open(mock_wav_path1, "w") as f: pass
        with open(mock_wav_path2, "w") as f: pass
        print(f"Created dummy BMS: {mock_bms_path}")
    except Exception as e:
        print(f"Error creating dummy BMS: {e}")


def load_settings():
    """Load settings from JSON, merging with defaults."""
    settings = dict(DEFAULT_SETTINGS)
    if os.path.exists(paths.SETTINGS_FILE):
        try:
            with open(paths.SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                
                # Migration: if joystick_keys contains integers, reset to new string-based defaults
                if "joystick_keys" in saved and any(isinstance(k, int) for k in saved["joystick_keys"]):
                    print("Migrating legacy joystick settings...")
                    saved["joystick_keys"] = DEFAULT_SETTINGS["joystick_keys"]
                
                # Migration: if note_type is string "Bar" or "Circle", convert to 0 or 1
                if "note_type" in saved and isinstance(saved["note_type"], str):
                    saved["note_type"] = 1 if saved["note_type"] == "Circle" else 0
                if "ai_note_type" in saved and isinstance(saved["ai_note_type"], str):
                    saved["ai_note_type"] = 1 if saved["ai_note_type"] == "Circle" else 0
                
                settings.update(saved)
        except Exception as e:
            print(f"Warning: Failed to load settings ({e})")
    
    return settings


def save_settings(settings):
    """Save current settings to JSON (excluding runtime-only keys)."""
    # Filter out keys starting with _ (internal/runtime)
    to_save = {k: v for k, v in settings.items() if not k.startswith("_")}
    # Convert language index to language code for persistence
    if "language" in to_save and isinstance(to_save["language"], int):
        from only4bms.i18n import LANGUAGE_CODES
        idx = to_save["language"]
        to_save["language"] = LANGUAGE_CODES[idx] if 0 <= idx < len(LANGUAGE_CODES) else "en"
    
    try:
        # Final safety: confirm directory exists before writing
        target_dir = os.path.dirname(paths.SETTINGS_FILE)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        with open(paths.SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(to_save, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving settings: {e}")


# ── Entry point ──────────────────────────────────────────────────────────

def main():
    settings = load_settings()
    
    # Create bms directory if not exists
    song_dir = paths.SONG_DIR
    if not os.path.exists(song_dir):
        try:
            os.makedirs(song_dir)
            # Create a dummy BMS for first-run
            _create_mock_bms(song_dir)
        except Exception as e:
            print(f"Error creating bms directory at {song_dir}: {e}")
            # Final fallback to a guaranteed writable local path
            song_dir = "bms" 
            try:
                if not os.path.exists(song_dir): os.makedirs(song_dir)
            except: pass

    print(f"Scanning song directory: {os.path.abspath(song_dir)}")

    # Initialize i18n from settings
    i18n.set_language(settings.get("language", "auto"))

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
            # Fallback for older pygame/SDL versions
            env_key = hint if hint.startswith("SDL_") else f"SDL_HINT_{hint}"
            os.environ[env_key] = value
    
    window = Window("Only4BMS", size=(800, 600), hidden=True)
    _vsync = settings.get("vsync", 0)
    renderer = Renderer(window, vsync=_vsync)  # Custom VSync setting (0 or 1)
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

    # Initialize Challenge Manager
    challenge_manager = ChallengeManager()

    # Main loop
    while True:
        menu_action = MainMenu(settings, renderer=renderer, window=window).run()

        if menu_action == "QUIT":
            break

        if menu_action == "SETTINGS":
            SettingsMenu(settings, renderer=renderer, window=window).run()
            save_settings(settings)
            continue
        
        if menu_action == "CHALLENGE":
            from only4bms.ui.challenge_menu import ChallengeMenu
            ChallengeMenu(settings, renderer=renderer, window=window).run()
            continue

        if menu_action == "COURSE":
            from only4bms.ui.course_menu import CourseMenu
            course_res = CourseMenu(settings, renderer=renderer, window=window).run()
            if course_res and course_res[0] == "START":
                difficulty, duration_ms = course_res[1], course_res[2]
                from only4bms.game.course_session import CourseSession
                CourseSession(
                    settings, renderer, window,
                    difficulty, duration_ms, paths,
                    init_mixer_fn=_init_mixer,
                    challenge_manager=challenge_manager,
                ).run()
            continue

        if menu_action in ("SINGLE", "AI_MULTI"):
            mode = 'ai_multi' if menu_action == "AI_MULTI" else 'single'
            cached_songs = None  # First entry scans; re-entries reuse cache
            
            while True:
                ssm = SongSelectMenu(settings, renderer=renderer, window=window, mode=mode, song_groups=cached_songs)
                res = ssm.run()
                cached_songs = ssm.song_groups  # Cache for next iteration
                
                # Check for "scan_complete" challenge (e.g., BMS folder discovery)
                if challenge_manager and cached_songs:
                    total_songs = sum(len(g.get('charts', [])) for g in cached_songs)
                    challenge_manager.check_challenges({'mode': 'scan_complete', 'total_songs': total_songs})
                
                action, selected_song, ai_difficulty, note_mod = res

                if action in ("QUIT", "MENU") or not action:
                    break

                if action == "SETTINGS":
                    SettingsMenu(settings, renderer=renderer, window=window).run()
                    save_settings(settings)
                    continue

                if action == "PLAY" and selected_song:
                    _init_mixer(settings)
                    # _play_song(selected_song, settings, mode=mode, renderer=renderer, window=window) # Original call
                    
                    # Inlined _play_song logic with new RhythmGame instantiation
                    print(f"Loading {selected_song}...")
                    parser = BMSParser(selected_song)
                    notes, bgms, bgas, bmp_map, visual_timing_map, measures = parser.parse()

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
                        "lanes_compressed": parser.lanes_compressed,
                    }
                    while True:
                        game = RhythmGame(
                            notes, bgms, bgas, parser.wav_map, bmp_map,
                            parser.title, settings, visual_timing_map=visual_timing_map, measures=measures, mode=mode, metadata=metadata,
                            renderer=renderer, window=window,
                            ai_difficulty=ai_difficulty, note_mod=note_mod,
                            challenge_manager=challenge_manager
                        )
                        result = game.run()
                        action = result.get('action', 'QUIT')
                        if action != "RESTART":
                            # Challenges were handled internally in RhythmGame, but we can print here too
                            if isinstance(result, dict) and result.get('newly_completed'):
                                print(f"Newly completed challenges: {[c['id'] for c in result['newly_completed']]}")
                            break
                        # Restarting involves re-initializing mixer if needed or just re-running
                        _init_mixer(settings)


    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()  # Required for PyInstaller on macOS/Windows
    main()
