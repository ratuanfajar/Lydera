import importlib
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.exceptions import BadRequestException


@pytest.fixture(scope="module")
def client() -> TestClient:
    # app.main memasang StaticFiles pada settings.OUTPUT_DIR; direktori harus ada sebelum impor.
    Path(settings.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    main = importlib.import_module("app.main")

    app = FastAPI()
    app.add_exception_handler(StarletteHTTPException, main.http_exception_handler)
    app.add_exception_handler(main.AppException, main.app_exception_handler)
    app.add_exception_handler(RequestValidationError, main.request_validation_exception_handler)
    app.add_exception_handler(Exception, main.global_exception_handler)
    app.add_exception_handler(IntegrityError, main.sqlalchemy_integrity_exception_handler)

    @app.get("/app-error")
    async def app_error():
        raise BadRequestException("data salah", errors=[{"field": "x", "pesan": "wajib"}])

    @app.get("/app-error-tanpa-detail")
    async def app_error_without_detail():
        raise BadRequestException

    @app.get("/http-error")
    async def http_error():
        raise StarletteHTTPException(status_code=404, detail="tidak ada")

    @app.get("/validasi")
    async def validation(q: int):
        return q

    @app.get("/boom")
    async def boom():
        raise RuntimeError("detail internal jangan bocor")

    @app.get("/duplikat")
    async def duplicate():
        origin = Exception(
            'duplicate key value violates unique constraint "users_email_key"\n'
            "DETAIL:  Key (email)=(a@b.c) already exists."
        )
        raise IntegrityError("INSERT INTO users", {}, origin)

    @app.get("/integritas-lain")
    async def other_integrity():
        raise IntegrityError("INSERT INTO users", {}, Exception("foreign key violation"))

    return TestClient(app, raise_server_exceptions=False)


def test_app_exception_memakai_status_detail_dan_errors(client):
    response = client.get("/app-error")
    assert response.status_code == 400
    assert response.json() == {
        "detail": "data salah",
        "errors": [{"field": "x", "pesan": "wajib"}],
    }


def test_app_exception_tanpa_detail_memakai_detail_bawaan_kelas(client):
    response = client.get("/app-error-tanpa-detail")
    assert response.status_code == 400
    assert response.json() == {"detail": "Bad Request", "errors": None}


def test_http_exception_diteruskan_dengan_errors_none(client):
    response = client.get("/http-error")
    assert response.status_code == 404
    assert response.json() == {"detail": "tidak ada", "errors": None}


def test_request_validation_diringkas_jadi_satu_pesan_dengan_daftar_error(client):
    response = client.get("/validasi", params={"q": "bukan-angka"})
    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == "Validation failed"
    assert body["errors"] and body["errors"][0]["loc"] == ["query", "q"]


def test_exception_tak_terduga_jadi_500_tanpa_membocorkan_pesan_asli(client):
    response = client.get("/boom")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error", "errors": None}
    assert "jangan bocor" not in response.text


def test_integrity_error_duplikat_menyebut_nama_kolom(client):
    response = client.get("/duplikat")
    assert response.status_code == 409
    assert response.json() == {
        "detail": "email sudah ada. Silahkan ganti email.",
        "errors": None,
    }


def test_integrity_error_lain_jadi_400_dengan_pesan_umum(client):
    response = client.get("/integritas-lain")
    assert response.status_code == 400
    assert response.json() == {
        "detail": "Error silahkan check kembali data input.",
        "errors": None,
    }
