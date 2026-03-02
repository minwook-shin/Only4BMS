# Only4BMS

<img width="2556" height="1439" alt="스크린샷 2026-02-24 230333" src="https://github.com/user-attachments/assets/68d1891b-891b-4927-ab81-96f7bbc098f7" />

[![Only4BMS AI Battle1](https://img.youtube.com/vi/mrSUp4h7DnE/0.jpg)](https://youtu.be/mrSUp4h7DnE)

7 Tasten? Nein danke. 

Dies ist ein Pygame-basierter BMS-Player, der alle BMS-Charts **zwangsweise** auf **4 Tasten (DFJK)** neu anordnet.

## Projektübersicht

Only4BMS wurde für 4-Tasten-Puristen entwickelt, die vor komplexen BMS-Charts wie 7-Tasten oder 14-Tasten stehen und denken: „Wie soll ich das alles spielen?“

Dieses Projekt verwendet Pygame, um BMS-Dateien zu parsen, und bietet eine Umgebung, in der Sie jedes Chart-Format **auf 4 Spuren umgemappt** zusammen mit Tastentönen (Keysounds) genießen können.

## Hauptfunktionen

**Erzwungenes 4-Tasten-Mapping**: Weist 5-Tasten-, 7-Tasten-, 10-Tasten- und 14-Tasten-Charts automatisch 4 Spuren (D, F, J, K) mithilfe mathematischer Algorithmen zu.

**Dichteprüfer (Density Checker)**: Überprüft und visualisiert die Notendichte, wenn 7-Tasten-Charts zu 4-Tasten zusammengeführt werden.

## 🛠️ Tech-Stack

**Sprache**: Python 3.x

**Bibliothek**: Pygame (Sound & Rendering)

**Format**: Be-Music Script (.bms, .bme, .bml)

## So wird gespielt (Songs hinzufügen & Ausführen)

1. **Spiel erhalten**: Laden Sie die vorkompilierte `Only4BMS.exe` herunter oder bauen Sie sie selbst.
2. **Starten**: Führen Sie einfach die `Only4BMS.exe` in einem beliebigen Ordner aus. 
3. **Der `bms`-Ordner**: Beim Start erstellt das Spiel automatisch einen `bms`-Ordner im selben Verzeichnis wie die ausführbare Datei. Wenn keine Songs gefunden werden, generiert es einen einfachen Mock-Demo-Song.
4. **Eigene Songs hinzufügen**: 
   - Laden Sie BMS/BME/BML-Dateien und die zugehörigen Medien (Audio/BGA-Videos) herunter.
   - Entpacken Sie diese in ihre eigenen Unterordner innerhalb des `bms/`-Verzeichnisses.
   - Beispielstruktur:
     ```text
     [Verzeichnis mit Only4BMS.exe]
     ├── Only4BMS.exe
     └── bms/
         ├── Awesome Track/
         │   ├── song.bms
         │   ├── audio.wav
         │   └── video.mp4
         └── Another Track/
             └── ...
     ```

## 🎵 Kursmodus (Roguelike-Training)

Müde von den gleichen Liedern? Betritt den **Kursmodus**, einen endlosen prozeduralen Trainingsmodus!
- Prozedural generierte Notenblätter, die jedes Mal anders sind.
- Progressive Schwierigkeiten: Anfänger (BPM 80~110), Fortgeschritten (BPM 120~160), Experte (BPM 160~200).
- Stelle dich langen Noten und BPM-Gimmicks (Geschwindigkeitsänderungen), während du aufsteigst.
- Jede Etappe dauert etwa 30 Sekunden. Überlebe und sieh, was als Nächstes kommt!

## 🤖 KI-Training & Multiplayer

Only4BMS bietet einen KI-Multiplayer-Modus, der auf **Reinforcement Learning (PPO)** basiert.

### So funktioniert es
- Die KI wird mit `stable-baselines3` auf prozedural generierten Rhythmusspuren und lizenzfreien Demo-Songs trainiert.
- **Rechtliche Compliance**: Um ethische Standards zu gewährleisten, enthalten offizielle Versionen Modelle, die während des CI/CD-Prozesses *ausschließlich* auf nicht-kommerziellen Daten trainiert wurden.
- **Schwierigkeitsgrade**:
  - **NORMAL**: Für 25.000 Schritte trainiert. Hohe Genauigkeit, aber gelegentliche menschenähnliche Fehler.
  - **HARD**: Für 40.000 Schritte trainiert. Nahezu perfektes Timing und Combo-Erhalt.

### Lokales Training
Wenn Sie Ihre eigenen Modelle lokal trainieren möchten:
1. Installieren Sie die Abhängigkeiten: `pip install stable-baselines3 shimmy gymnasium torch`
2. Führen Sie das Trainingsskript aus: `python -m only4bms.ai.train`
3. Die generierten Dateien `model_normal.zip` und `model_hard.zip` werden in `src/only4bms/ai/` gespeichert.

### Automatisierte CI/CD
Unser GitHub Actions-Workflow trainiert die KI-Modelle bei jedem Release automatisch von Grund auf neu unter Verwendung der `Mock Song Demo`. Dies stellt sicher, dass die an die Benutzer verteilte Binärdatei immer „sauber“ und optimiert ist.

<a href="https://minwook-shin.itch.io/only4bms" class="btn">Auf itch.io spielen</a>

## Transparenzerklärung:

Only4BMS ist ein leidenschaftliches Soloprojekt.

Um den Produktionsprozess zu optimieren, habe ich KI-gestützte Technologie für den Code integriert.

Dies ermöglichte es mir, die Grenzen dessen zu erweitern, was eine einzelne Person schaffen kann, und sicherzustellen, dass sich das fertige Spiel geschliffen und vollständig anfühlt.

## 🤝 Beitragen

Fehlerberichte und Funktionsvorschläge von 4-Tasten-Benutzern sind immer willkommen!

## 📜 Lizenz

MIT-Lizenz - Sie können das Spiel gerne ändern und verbreiten. Bitte wahren Sie einfach den Frieden für 4-Tasten-Benutzer.
