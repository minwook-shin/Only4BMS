import os
import numpy as np

class RhythmInference:
    def __init__(self, difficulty='normal'):
        weight_path = os.path.join(os.path.dirname(__file__), f"model_{difficulty}")
            
        self.usable = False
        try:
            from stable_baselines3 import PPO
            self.model = PPO.load(weight_path)
            self.usable = True
        except ImportError:
            print("To use the AI bot, install stable-baselines3: pip install stable-baselines3")
        except Exception as e:
            print(f"Failed to load AI weights from {weight_path}: {e}")

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
