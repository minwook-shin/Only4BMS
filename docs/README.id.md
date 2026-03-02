# Only4BMS

<img width="2556" height="1439" alt="스크린샷 2026-02-24 230333" src="https://github.com/user-attachments/assets/68d1891b-891b-4927-ab81-96f7bbc098f7" />

[![Only4BMS AI Battle1](https://img.youtube.com/vi/mrSUp4h7DnE/0.jpg)](https://youtu.be/mrSUp4h7DnE)

7 tombol? Tidak, terima kasih. 

Ini adalah driver BMS berbasis Pygame yang **mengatur ulang secara paksa** semua chart BMS menjadi **4 tombol (DFJK)** untuk dimainkan.

## Ikhtisar Proyek

Only4BMS diciptakan untuk para purist 4 tombol yang menghadapi chart BMS rumit seperti 7 tombol atau 14 tombol dan berpikir, “Bagaimana cara memainkan semua ini?”

Proyek ini menggunakan Pygame untuk mengurai file BMS dan menyediakan lingkungan di mana Anda dapat menikmati format chart apa pun yang **dipetakan ulang ke dalam 4 jalur** bersama dengan suara tuts (keysound).

## Fitur Utama

**Pemetaan 4 Tombol Paksa**: Secara otomatis menetapkan chart 5 tombol, 7 tombol, 10 tombol, dan 14 tombol ke 4 jalur (D, F, J, K) menggunakan algoritma matematika.

**Density Checker**: Memeriksa dan memvisualisasikan kepadatan note saat chart 7 tombol dikonsolidasikan menjadi 4 tombol.

## 🛠️ Stack Teknologi

**Bahasa**: Python 3.x

**Pustaka**: Pygame (Suara & Rendering)

**Format**: Be-Music Script (.bms, .bme, .bml)

## Cara Bermain (Menambahkan Lagu & Menjalankan)

1. **Dapatkan Game**: Unduh `Only4BMS.exe` yang sudah jadi atau bangun sendiri dari source code.
2. **Jalankan**: Cukup jalankan `Only4BMS.exe` dari folder mana pun. 
3. **Folder `bms`**: Saat dijalankan, game secara otomatis membuat folder `bms` di direktori yang sama dengan executable. Jika tidak ada lagu yang ditemukan, game akan menghasilkan lagu demo mock dasar.
4. **Menambahkan Lagu Anda Sendiri**: 
   - Unduh file BMS/BME/BML dan media terkaitnya (audio/video BGA).
   - Ekstrak ke dalam subfoldernya masing-masing di dalam direktori `bms/`.
   - Contoh struktur:
     ```text
     [Direktori yang berisi Only4BMS.exe]
     ├── Only4BMS.exe
     └── bms/
         ├── Awesome Track/
         │   ├── song.bms
         │   ├── audio.wav
         │   └── video.mp4
         └── Another Track/
             └── ...
     ```

## 🎵 Mode Kursus (Pelatihan Roguelike)

Bosan dengan lagu yang itu-itu saja? Masuki **Mode Kursus**, mode pelatihan prosedural tanpa akhir!
- Chart yang dihasilkan secara prosedural dan berbeda setiap saat.
- Kesulitan progresif: Pemula (BPM 80~110), Menengah (BPM 120~160), Lanjutan (BPM 160~200).
- Hadapi long notes dan gimmick perubahan BPM saat Anda naik peringkat.
- Setiap stage berlangsung selama ~30 detik. Bertahanlah dan hadapi tantangan berikutnya!

## 🤖 Pelatihan AI & Multiplayer

Only4BMS menghadirkan mode AI Multiplayer yang didukung oleh **Reinforcement Learning (PPO)**.

### Cara Kerjanya
- AI dilatih menggunakan `stable-baselines3` pada lagu ritme yang dihasilkan secara prosedural dan lagu demo bebas royalti.
- **Kepatuhan Hukum**: Untuk memastikan standar etika, rilisan resmi menyertakan model yang dilatih *secara eksklusif* pada data non-komersial selama proses CI/CD.
- **Tingkat Kesulitan**:
  - **NORMAL**: Dilatih selama 25.000 langkah. Akurasi tinggi tetapi terkadang ada kesalahan mirip manusia.
  - **HARD**: Dilatih selama 40.000 langkah. Ketepatan waktu dan pemeliharaan combo yang hampir sempurna.

### Pelatihan Lokal
Jika Anda ingin melatih model Anda sendiri secara lokal:
1. Instal dependensi: `pip install stable-baselines3 shimmy gymnasium torch`
2. Jalankan skrip pelatihan: `python -m only4bms.ai.train`
3. File `model_normal.zip` dan `model_hard.zip` yang dihasilkan akan disimpan di `src/only4bms/ai/`.

### CI/CD Terotomatisasi
Alur kerja GitHub Actions kami secara otomatis melatih ulang model AI dari nol menggunakan `Mock Song Demo` yang disertakan untuk setiap rilis. Ini memastikan bahwa binary yang didistribusikan ke pengguna selalu "bersih" dan optimal.

<a href="https://minwook-shin.itch.io/only4bms" class="btn">Mainkan di itch.io</a>

## Pernyataan Transparansi:

Only4BMS adalah proyek solo yang dikerjakan dengan penuh semangat.

Untuk merampingkan proses produksi, saya telah menyertakan teknologi berbantuan AI untuk kode.

Hal ini memungkinkan saya untuk melampaui batas dari apa yang dapat dibuat oleh satu orang, memastikan bahwa game akhir terasa halus dan lengkap.

## 🤝 Kontribusi

Laporan bug dan saran fitur dari pengguna 4 tombol selalu kami nantikan!

## 📜 Lisensi

Lisensi MIT - Bebas untuk dimodifikasi dan didistribusikan. Harap jaga kedamaian bagi pengguna 4 tombol.
