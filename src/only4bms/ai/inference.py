import os
import sys
import numpy as np

class RhythmInference:
    def __init__(self, difficulty='normal'):
        self.usable = False

        # 1. Determine base search paths
        search_dirs = [os.path.dirname(__file__)]
        if getattr(sys, 'frozen', False):
            search_dirs.insert(0, os.path.join(sys._MEIPASS, "only4bms", "ai"))
            search_dirs.append(sys._MEIPASS)
        search_dirs.append(os.path.join(os.getcwd(), "only4bms", "ai"))
        search_dirs.append(os.getcwd())

        # 2. Find the model file
        weight_base = f"model_{difficulty}"
        final_path = None
        
        for d in search_dirs:
            p = os.path.join(d, weight_base)
            if os.path.exists(p + ".zip"):
                final_path = p
                break
        
        if not final_path:
            return

        # 3. Load the model
        try:
            from stable_baselines3 import PPO
            self.model = PPO.load(final_path)
            self.usable = True
        except Exception:
            pass

    def predict(self, obs, deterministic=False):
        """
        Takes observation array of shape (3,), representing relative distances to upcoming notes and hold state for a single lane.
        Returns 0 or 1 for key press.
        Uses SB3 PPO predict.
        """
        if not self.usable:
            return 0
            
        action, _ = self.model.predict(obs, deterministic=deterministic)
        return action
