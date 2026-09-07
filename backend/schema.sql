PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS module (
    id          INTEGER PRIMARY KEY,
    title       TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS chapter (
    id          INTEGER PRIMARY KEY,
    module_id   INTEGER NOT NULL REFERENCES module(id) ON DELETE CASCADE,
    number      INTEGER,
    title       TEXT,
    source_file TEXT,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS block (
    id              INTEGER PRIMARY KEY,
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
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS ix_chapter_module ON chapter(module_id, number);
CREATE INDEX IF NOT EXISTS ix_block_chapter_order ON block(chapter_id, reading_order);
