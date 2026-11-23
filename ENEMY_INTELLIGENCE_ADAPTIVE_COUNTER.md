# Enemy Intelligence + Adaptive Counter

- Profil musuh dibuat dari kombinasi tepat 10 username pada TARGET. Urutan username tidak berpengaruh; huruf besar/kecil dinormalisasi.
- Profil dan statistik dipisahkan per akun pengguna.
- Setiap konfigurasi counter yang dipakai disimpan sebagai varian tersendiri.
- Hasil pembelajaran dicatat otomatis ketika event `kick.job.finished` diterima. Sistem menghitung username WS1–WS10 unik yang mendapat konfirmasi kick selama job berjalan, lalu membandingkannya dengan jumlah TARGET saat job dimulai.
- Jika jumlah WS1–WS10 yang terkena kick lebih sedikit daripada jumlah TARGET, hasil dicatat sebagai BERHASIL. Jika lebih banyak, dicatat sebagai GAGAL. Jika sama, hasil NETRAL dan statistik tidak berubah.
- Hasil hanya dicatat untuk profil dengan tepat 10 username TARGET, sesuai kunci profil Adaptive Counter.
- Saat kombinasi 10 username yang sama dimuat kembali, sistem memilih varian yang memiliki rasio keberhasilan terbaik; jumlah kemenangan dan total percobaan menjadi pemecah seri.
- Auto-apply hanya mengisi parameter konfigurasi. Sistem tidak otomatis menekan atau menjalankan KICK ALL.

## Batasan data

Build ini menggunakan identitas 10 username TARGET sebagai kunci profil. Ia tidak mengklaim membaca komposisi unit/pasukan lawan karena versi sumber ini belum menyediakan feed komposisi pasukan lawan yang terstruktur. Penghitungan WS kicked bergantung pada event kick terkonfirmasi yang diterima frontend; event yang tidak diterima tidak dapat dihitung.
