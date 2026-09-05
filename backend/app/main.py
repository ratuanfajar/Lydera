from fastapi import APIRouter, FastAPI, Request
import logging
from fastapi.responses import JSONResponse
from core.exceptions import AppException
from core.response import Response
from domains.cities.router import router as city_router
from domains.schools.router import router as school_router


api_router = APIRouter(prefix="/api")

api_router.include_router(city_router)
api_router.include_router(school_router)

app = FastAPI()

app.include_router(api_router)

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )

logger = logging.getLogger(__name__)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception occurred")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

@app.get("/health",response_model=Response[bool])
def health():
    return {
        "message": "Sehat",
        "data": True
        }
