# Catatan Penyempurnaan Project

## Prinsip
Penyempurnaan dilakukan tanpa menambah fitur, mengubah tampilan, mengubah kontrak API, mengubah payload/protokol WebSocket, atau mengubah alur bisnis yang sudah ada.

## Perubahan pada build ini

1. `app.py` — akses database autentikasi/session yang dipanggil dari handler HTTP dipindahkan ke `asyncio.to_thread()`. Operasi SQLite sinkron tidak lagi menahan thread event loop saat request diproses.
2. `app.py` — pembacaan dan hashing file update dijalankan di thread terpisah agar pemeriksaan file besar tidak memblokir event loop.
3. `app.py` — hasil SHA-256 file update di-cache berdasarkan path, ukuran, dan `mtime_ns`. File yang tidak berubah tidak perlu di-hash ulang pada setiap pemeriksaan.
4. `app.py` — penulisan chunk upload file update dipindahkan ke thread terpisah, dengan urutan penulisan tetap serial dan proses publikasi file tetap atomik.
5. `app.py` — pencarian file update dan pembuatan direktori update dijalankan di thread terpisah.

## Bagian yang sengaja tidak diubah

- Dispatch Kick/KickAll, timer countdown, penjadwalan task, retry/replacement, Delay Target/Delay Socket, dan rate-limit.
- Pengiriman WebSocket upstream dan format payload.
- UI, sinkronisasi konfigurasi frontend, dan interval countdown.
- `auth.py`, skema database, autentikasi, session, perangkat, dan otorisasi.
- Kontrak endpoint serta format respons API.

Bagian yang memicu tindakan massal dan batas pengiriman tidak dioptimalkan atau dipercepat. Perubahan dibatasi pada efisiensi I/O, hashing, dan pemrosesan request umum.

## Validasi yang dilakukan

- `app.py` dan `auth.py`: lolos parsing/kompilasi Python.
- `app.py`: berhasil di-import dalam lingkungan pemeriksaan.
- `check.js`, `extracted.js`, dan JavaScript inline `public/index.html`: lolos `node --check`.
- Tidak ada klaim benchmark runtime atau peningkatan persentase; dampak performa perlu diukur pada server target.

## Catatan distribusi dan keamanan

- `auth.db` dan `__pycache__` tidak disertakan dalam ZIP hasil agar database sesi/akun lokal dan bytecode mesin tidak ikut terdistribusi.
- Saat aplikasi dijalankan, `init_auth_db()` membuat database baru sesuai mekanisme aplikasi yang sudah ada.
- Kredensial bootstrap yang sudah ada di `auth.py` tidak diubah dalam penyempurnaan ini. Pastikan kredensial admin awal segera diganti setelah deployment.
