# 🎹 Only4BMS

7 keys? No thanks. 

This is a Pygame-based BMS driver that **forcefully rearranges** all BMS charts into **4 keys (DFJK)** for playback.

## 🚀 Project Overview

Only4BMS was created for 4-key purists who face complex BMS charts like 7-key or 14-key and think, “How am I supposed to play all this?”

This project uses Pygame to parse BMS files and provides an environment where you can enjoy any chart format **remapped into 4 lanes** along with key sounds.

## ✨ Key Features

Forced 4-Key Mapping: Automatically assigns 5-key, 7-key, 10-key, and 14-key charts to 4 lanes (D, F, J, K) using mathematical algorithms.

Density Checker: Checks and visualizes note density when 7-key charts are consolidated into 4-key.

## 🛠️ Tech Stack

Language: Python 3.x

Library: Pygame (Sound & Rendering)

Format: Be-Music Script (.bms, .bme, .bml)

## 🎮 How to Play (Adding Songs & Running)

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
5. **Play**: From the Song Selection Menu, press `F5` to magically rescan the `bms` folder and load your newly added songs! You can also press `F3` to search the web for BMS files directly from the game.

## 📦 How to Build (EXE)

To construct the standalone `.exe` without packing the `bms/` media folder (keeping it lightweight):

1. **Requirements**: Python 3.10+
2. **Install Project & Tools**:
   ```bash
   pip install -e .
   pip install pyinstaller
   ```
3. **Compile Executable**:
   ```bash
   pyinstaller --onefile --windowed --name=Only4BMS src/only4bms/main.py
   ```
4. **Locate the Output**: The compiled `Only4BMS.exe` will be located in the `dist/` directory. By design, the massive `bms` content directory is ignored.

## 🤝 Contributing

Bug reports and feature suggestions from 4-key users are always welcome!

## 📜 License

MIT License - Feel free to modify and distribute. Just please keep the peace for 4-key users.
