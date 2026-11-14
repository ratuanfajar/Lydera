import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.core.exceptions import NotFoundException
from app.domains.classrooms.schemas import (
    ClassroomCreate,
    ClassroomResponse,
    ClassroomTypeResponse,
)
from app.domains.classrooms.services import ClassroomService, ClassroomTypeService
from app.utils.role import Role


def run(coro):
    return asyncio.run(coro)


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class FakeDb:
    def __init__(self):
        self.commits, self.rollbacks = 0, 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class ClassroomRepo:
    def __init__(self, classrooms=None, found=None, created=None, join_result=True, fail=None):
        self.classrooms = classrooms or []
        self.found, self.created, self.join_result, self.fail = found, created, join_result, fail
        self.calls = []

    async def create_classroom(self, dto, teacher_id):
        self.calls.append((dto, teacher_id))
        if self.fail == "create":
            raise RuntimeError("gagal membuat kelas")
        return self.created

    async def get_classrooms(self, profile_id, role):
        self.calls.append((profile_id, role))
        return self.classrooms

    async def get_classroom_by_id(self, classroom_id, profile_id, role):
        self.calls.append((classroom_id, profile_id, role))
        return self.found

    async def join_classroom(self, code, student_id):
        self.calls.append((code, student_id))
        if self.fail == "join":
            raise RuntimeError("gagal join")
        return self.join_result


class ClassroomTypeRepo:
    def __init__(self, types=None):
        self.types = types or []

    async def get_classroom_types(self):
        return self.types


def classroom_type(type_id=2, name="MIPA"):
    return SimpleNamespace(id=type_id, name=name, created_at=NOW, updated_at=NOW)


def classroom(classroom_id=7, teacher_id=10, type_id=2):
    return SimpleNamespace(
        id=classroom_id,
        teacher_id=teacher_id,
        school_id=1,
        name="Kelas 11 MIPA 1",
        code="ABC1234",
        grade=11,
        classroom_type=classroom_type(type_id),
        created_at=NOW,
        updated_at=NOW,
    )


def create_payload():
    return ClassroomCreate(name="Kelas 11 MIPA 1", classroom_type_id=2, school_id=1, grade=11)


def test_create_classroom_mengembalikan_data_dan_commit():
    db = FakeDb()
    repo = ClassroomRepo(created=classroom())
    service = ClassroomService(repo, db)

    result = run(service.create_classroom(create_payload(), teacher_id=10))

    assert isinstance(result, ClassroomResponse)
    assert (result.id, result.teacher_id, result.code) == (7, 10, "ABC1234")
    assert repo.calls[0][1] == 10
    assert (db.commits, db.rollbacks) == (1, 0)


def test_create_classroom_gagal_di_rollback_lalu_galat_diteruskan():
    db = FakeDb()
    service = ClassroomService(ClassroomRepo(fail="create"), db)

    with pytest.raises(RuntimeError, match="gagal membuat kelas"):
        run(service.create_classroom(create_payload(), teacher_id=10))

    assert (db.commits, db.rollbacks) == (0, 1)


def test_get_classrooms_mengubah_setiap_baris_menjadi_response():
    repo = ClassroomRepo(classrooms=[classroom(1), classroom(2)])
    service = ClassroomService(repo, FakeDb())

    result = run(service.get_classrooms(profile_id=10, role=Role.TEACHER))

    assert [c.id for c in result] == [1, 2]
    assert repo.calls == [(10, Role.TEACHER)]


def test_get_classrooms_kosong_menghasilkan_daftar_kosong():
    service = ClassroomService(ClassroomRepo(classrooms=[]), FakeDb())
    assert run(service.get_classrooms(profile_id=10, role=Role.TEACHER)) == []


def test_get_classroom_by_id_mengembalikan_kelas_yang_bisa_diakses():
    repo = ClassroomRepo(found=classroom())
    service = ClassroomService(repo, FakeDb())

    result = run(service.get_classroom_by_id(7, profile_id=10, role=Role.TEACHER))

    assert result.id == 7
    assert repo.calls == [(7, 10, Role.TEACHER)]


def test_get_classroom_by_id_yang_tidak_ada_atau_tanpa_akses_ditolak():
    service = ClassroomService(ClassroomRepo(found=None), FakeDb())

    with pytest.raises(NotFoundException, match="not found or you don't have access"):
        run(service.get_classroom_by_id(7, profile_id=10, role=Role.TEACHER))


def test_join_classroom_berhasil_commit():
    db, repo = FakeDb(), ClassroomRepo(join_result=True)
    service = ClassroomService(repo, db)

    assert run(service.join_classroom("ABC1234", student_id=20)) is True
    assert repo.calls == [("ABC1234", 20)]
    assert (db.commits, db.rollbacks) == (1, 0)


def test_join_classroom_dengan_kode_salah_ditolak_dan_di_rollback():
    db = FakeDb()
    service = ClassroomService(ClassroomRepo(join_result=False), db)

    with pytest.raises(NotFoundException, match="code is invalid"):
        run(service.join_classroom("SALAH", student_id=20))

    assert (db.commits, db.rollbacks) == (0, 1)


def test_join_classroom_gagal_di_repository_di_rollback():
    db = FakeDb()
    service = ClassroomService(ClassroomRepo(fail="join"), db)

    with pytest.raises(RuntimeError, match="gagal join"):
        run(service.join_classroom("ABC1234", student_id=20))

    assert (db.commits, db.rollbacks) == (0, 1)


def test_get_classroom_types_mengubah_setiap_baris_menjadi_response():
    service = ClassroomTypeService(ClassroomTypeRepo([classroom_type(1, "MIPA"), classroom_type(2, "IPS")]), FakeDb())

    result = run(service.get_classroom_types())

    assert [(t.id, t.name) for t in result] == [(1, "MIPA"), (2, "IPS")]
    assert all(isinstance(t, ClassroomTypeResponse) for t in result)
