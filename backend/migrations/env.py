# migrations/env.py
import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Make `app` importable
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.db import Base
from app.core.config import settings

# Import every domain's models so Base.metadata knows about all tables
from app.domains.users.models.user import User          # noqa
from app.domains.users.models.student import Student          # noqa
from app.domains.users.models.teacher import Teacher          # noqa
from app.domains.schools.models.school import School
from app.domains.classrooms.models.classroom import Classroom
from app.domains.cities.models.city import City          # noqa
from app.domains.contents.models.module import Module
from app.domains.contents.models.block import Block
from app.domains.contents.models.chapter import Chapter
from app.domains.contents.models.cp import Cp
from app.domains.contents.models.fase import Fase
from app.domains.contents.models.module_progress import ModuleProgress
from app.domains.contents.models.chapter_progress import ChapterProgress
from app.domains.jobs.models.job import Job
from app.domains.quizz.models.quiz_request import QuizRequest
from app.domains.quizz.models.quiz_request_chapter import QuizRequestChapter
from app.domains.quizz.models.soal import Soal
from app.domains.quizz.models.soal_langkah import SoalLangkah
from app.domains.quizz.models.soal_opsi import SoalOpsi
from app.domains.quizz.models.soal_stimulus import SoalStimulus
# add every new domain's models import here

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,   # migrations don't need pooling
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())