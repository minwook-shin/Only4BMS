# AI Rhythm Player: Only4BMS

This directory contains the reinforcement learning (RL) implementation for an autonomous rhythm game player tailored for the 4-lane BMS environment.

## 🚀 Overview

The Only4BMS AI is trained to play rhythm games by simulating human-like perception and reaction timing. It uses **Proximal Policy Optimization (PPO)** to master complex rhythmic patterns through a custom-built gymnasium environment.

## 🧠 Reinforcement Learning Architecture

### Algorithm: PPO (Proximal Policy Optimization)
We utilize the PPO implementation from `stable-baselines3`. PPO was chosen for its stability and reliability in continuous and discrete action spaces, making it ideal for the high-precision requirements of a rhythm game.

### Environment: `RhythmEnv`
A custom Gymnasium environment (`env.py`) that simulates the 4-lane rhythm game mechanics:
- **State Space (Observation)**: A 3-dimensional vector:
  1. `relative_distance_1`: Distance to the closest upcoming note (normalized).
  2. `relative_distance_2`: Distance to the second closest note (normalized).
  3. `lane_state`: Boolean indicating if the lane is currently being held.
- **Action Space**: Discrete(2) — `0` (Idle) or `1` (Tap/Press).
- **Step interval**: 16ms (simulating ~60 FPS logic).

### ⚖️ Reward Structure
The agent is incentivized for precision and penalized for inefficiency:
- **Perfect Hit**: +10.0 (within ±40ms)
- **Great Hit**: +3.0 (within ±100ms)
- **Good Hit**: +0.5 (within ±200ms)
- **Miss**: -1.0
- **Random Press (Ghosting)**: -1.0
- **Holding/Spamming**: -1.0 (Forces discrete tapping behavior)
- **Survival**: +0.01 per frame (incentivizes completing the track)

## 📊 Difficulty & Human Simulation

We introduce **Perception Jitter** to simulate different skill levels:
- **Hard Mode**: Low jitter (2ms). The AI has near-perfect perception, leading to frame-perfect timing.
- **Normal Mode**: High jitter (30ms). Adds Gaussian noise to the note timestamps, forcing the AI to miss the "Perfect" center and resulting in more "Great" or "Good" judgments.
