# Only4BMS

<img width="2556" height="1439" alt="스크린샷 2026-02-24 230333" src="https://github.com/user-attachments/assets/68d1891b-891b-4927-ab81-96f7bbc098f7" />

[![Only4BMS AI Battle1](https://img.youtube.com/vi/mrSUp4h7DnE/0.jpg)](https://youtu.be/mrSUp4h7DnE)

7 tasti? No, grazie. 

Questo è un driver BMS basato su Pygame che **riorganizza forzatamente** tutti i grafici BMS in **4 tasti (DFJK)** per la riproduzione.

## Panoramica del progetto

Only4BMS è stato creato per i puristi dei 4 tasti che si trovano di fronte a grafici BMS complessi come quelli a 7 tasti o 14 tasti e pensano: "Come dovrei suonare tutto questo?"

Questo progetto utilizza Pygame per analizzare i file BMS e fornisce un ambiente in cui è possibile godere di qualsiasi formato di grafico **rimappato in 4 corsie** insieme ai suoni dei tasti (keysounds).

## Caratteristiche principali

**Mappatura forzata a 4 tasti**: assegna automaticamente grafici a 5 tasti, 7 tasti, 10 tasti e 14 tasti a 4 corsie (D, F, J, K) utilizzando algoritmi matematici.

**Densimetro (Density Checker)**: controlla e visualizza la densità delle note quando i grafici a 7 tasti vengono consolidati in 4 tasti.

## 🛠️ Stack Tecnologico

**Linguaggio**: Python 3.x

**Libreria**: Pygame (Suono e Rendering)

**Formato**: Be-Music Script (.bms, .bme, .bml)

## Come giocare (Aggiunta di brani ed esecuzione)

1. **Ottieni il gioco**: scarica l'eseguibile `Only4BMS.exe` precompilato o compilalo tu stesso.
2. **Avvio**: è sufficiente eseguire `Only4BMS.exe` da qualsiasi cartella. 
3. **La cartella `bms`**: all'avvio, il gioco crea automaticamente una cartella `bms` nella stessa directory dell'eseguibile. Se non vengono trovati brani, genera un brano dimostrativo di base.
4. **Aggiunta dei propri brani**: 
   - Scarica i file BMS/BME/BML e i relativi supporti associati (audio/video BGA).
   - Estraili nelle rispettive sottocartelle all'interno della directory `bms/`.
   - Esempio di struttura:
     ```text
     [Directory contenente Only4BMS.exe]
     ├── Only4BMS.exe
     └── bms/
         ├── Awesome Track/
         │   ├── song.bms
         │   ├── audio.wav
         │   └── video.mp4
         └── Another Track/
             └── ...
     ```

## 🎵 Modalità Corso (Allenamento Roguelike)

Stanco delle stesse canzoni? Entra nella **Modalità Corso**, una modalità di allenamento procedurale senza fine!
- Spartiti generati proceduralmente, sempre diversi.
- Difficoltà progressive: Principiante (BPM 80~110), Intermedio (BPM 120~160), Avanzato (BPM 160~200).
- Affronta note lunghe e gimmick di cambio BPM man mano che sali di grado.
- Ogni stage dura circa 30 secondi. Sopravvivi e scopri cosa ti aspetta!

## 🤖 Allenamento AI e Multiplayer

Only4BMS dispone di una modalità AI Multiplayer alimentata da **Apprendimento per Rinforzo (PPO)**.

### Come funziona
- L'IA viene addestrata utilizzando `stable-baselines3` su tracce ritmiche generate proceduralmente e brani dimostrativi esenti da royalty.
- **Conformità legale**: per garantire standard etici, le versioni ufficiali includono modelli addestrati *esclusivamente* su dati non commerciali durante il processo CI/CD.
- **Difficoltà**:
  - **NORMAL**: addestrato per 25.000 passaggi. Elevata precisione ma occasionali errori simili a quelli umani.
  - **HARD**: addestrato per 40.000 passaggi. Tempismo e mantenimento delle combo quasi perfetti.

### Allenamento locale
Se desideri addestrare i tuoi modelli localmente:
1. Installa le dipendenze: `pip install stable-baselines3 shimmy gymnasium torch`
2. Esegui lo script di addestramento: `python -m only4bms.ai.train`
3. I file `model_normal.zip` e `model_hard.zip` generati verranno salvati in `src/only4bms/ai/`.

### CI/CD Automatizzato
Il nostro flusso di lavoro GitHub Actions addestra automaticamente i modelli IA da zero utilizzando `Mock Song Demo` per ogni release. Ciò garantisce che il binario distribuito agli utenti sia sempre "pulito" e ottimizzato.

<a href="https://minwook-shin.itch.io/only4bms" class="btn">Gioca su itch.io</a>

## Dichiarazione di Trasparenza:

Only4BMS è un appassionato progetto solista.

Per snellire il processo di produzione, ho incorporato la tecnologia assistita dall'IA per il codice.

Ciò mi ha permesso di spingere i confini di ciò che una singola persona può creare, assicurando che il gioco finale risulti rifinito e completo.

## 🤝 Contribuire

Le segnalazioni di bug e i suggerimenti di funzionalità dagli utenti dei 4 tasti sono sempre i benvenuti!

## 📜 Licenza

Licenza MIT - Sentiti libero di modificare e distribuire. Mantieni la pace per gli utenti di 4 tasti.
