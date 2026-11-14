# Catatan Optimasi Project Duel Bot

## Prinsip
Optimasi dilakukan secara konservatif: tidak mengubah protokol WebSocket, payload, urutan proses bisnis, konfigurasi, batas rate-limit, autentikasi, maupun otorisasi.

## Perubahan
1. `public/index.html` — rendering daftar USER menggunakan `DocumentFragment` dan `replaceChildren()` agar perubahan DOM dilakukan sekaligus, mengurangi operasi DOM berulang saat snapshot participant diperbarui.
2. `public/index.html` — pencarian target menggunakan `appState.targets` (`Map`) sehingga pengecekan duplikat menjadi lookup konstan, bukan pemindaian seluruh elemen DOM.
3. `public/index.html` — sinkronisasi indeks target saat aksi `List User` mengosongkan daftar target, agar lookup Map tetap sama dengan tampilan.
4. `check.js` — menerapkan optimasi rendering dan lookup target yang sama.
5. `extracted.js` — menerapkan optimasi rendering daftar USER; lookup target yang sudah memakai indeks `Map` dipertahankan.

## Bagian yang sengaja tidak diubah
- `app.py`: dispatch KICK, pengiriman WebSocket, timer countdown, rate-limit, retry/replacement, dan batas otorisasi.
- `auth.py` dan `auth.db`: autentikasi, session, perangkat, serta data akun.
- Kontrak API, format payload, file konfigurasi, dan fungsi UI lainnya.

Bagian backend/protokol tidak diubah karena perubahan agresif tanpa pengujian integrasi terhadap server upstream berisiko mengubah perilaku project.

## Validasi
- `app.py` dan `auth.py`: lolos kompilasi Python.
- `check.js`, `extracted.js`, dan JavaScript inline pada `public/index.html`: lolos `node --check`.
- Tidak ada klaim benchmark runtime; peningkatan yang diterapkan adalah pengurangan kerja DOM dan pencarian target pada jalur frontend.
