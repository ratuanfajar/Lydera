import pytest

from app.core.config import DEFAULT_AI_OUTPUT_DIR, Settings


REQUIRED = {
    "DB_NAME": "lydera",
    "DB_USER": "lydera",
    "DB_PASSWORD": "lydera",
    "DB_URL": "postgresql+asyncpg://lydera:lydera@localhost:5432/lydera_test",
    "REDIS_URL": "redis://localhost:6379/0",
    "APP_SECRET_KEY": "rahasia-uji",
    "JWT_ALGORITHM": "HS256",
}


def make(**overrides) -> Settings:
    return Settings(**{**REQUIRED, **overrides})


def test_nilai_bawaan_yang_tidak_bergantung_lingkungan():
    cfg = make()
    assert (cfg.APP_NAME, cfg.APP_VERSION) == ("Lydera", "1.0.0")
    assert cfg.APP_DESCRIPTION == "Backend untuk Lydera"


def test_kwargs_menimpa_variabel_lingkungan(monkeypatch):
    monkeypatch.setenv("DB_NAME", "dari_env")
    assert make(DB_NAME="dari_kwargs").DB_NAME == "dari_kwargs"


def test_variabel_lingkungan_dipakai_bila_tidak_diberi_kwargs(monkeypatch):
    monkeypatch.setenv("DB_HOST", "db.internal")
    assert make().DB_HOST == "db.internal"


def test_nilai_numerik_dari_string_dikonversi_ke_int():
    cfg = make(PORT="9090", EMBEDDING_DIM="1024", ACCESS_TOKEN_EXPIRE_DAY="2")
    assert (cfg.PORT, cfg.EMBEDDING_DIM, cfg.ACCESS_TOKEN_EXPIRE_DAY) == (9090, 1024, 2)


def test_kunci_lingkungan_yang_tidak_dikenal_diabaikan():
    cfg = make(TIDAK_DIKENAL="x")
    assert not hasattr(cfg, "TIDAK_DIKENAL")


def test_database_url_sama_dengan_db_url_pada_app_env_test(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    assert make().DATABASE_URL == REQUIRED["DB_URL"]


def test_database_url_pada_app_env_testing_memakai_db_url_dari_lingkungan(monkeypatch):
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("DB_URL", "postgresql+asyncpg://env/db")
    assert make().DATABASE_URL == "postgresql+asyncpg://env/db"


def test_output_dir_bisa_ditimpa():
    assert make(OUTPUT_DIR="/tmp/keluaran-uji").OUTPUT_DIR == "/tmp/keluaran-uji"


def test_output_dir_bawaan_menunjuk_ke_folder_annoter():
    assert DEFAULT_AI_OUTPUT_DIR.parent.name == "annoter"
    assert DEFAULT_AI_OUTPUT_DIR.name == "output"
