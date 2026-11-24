# Catatan Penyempurnaan Project

## Prinsip
Penyempurnaan dilakukan tanpa menambah fitur, mengubah tampilan, mengubah kontrak API, mengubah payload/protokol WebSocket, atau mengubah alur bisnis yang sudah ada.

## Perubahan pada build ini

1. `app.py` — akses database autentikasi/session yang dipanggil dari handler HTTP dipindahkan ke `asyncio.to_thread()`. Operasi SQLite sinkron tidak lagi menahan thread event loop saat request diproses.
2. `app.py` — pembacaan dan hashing file update dijalankan di thread terpisah agar pemeriksaan file besar tidak memblokir event loop.
3. `app.py` — hasil SHA-256 file update di-cache berdasarkan path, ukuran, dan `mtime_ns`. File yang tidak berubah tidak perlu di-hash ulang pada setiap pemeriksaan.
4. `app.py` — penulisan chunk upload file update dipindahkan ke thread terpisah, dengan urutan penulisan tetap serial dan proses publikasi file tetap atomik.
5. `app.py` — pencarian file update dan pembuatan direktori update dijalankan di thread terpisah.
6. `app.py` — daftar target dinormalisasi dan duplikat yang berbeda hanya pada huruf besar/kecil dibuang, baik pada konfigurasi otomatis maupun saat menjalankan job. Ini mencegah target yang sama diproses berulang akibat input duplikat; urutan target pertama tetap dipertahankan.

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

## Optimasi tambahan pada pembaruan ini

8. `app.py` — relay upstream WebSocket melakukan pre-filter teks ringan sebelum JSON decode. Hanya frame yang berpotensi memengaruhi countdown, snapshot peserta, atau konfirmasi event yang di-parse. Frame tetap diteruskan sebagai teks asli tanpa serialisasi ulang.

Perubahan dibatasi pada pendukung KickAll dan relay WebSocket. Fitur unggah/update, hashing file, database, autentikasi, serta modul lain tidak dioptimalkan atau diubah. Tidak ada benchmark runtime atau klaim persentase peningkatan; dampak aktual bergantung pada pola pesan upstream dan kondisi jaringan.

## Validasi tambahan

- `app.py`: lolos `py_compile` dan berhasil di-import.
- Prefilter WebSocket: smoke test untuk pesan biasa, auto countdown, snapshot peserta, socket BANK, dan konfirmasi event.
- JavaScript aktif dan artefak JS: lolos `node --check`.
- Uji integrasi jaringan/upstream dan benchmark unggah file besar tidak tersedia di lingkungan ini.
