CREATE TABLE IF NOT EXISTS module (
    id          SERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chapter (
    id          SERIAL PRIMARY KEY,
    module_id   INTEGER NOT NULL REFERENCES module(id) ON DELETE CASCADE,
    number      INTEGER,
    title       TEXT,
    source_file TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS block (
    id              SERIAL PRIMARY KEY,
    chapter_id      INTEGER NOT NULL REFERENCES chapter(id) ON DELETE CASCADE,
    reading_order   INTEGER NOT NULL,
    block_type      TEXT    NOT NULL CHECK (block_type IN
                        ('heading', 'text', 'formula', 'table', 'image')),
    readable_text   TEXT    NOT NULL,
    review_priority TEXT    NOT NULL DEFAULT 'normal'
                        CHECK (review_priority IN ('low', 'normal', 'high')),
    heading_level   INTEGER,
    source_markup   TEXT,
    caption         TEXT,
    image_file      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS job (
    id           SERIAL PRIMARY KEY,
    chapter_id   INTEGER NOT NULL REFERENCES chapter(id) ON DELETE CASCADE,
    pdf_path     TEXT NOT NULL,
    out_dir      TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'queued'
                     CHECK (status IN ('queued', 'running', 'done', 'failed')),
    error        TEXT,
    blocks_total INTEGER,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fase (
    id    SERIAL PRIMARY KEY,
    kode  TEXT NOT NULL UNIQUE CHECK (kode IN ('E', 'F'))
);

CREATE TABLE IF NOT EXISTS cp (
    id       SERIAL PRIMARY KEY,
    fase_id  INTEGER NOT NULL REFERENCES fase(id),
    domain   TEXT NOT NULL CHECK (domain IN (
                 'Bilangan', 'Aljabar dan Fungsi', 'Pengukuran', 'Geometri',
                 'Analisis Data dan Peluang', 'Fungsi', 'Kalkulus')),
    cp_text  TEXT NOT NULL,
    UNIQUE (fase_id, domain)
);

ALTER TABLE module  ADD COLUMN IF NOT EXISTS fase_id INTEGER REFERENCES fase(id);
ALTER TABLE chapter ADD COLUMN IF NOT EXISTS cp_id   INTEGER REFERENCES cp(id);

CREATE TABLE IF NOT EXISTS quiz_request (
    id          SERIAL PRIMARY KEY,
    module_id   INTEGER NOT NULL REFERENCES module(id) ON DELETE CASCADE,
    status      TEXT    NOT NULL DEFAULT 'queued'
                    CHECK (status IN ('queued', 'running', 'done', 'failed')),
    error       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE quiz_request DROP COLUMN IF EXISTS hots_count;
ALTER TABLE quiz_request DROP COLUMN IF EXISTS lots_count;

CREATE TABLE IF NOT EXISTS quiz_request_chapter (
    quiz_request_id INTEGER NOT NULL REFERENCES quiz_request(id) ON DELETE CASCADE,
    chapter_id      INTEGER NOT NULL REFERENCES chapter(id) ON DELETE CASCADE,
    PRIMARY KEY (quiz_request_id, chapter_id)
);

ALTER TABLE quiz_request_chapter ADD COLUMN IF NOT EXISTS hots_count INTEGER NOT NULL DEFAULT 0 CHECK (hots_count >= 0);
ALTER TABLE quiz_request_chapter ADD COLUMN IF NOT EXISTS lots_count INTEGER NOT NULL DEFAULT 0 CHECK (lots_count >= 0);

CREATE TABLE IF NOT EXISTS soal_stimulus (
    id                          SERIAL PRIMARY KEY,
    quiz_request_id             INTEGER NOT NULL REFERENCES quiz_request(id) ON DELETE CASCADE,
    chapter_id                  INTEGER NOT NULL REFERENCES chapter(id) ON DELETE CASCADE,
    source_markup               TEXT    NOT NULL DEFAULT '',
    readable_text               TEXT    NOT NULL,
    review_status               TEXT    NOT NULL DEFAULT 'pending'
                                     CHECK (review_status IN ('pending', 'approved', 'rejected', 'edited')),
    source_reading_order_start  INTEGER NOT NULL,
    source_reading_order_end    INTEGER NOT NULL,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS soal (
    id                          SERIAL PRIMARY KEY,
    quiz_request_id             INTEGER NOT NULL REFERENCES quiz_request(id) ON DELETE CASCADE,
    chapter_id                  INTEGER NOT NULL REFERENCES chapter(id) ON DELETE CASCADE,
    bloom_level                 INTEGER NOT NULL CHECK (bloom_level BETWEEN 1 AND 6),
    question_text               TEXT    NOT NULL,
    correct_option              CHAR(1) NOT NULL CHECK (correct_option IN ('A', 'B', 'C', 'D')),
    kesimpulan                  TEXT    NOT NULL,
    source_reading_order_start  INTEGER NOT NULL,
    source_reading_order_end    INTEGER NOT NULL,
    review_status               TEXT    NOT NULL DEFAULT 'pending'
                                     CHECK (review_status IN ('pending', 'approved', 'rejected', 'edited')),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE soal ADD COLUMN IF NOT EXISTS stimulus_id INTEGER REFERENCES soal_stimulus(id) ON DELETE CASCADE;
ALTER TABLE soal ADD COLUMN IF NOT EXISTS review_priority TEXT NOT NULL DEFAULT 'normal'
    CHECK (review_priority IN ('low', 'normal', 'high'));
ALTER TABLE soal ADD COLUMN IF NOT EXISTS validation_notes TEXT;

CREATE TABLE IF NOT EXISTS soal_opsi (
    id        SERIAL PRIMARY KEY,
    soal_id   INTEGER NOT NULL REFERENCES soal(id) ON DELETE CASCADE,
    label     CHAR(1) NOT NULL CHECK (label IN ('A', 'B', 'C', 'D')),
    opsi_text TEXT    NOT NULL,
    UNIQUE (soal_id, label)
);

CREATE TABLE IF NOT EXISTS soal_langkah (
    id       SERIAL PRIMARY KEY,
    soal_id  INTEGER NOT NULL REFERENCES soal(id) ON DELETE CASCADE,
    urutan   INTEGER NOT NULL,
    teks     TEXT    NOT NULL,
    UNIQUE (soal_id, urutan)
);

CREATE INDEX IF NOT EXISTS ix_chapter_module ON chapter(module_id, number);
CREATE INDEX IF NOT EXISTS ix_block_chapter_order ON block(chapter_id, reading_order);
CREATE INDEX IF NOT EXISTS ix_job_status ON job(status, id);
CREATE INDEX IF NOT EXISTS ix_job_chapter ON job(chapter_id, id);
CREATE INDEX IF NOT EXISTS ix_cp_fase ON cp(fase_id);
CREATE INDEX IF NOT EXISTS ix_quiz_request_module ON quiz_request(module_id);
CREATE INDEX IF NOT EXISTS ix_quiz_request_status ON quiz_request(status, id);
CREATE INDEX IF NOT EXISTS ix_soal_quiz_request ON soal(quiz_request_id);
CREATE INDEX IF NOT EXISTS ix_soal_chapter ON soal(chapter_id);
CREATE INDEX IF NOT EXISTS ix_soal_stimulus ON soal(stimulus_id);
CREATE INDEX IF NOT EXISTS ix_soal_opsi_soal ON soal_opsi(soal_id);
CREATE INDEX IF NOT EXISTS ix_soal_langkah_soal ON soal_langkah(soal_id);
CREATE INDEX IF NOT EXISTS ix_soal_stimulus_quiz_request ON soal_stimulus(quiz_request_id);
CREATE INDEX IF NOT EXISTS ix_soal_stimulus_chapter ON soal_stimulus(chapter_id);
