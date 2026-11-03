# Deploy dan rollback

Workflow: `.github/workflows/deploy.yaml` ("Build and Deploy"). Image: `ghcr.io/<owner>/lydera`.

## Deploy normal

1. Pastikan perubahan sudah merge dan migrasi Alembic sudah disiapkan (migrasi tidak dijalankan oleh workflow; periksa `/opt/lydera/deploy.sh` di VPS apakah menjalankannya).
2. Buat tag git: `lydera-1.2.3`, `v1.2.3`, atau `1.2.3`. Awalan `lydera-` dan `v` dibuang; tag image menjadi `1.2.3`.
3. `git push origin <tag>` memicu: build image dan push ke GHCR (tag versi + `latest`), lalu SSH ke VPS menjalankan `bash /opt/lydera/deploy.sh <tag>`.

## Build manual tanpa deploy

Actions, "Build and Deploy", Run workflow: isi `image_tag` (default `test`), biarkan `deploy` false. Centang `deploy` untuk ikut deploy.

## Rollback

Actions, Run workflow: isi `rollback_tag` dengan versi lama yang masih ada di GHCR (mis. `1.0.0`). Job rollback tidak membangun image; hanya menjalankan `deploy.sh` dengan tag lama.

Setelah rilis yang mengubah chunker Clarifier, reindex semua bab yang sudah terindeks (`POST /api/clarifier/classrooms/{id}/reindex`); perubahan versi prompt anotasi tidak membutuhkan langkah tambahan.

Rollback tidak membalik migrasi database. Jika rilis yang dibatalkan membawa migrasi, jalankan `alembic downgrade` secara terpisah dan hati-hati; jangan jalankan otomatis.

## Secrets yang dipakai workflow

`VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `GHCR_USER`, `GHCR_PAT`. Nilai dikelola di GitHub, bukan di repo.
