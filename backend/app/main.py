from fastapi import APIRouter, FastAPI, Request
import logging
import app.core.model_registry
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.exceptions import AppException
from app.core.response import Response
from app.domains.cities.router import router as router_city
from app.domains.schools.router import router as router_school
from app.domains.users.router import router_user, router_student, router_teacher
from app.domains.classrooms.router import router_classrooms, router_classrooms_types



api_router = APIRouter(prefix="/api")

api_router.include_router(router_city)
api_router.include_router(router_school)
api_router.include_router(router_user)
api_router.include_router(router_student)
api_router.include_router(router_teacher)
api_router.include_router(router_classrooms_types)
api_router.include_router(router_classrooms)

app = FastAPI()

app.include_router(api_router)

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "errors": None,
        },
    )

@app.exception_handler(AppException)
async def app_exception_handler(
    request: Request,
    exc: AppException,
):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "errors": exc.errors,
        },
    )

@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation failed",
            "errors": jsonable_encoder(exc.errors()),
        },
    )

logger = logging.getLogger(__name__)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception occurred")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "errors": None,
        },
    )

@app.get("/health",response_model=Response[bool])
def health():
    return {
        "message": "Sehat",
        "data": True
        }
