# Dokumentasi Lydera

| Folder / berkas | Isi |
|---|---|
| [architecture.md](architecture.md) | Batas tanggung jawab antar bagian dan alur data tiap fitur |
| [adr/](adr/) | Architecture Decision Record: keputusan yang bertahan lama beserta alasannya |
| [research/](research/) | Catatan riset dan brainstorming (sumber, opsi, rekomendasi), dibuat lewat `/research` |
| [specs/](specs/) | Spec fitur, satu berkas per fitur (`NNNN-slug.md`), dibuat lewat `/feature-spec` |
| [runbooks/](runbooks/) | Langkah operasional: dev lokal, deploy, rollback |
| [planning/](planning/) | Backlog dan roadmap |

Aturan menulis:
- Bahasa Indonesia; istilah teknis tetap Inggris.
- ADR tidak diedit setelah diterima. Keputusan berubah berarti ADR baru yang menggantikan, dan ADR lama diberi status `digantikan oleh NNNN`.
- Spec mengikuti `specs/_template.md`.
