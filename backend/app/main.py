import sys
from contextlib import asynccontextmanager
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import paths

paths.setup()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import db
from app.routers import blocks, chapters, fase, modules, quiz, soal


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Lydera Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(modules.router)
app.include_router(chapters.router)
app.include_router(blocks.router)
app.include_router(fase.router)
app.include_router(quiz.router)
app.include_router(soal.router)


@app.get("/health")
def health():
    return {"status": "ok"}
