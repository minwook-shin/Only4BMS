"""
Training script for the AI Battle opponent.

Run from the project root:
    python mods/ai_multi/train.py

Produces model_normal.zip and model_hard.zip in mods/ai_multi/.
Users who want to retrain or replace the AI can run this script directly.
"""

import os
import sys

# Allow both direct script execution and package import
_mod_dir = os.path.dirname(os.path.abspath(__file__))
if _mod_dir not in sys.path:
    sys.path.insert(0, _mod_dir)

# Allow finding only4bms package when run as a script
_src_dir = os.path.abspath(os.path.join(_mod_dir, '..', '..', 'src'))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from env import RhythmEnv  # noqa: E402  (local, works both as script and package)

from stable_baselines3 import PPO
import random
import torch
import numpy as np


def set_global_seeds(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def train_and_export():
    set_global_seeds(42)

    # 1. HARD model — 2 ms jitter, near-perfect timing
    env_hard = RhythmEnv(None, hw_mult=1.0, jitter=2.0)
    env_hard.reset(seed=42)

    print("Training HARD model (low jitter)...")
    model_hard = PPO("MlpPolicy", env_hard, verbose=1,
                     learning_rate=0.003, ent_coef=0.01, n_steps=2048, seed=42)
    model_hard.learn(total_timesteps=25000)
    model_hard.save(os.path.join(_mod_dir, "model_hard"))

    # 2. NORMAL model — 30 ms jitter, mostly GREAT hits
    env_normal = RhythmEnv(None, hw_mult=1.0, jitter=30.0)
    env_normal.reset(seed=42)

    print("\nTraining NORMAL model (high jitter)...")
    model_normal = PPO("MlpPolicy", env_normal, verbose=0,
                       learning_rate=0.003, ent_coef=0.01, n_steps=2048, seed=42)
    model_normal.learn(total_timesteps=22500)
    model_normal.save(os.path.join(_mod_dir, "model_normal"))

    print(f"\nSaved models to {_mod_dir}")


if __name__ == "__main__":
    train_and_export()
