from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.testclient import TestClient

from app.core.response import set_response_message
from app.core.route import WrappedRoute


def make_client() -> TestClient:
    app = FastAPI()
    router = APIRouter(route_class=WrappedRoute)

    @router.get("/dict")
    async def plain_dict():
        return {"nilai": 1}

    @router.get("/pesan")
    async def custom_message():
        set_response_message("Berhasil membuat akun guru")
        return {"ok": True}

    @router.get("/sudah-dibungkus")
    async def already_wrapped():
        return {"message": "khusus", "data": 1}

    @router.get("/teks", response_class=PlainTextResponse)
    async def plain_text():
        return "halo"

    @router.post("/created")
    async def created():
        return JSONResponse(status_code=201, content={"nilai": 2})

    app.include_router(router)
    return TestClient(app)


def test_body_dict_dibungkus_dengan_pesan_bawaan_success():
    response = make_client().get("/dict")
    assert response.status_code == 200
    assert response.json() == {"message": "success", "data": {"nilai": 1}}


def test_pesan_khusus_dari_set_response_message_dipakai():
    response = make_client().get("/pesan")
    assert response.json() == {"message": "Berhasil membuat akun guru", "data": {"ok": True}}


def test_pesan_kustom_tidak_terbawa_ke_request_berikutnya():
    client = make_client()
    client.get("/pesan")
    assert client.get("/dict").json()["message"] == "success"


def test_body_yang_sudah_punya_message_dan_data_tidak_dibungkus_ulang():
    response = make_client().get("/sudah-dibungkus")
    assert response.json() == {"message": "khusus", "data": 1}


def test_response_non_json_dilewatkan_tanpa_dibungkus():
    response = make_client().get("/teks")
    assert response.text == "halo"
    assert response.headers["content-type"].startswith("text/plain")


def test_status_code_dari_response_json_dipertahankan():
    response = make_client().post("/created")
    assert response.status_code == 201
    assert response.json() == {"message": "success", "data": {"nilai": 2}}
