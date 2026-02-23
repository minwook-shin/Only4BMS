# Only4BMS

Training AI to Learn Long Notes

[![Only4BMS AI Battle1](https://img.youtube.com/vi/XcOX6EJuddw/0.jpg)](https://youtu.be/XcOX6EJuddw)

Training AI to Learn dynamic BPM gimmicks

[![Only4BMS AI Battle2](https://img.youtube.com/vi/enBUNKZaR4M/0.jpg)](https://youtu.be/enBUNKZaR4M)


7 keys? No thanks. 

This is a Pygame-based BMS driver that **forcefully rearranges** all BMS charts into **4 keys (DFJK)** for playback.

## Project Overview

Only4BMS was created for 4-key purists who face complex BMS charts like 7-key or 14-key and think, “How am I supposed to play all this?”

This project uses Pygame to parse BMS files and provides an environment where you can enjoy any chart format **remapped into 4 lanes** along with key sounds.

## Key Features

Forced 4-Key Mapping: Automatically assigns 5-key, 7-key, 10-key, and 14-key charts to 4 lanes (D, F, J, K) using mathematical algorithms.

Density Checker: Checks and visualizes note density when 7-key charts are consolidated into 4-key.

## 🛠️ Tech Stack

Language: Python 3.x

Library: Pygame (Sound & Rendering)

Format: Be-Music Script (.bms, .bme, .bml)

## How to Play (Adding Songs & Running)

1. **Get the Game**: Download the pre-built `Only4BMS.exe` or build it yourself.
2. **Launch**: Simply run `Only4BMS.exe` from any folder. 
3. **The `bms` Folder**: Upon launching, the game automatically creates a `bms` folder in the same directory as the executable. If no songs are found, it generates a basic mock demo song.
4. **Adding Your Own Songs**: 
   - Download BMS/BME/BML files and their associated media (audio/BGA videos).
   - Extract them into their own subfolders inside the `bms/` directory.
   - Example structure:
     ```text
     [Directory containing Only4BMS.exe]
     ├── Only4BMS.exe
     └── bms/
         ├── Awesome Track/
         │   ├── song.bms
         │   ├── audio.wav
         │   └── video.mp4
         └── Another Track/
             └── ...
     ```

## 🤖 AI Training & Multiplayer

Only4BMS features an AI Multiplayer mode powered by **Reinforcement Learning (PPO)**.

### How it Works
- The AI is trained using `stable-baselines3` on procedurally generated rhythm tracks and royalty-free demo songs.
- **Legal Compliance**: To ensure ethical standards, official releases bundle models trained *exclusively* on non-commercial data during the CI/CD process.
- **Difficulties**:
  - **NORMAL**: Trained for 25,000 steps. High accuracy but occasional human-like errors.
  - **HARD**: Trained for 40,000 steps. Near-perfect timing and combo maintenance.

### Local Training
If you wish to train your own models locally:
1. Install dependencies: `pip install stable-baselines3 shimmy gymnasium torch`
2. Run the training script: `python -m only4bms.ai.train`
3. The generated `model_normal.zip` and `model_hard.zip` will be saved in `src/only4bms/ai/`.

### Automated CI/CD
Our GitHub Actions workflow automatically retrains the AI models from scratch using the bundled `Mock Song Demo` for every release. This ensures that the binary distributed to users is always "clean" and optimized.


<a href="https://minwook-shin.itch.io/only4bms" class="btn">Play on itch.io</a>


## Transparency Statement:

Only4BMS is a passionate solo project.

To streamline the production process, I’ve incorporated AI-assisted technology for code.

This allowed me to push the boundaries of what a single person can create, ensuring that the final game feels polished and complete.

## 🤝 Contributing

Bug reports and feature suggestions from 4-key users are always welcome!

## 📜 License

MIT License - Feel free to modify and distribute. Just please keep the peace for 4-key users.
