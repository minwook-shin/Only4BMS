"""
RhythmInference — loads a trained PPO model for AI opponent use.

Model files (model_normal.zip, model_hard.zip) are searched in
mods/ai_multi/ (next to this file) so users can freely replace them.
"""

import os
import sys


class RhythmInference:
    def __init__(self, difficulty='normal'):
        self.usable = False

        # In a frozen PyInstaller build, __file__ lives inside _MEIPASS.
        # Use paths.MODS_DIR so we always resolve to <exe_dir>/mods/ai_multi/.
        try:
            from only4bms import paths as _paths
            _mod_dir = os.path.join(_paths.MODS_DIR, "ai_multi")
        except ImportError:
            _mod_dir = os.path.dirname(os.path.abspath(__file__))

        search_dirs = [_mod_dir]

        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Extra fallback: models may have been bundled inside the exe
            search_dirs.append(os.path.join(sys._MEIPASS, "mods", "ai_multi"))

        search_dirs.append(os.getcwd())

        weight_base = f"model_{difficulty}"
        final_path = None

        for d in search_dirs:
            if not d:
                continue
            p = os.path.join(d, weight_base)
            if os.path.exists(p + ".zip"):
                final_path = p
                print(f"[RhythmInference] Found {difficulty} model at {p}.zip")
                break

        if not final_path:
            print(f"[RhythmInference] Could not find {weight_base}.zip in {search_dirs}")
            return

        try:
            from stable_baselines3 import PPO
            self.model = PPO.load(final_path)
            self.usable = True
            print(f"[RhythmInference] Loaded {difficulty} model.")
        except Exception as e:
            print(f"[RhythmInference] Failed to load model: {e}")

    def predict(self, obs, deterministic=False):
        if not self.usable:
            return 0
        action, _ = self.model.predict(obs, deterministic=deterministic)
        return action
