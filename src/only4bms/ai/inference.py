import os
import sys
import numpy as np
from only4bms import paths

class RhythmInference:
    def __init__(self, difficulty='normal'):
        self.usable = False

        # 1. Determine base search paths
        search_dirs = [paths.AI_DIR]
        
        # Fallbacks for extra robustness
        if getattr(sys, 'frozen', False):
            search_dirs.append(sys._MEIPASS)
        search_dirs.append(os.path.join(paths.BASE_PATH, "only4bms", "ai"))
        search_dirs.append(os.getcwd())

        # 2. Find the model file
        weight_base = f"model_{difficulty}"
        final_path = None
        
        for d in search_dirs:
            if not d: continue
            p = os.path.join(d, weight_base)
            if os.path.exists(p + ".zip"):
                final_path = p
                print(f"DEBUG [Inference]: Found {difficulty} model at {p}.zip")
                break
        
        if not final_path:
            print(f"ERROR [Inference]: Could not find {weight_base}.zip in {search_dirs}")
            return

        # 3. Load the model
        try:
            from stable_baselines3 import PPO
            self.model = PPO.load(final_path)
            self.usable = True
            print(f"SUCCESS [Inference]: AI {difficulty} model loaded.")
        except Exception as e:
            print(f"ERROR [Inference]: Failed to load AI model: {e}")

    def predict(self, obs, deterministic=False):
        if not self.usable:
            return 0
            
        action, _ = self.model.predict(obs, deterministic=deterministic)
        return action
