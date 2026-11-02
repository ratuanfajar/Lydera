# Frontend

Belum ada proyek Flutter. Saat dimulai, aplikasi melayani dua peran: guru (upload modul, validasi anotasi dan soal) dan siswa (baca modul, kerjakan quiz, chatbot) lewat TalkBack.

## Prinsip yang sudah disepakati

- Semua presentasi ada di frontend: ukuran font, paginasi dinamis, geser halaman berikutnya, navigasi antar heading. Paginasi dihitung di client karena bergantung pada font-size runtime dan viewport.
- Ukuran font harus bisa diatur (siswa low-vision).
- Sedikit konten per halaman.
- Tombol dan kontrol punya `Semantics` label yang jelas; urutan fokus mengikuti urutan baca.
- Teks siap-baca datang dari backend (`readable_text`); frontend tidak menafsirkan LaTeX.

Detail aksesibilitas: `.claude/rules/accessibility.md`. Kontrak API: OpenAPI backend di `/docs`.
