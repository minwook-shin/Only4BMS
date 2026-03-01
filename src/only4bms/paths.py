import os
import sys

def get_base_path():
    """Get the application's executable directory."""
    if getattr(sys, 'frozen', False):
        exe_path = os.path.dirname(os.path.abspath(sys.executable))
        if sys.platform == "darwin" and ".app/Contents/MacOS" in exe_path:
            return os.path.abspath(os.path.join(exe_path, "../../../"))
        return exe_path
    # Development mode: assume project root
    return os.path.abspath(".")

def get_writable_data_path():
    """Returns a writable directory for settings and BMS files.
    Prefers the executable directory (portable mode),
    falls back to User AppData if the exe dir is read-only (Windows Program Files).
    """
    base = get_base_path()
    # Try creating a dummy file to check writability
    test_file = os.path.join(base, ".write_test")
    try:
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return base
    except (IOError, OSError, PermissionError):
        # Fallback to User Data directory
        if sys.platform == "win32":
            user_data = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Only4BMS")
        elif sys.platform == "darwin":
            user_data = os.path.expanduser("~/Library/Application Support/Only4BMS")
        else:
            user_data = os.path.expanduser("~/.only4bms")
            
        try:
            os.makedirs(user_data, exist_ok=True)
        except:
            pass # Fallback to current dir if even this fails
        return user_data

BASE_PATH = get_base_path()
DATA_PATH = get_writable_data_path()
SETTINGS_FILE = os.path.join(DATA_PATH, "settings.json")
SONG_DIR = os.path.join(DATA_PATH, "bms")

# AI Model Path (Internal to bundle or project)
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    AI_DIR = os.path.join(sys._MEIPASS, "only4bms", "ai")
else:
    # Development: path to src/only4bms/ai
    AI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai")
