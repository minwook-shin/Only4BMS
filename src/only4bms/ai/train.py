import os
import sys
# Adjust path to import only4bms safely if run as a script
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env
from only4bms.ai.env import RhythmEnv
from only4bms.core.bms_parser import BMSParser

import random
import torch
import numpy as np

def set_global_seeds(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    # For SB3, we'll pass the seed to PPO directly

def train_and_export():
    set_global_seeds(42)
    
    # 1. Setup HARD env (Low jitter - 2ms)
    env_hard = RhythmEnv(None, hw_mult=1.0, jitter=2.0)
    env_hard.reset(seed=42) 

    print("Training Rhythm AI on deterministic curriculum for HARD difficulty (low jitter)...")
    model_hard = PPO("MlpPolicy", env_hard, verbose=1, learning_rate=0.003, ent_coef=0.01, n_steps=2048, seed=42)
    model_hard.learn(total_timesteps=25000)
    out_hard = os.path.join(os.path.dirname(__file__), "model_hard")
    model_hard.save(out_hard)
    
    # 2. Setup NORMAL env (High jitter - 30ms)
    # This forces the AI to miss the exact 'Perfect' center frequently, resulting in Greats
    env_normal = RhythmEnv(None, hw_mult=1.0, jitter=30.0)
    env_normal.reset(seed=42)

    print("\nTraining Rhythm AI on deterministic curriculum for NORMAL difficulty (high jitter)...")
    model_normal = PPO("MlpPolicy", env_normal, verbose=0, learning_rate=0.003, ent_coef=0.01, n_steps=2048, seed=42)
    model_normal.learn(total_timesteps=22500)
    out_normal = os.path.join(os.path.dirname(__file__), "model_normal")
    model_normal.save(out_normal)
    
    print(f"\nSaved deterministic SB3 models to {os.path.dirname(__file__)}")

if __name__ == "__main__":
    train_and_export()
