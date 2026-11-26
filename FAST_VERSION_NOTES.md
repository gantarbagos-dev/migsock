# Fast Version — perubahan terukur dan batas kompatibilitas

Versi ini dibuat dari `migsockv6-hybrid(1).zip`.

## Perubahan runtime

1. **Mengurangi lock contention pada fan-out Kick All** (`app.py`, fungsi `send_direct`).
   - Pemeriksaan `stopped` dan `kicked` tidak lagi mengambil `replacement_state["lock"]`.
   - Seluruh state job ini dibaca/ditulis pada satu asyncio event loop; dua pembacaan tersebut tidak memiliki `await` di antaranya.
   - Sebelumnya lock hanya melindungi pemeriksaan, lalu dilepas sebelum `queue.put()`. Karena itu lock tidak melindungi proses enqueue dan tidak menghilangkan kemungkinan state berubah setelah pemeriksaan.
   - Perubahan ini menghilangkan satu akuisisi lock untuk setiap pasangan target/WebSocket.

## Yang sengaja tidak diubah

- Endpoint API dan bentuk payload.
- Protokol upstream WebSocket dan isi frame yang diteruskan.
- Urutan target, jumlah loop, Delay Target, Delay Socket, Socket Apply, Target Apply.
- Batas rate kick per WebSocket (200 per 500 ms maksimum backend; konfigurasi UI tetap dibatasi backend).
- Timeout kirim, queue size, konfirmasi kick, replacement target, pemisahan sesi pengguna, serta pemisahan socket BANK/troop.
- Frontend dan tampilan.

## Validasi

- Jalankan `python3 -m py_compile app.py auth.py`.
- Jalankan `node --check` untuk file JavaScript yang tersedia.
- Uji beban wajib dilakukan di VPS dengan upstream sebenarnya. Tidak ada klaim angka peningkatan throughput dari pemeriksaan statis saja.

## Batasan

Ini adalah optimasi overhead dispatcher yang konservatif, bukan perubahan batas kecepatan/protokol. Kecepatan akhir tetap dipengaruhi RTT upstream, limit server mig33, jumlah WebSocket aktif, dan konfigurasi delay.
