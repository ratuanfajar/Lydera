import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.core.exceptions import NotFoundException, ValidationException
from app.core.response import get_response_message
from app.core.security import decode_access_token, hash_password
from app.domains.classrooms.schemas import ClassroomInfoResponse
from app.domains.users.schemas import Login, ProfileResponse, StudentCreate, TeacherCreate
from app.domains.users.schemas.student_dashboard_request import StudentDashboardRequest
from app.domains.users.schemas.teacher_dashboard_request import TeacherDashboardRequest
from app.domains.users.services import StudentService, TeacherService, UserService
from app.utils.role import AllowedRole, Role


def run(coro):
    return asyncio.run(coro)


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class FakeTransaction:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        self.db.begins += 1
        return self.db

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.db.commits += 1
        else:
            self.db.rollbacks += 1
        return False


class FakeDb:
    def __init__(self):
        self.commits, self.rollbacks, self.begins = 0, 0, 0

    def begin(self):
        return FakeTransaction(self)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class UserRepo:
    def __init__(self, user=None, profile=None):
        self.user, self.profile = user, profile
        self.created = []

    async def get_by_email(self, email):
        return self.user

    async def get_profile(self, user_id):
        return self.profile

    async def create_user(self, dto):
        self.created.append(dto)
        return SimpleNamespace(id=5)


class TeacherRepo:
    def __init__(self, dashboard=None, fail=False):
        self.dashboard, self.fail = dashboard, fail

    async def create_teacher(self, user_id):
        if self.fail:
            raise RuntimeError("gagal membuat guru")
        return SimpleNamespace(id=11, user_id=user_id)

    async def get_dashboard(self, classroom_id, limit):
        return self.dashboard


class StudentRepo:
    def __init__(self, tasks=None, fail=False):
        self.tasks, self.fail = tasks or {}, fail

    async def create_student(self, user_id):
        if self.fail:
            raise RuntimeError("gagal membuat murid")
        return SimpleNamespace(id=21, user_id=user_id)

    async def get_task_counts(self, classroom_id, student_id):
        return self.tasks


class ClassroomRepo:
    def __init__(self, info=None):
        self.info = info

    async def get_classroom_info(self, classroom_id, profile_id, role):
        return self.info


def user(email="guru@example.com", teacher=None, student=None, password=None):
    return SimpleNamespace(id=1, email=email, password=password or PASSWORD_HASH, teacher=teacher, student=student)


PASSWORD_HASH = hash_password("rahasia123")


TEACHER_PROFILE = SimpleNamespace(id=10)
STUDENT_PROFILE = SimpleNamespace(id=20)


def login_request(role, password="rahasia123"):
    return Login(email="guru@example.com", password=password, role=role)


def classroom_info():
    return ClassroomInfoResponse(
        school_name="SMAN 1",
        code="ABC1234",
        grade_class=11,
        classroom_type="MIPA",
    )


def profile(user_id=1):
    return SimpleNamespace(
        id=user_id,
        email="guru@example.com",
        teacher=SimpleNamespace(id=10, created_at=NOW, updated_at=NOW),
        student=None,
    )


def test_login_guru_mengembalikan_token_dengan_role_dan_profile_guru():
    repo = UserRepo(user(teacher=TEACHER_PROFILE))
    service = UserService(repo, FakeDb())

    token = run(service.login(login_request(AllowedRole.TEACHER)))
    payload = decode_access_token(token)

    assert (payload.sub, payload.profile_id, payload.role) == ("1", 10, Role.TEACHER)


def test_login_siswa_mengembalikan_token_dengan_role_dan_profile_siswa():
    repo = UserRepo(user(student=STUDENT_PROFILE))
    service = UserService(repo, FakeDb())

    payload = decode_access_token(run(service.login(login_request(AllowedRole.STUDENT))))

    assert (payload.profile_id, payload.role) == (20, Role.STUDENT)


def test_login_email_yang_tidak_terdaftar_ditolak():
    service = UserService(UserRepo(user=None), FakeDb())

    with pytest.raises(ValidationException):
        run(service.login(login_request(AllowedRole.TEACHER)))


def test_login_password_salah_ditolak():
    repo = UserRepo(user(teacher=TEACHER_PROFILE, password=hash_password("password-lain")))
    service = UserService(repo, FakeDb())

    with pytest.raises(ValidationException):
        run(service.login(login_request(AllowedRole.TEACHER, password="rahasia123")))


def test_login_role_yang_tidak_sesuai_profil_ditolak():
    service = UserService(UserRepo(user(teacher=TEACHER_PROFILE)), FakeDb())

    with pytest.raises(ValidationException):
        run(service.login(login_request(AllowedRole.STUDENT)))


def test_login_user_tanpa_profil_sama_sekali_ditolak():
    service = UserService(UserRepo(user()), FakeDb())

    with pytest.raises(ValidationException):
        run(service.login(login_request(AllowedRole.TEACHER)))


def test_get_profile_mengembalikan_data_profil():
    service = UserService(UserRepo(profile=profile()), FakeDb())

    result = run(service.get_profile(1))

    assert isinstance(result, ProfileResponse)
    assert (result.id, result.email, result.teacher.id) == (1, "guru@example.com", 10)
    assert result.student is None


def test_get_profile_yang_tidak_ada_ditolak():
    service = UserService(UserRepo(profile=None), FakeDb())

    with pytest.raises(NotFoundException):
        run(service.get_profile(99))


def test_create_teacher_membuat_user_dan_guru_lalu_commit():
    db, user_repo = FakeDb(), UserRepo()
    service = TeacherService(user_repo, ClassroomRepo(), TeacherRepo(), db)

    async def scenario():
        teacher = await service.create_teacher(
            TeacherCreate(
                email="guru@example.com",
                password="rahasia123",
                confirm_password="rahasia123",
            )
        )
        return teacher, get_response_message()

    teacher, message = run(scenario())

    assert teacher.user_id == 5
    assert len(user_repo.created) == 1
    assert (db.begins, db.commits, db.rollbacks) == (1, 1, 0)
    assert message == "Berhasil membuat akun guru"


def test_create_teacher_gagal_di_tengah_di_rollback():
    db = FakeDb()
    service = TeacherService(UserRepo(), ClassroomRepo(), TeacherRepo(fail=True), db)

    with pytest.raises(RuntimeError, match="gagal membuat guru"):
        run(
            service.create_teacher(
                TeacherCreate(
                    email="guru@example.com",
                    password="rahasia123",
                    confirm_password="rahasia123",
                )
            )
        )

    assert (db.commits, db.rollbacks) == (0, 1)


def test_create_student_membuat_user_dan_murid_lalu_commit():
    db, user_repo = FakeDb(), UserRepo()
    service = StudentService(user_repo, StudentRepo(), ClassroomRepo(), db)

    async def scenario():
        student = await service.create_student(
            StudentCreate(
                email="murid@example.com",
                password="rahasia123",
                confirm_password="rahasia123",
            )
        )
        return student, get_response_message()

    student, message = run(scenario())

    assert student.user_id == 5
    assert (db.begins, db.commits, db.rollbacks) == (1, 1, 0)
    assert message == "Berhasil membuat akun murid"


def test_dashboard_guru_mengembalikan_email_kelas_dan_ringkasan():
    dashboard = {
        "total_modules": 3,
        "total_exams": 2,
        "total_students": 30,
        "newest_modules": [],
        "newest_exams": [],
    }
    service = TeacherService(UserRepo(profile=profile()), ClassroomRepo(classroom_info()), TeacherRepo(dashboard), FakeDb())

    result = run(service.dashboard_teacher(TeacherDashboardRequest(classroom_id=7), teacher_id=10, user_id=1))

    assert result.teacher_email == "guru@example.com"
    assert result.classroom_info.code == "ABC1234"
    assert (result.total_modules, result.total_exams, result.total_students) == (3, 2, 30)


def test_dashboard_guru_menolak_kelas_yang_bukan_miliknya():
    service = TeacherService(UserRepo(profile=profile()), ClassroomRepo(None), TeacherRepo({}), FakeDb())

    with pytest.raises(NotFoundException, match="tidak punya kelas"):
        run(service.dashboard_teacher(TeacherDashboardRequest(classroom_id=7), teacher_id=10, user_id=1))


def test_dashboard_guru_menolak_user_yang_bukan_guru():
    student_only = SimpleNamespace(id=1, email="murid@example.com", teacher=None, student=STUDENT_PROFILE)
    service = TeacherService(UserRepo(profile=student_only), ClassroomRepo(classroom_info()), TeacherRepo({}), FakeDb())

    with pytest.raises(NotFoundException, match="User tidak ditemukan"):
        run(service.dashboard_teacher(TeacherDashboardRequest(classroom_id=7), teacher_id=10, user_id=1))


def test_dashboard_siswa_mengembalikan_email_dan_jumlah_tugas_belum_selesai():
    student = SimpleNamespace(id=1, email="murid@example.com", teacher=None, student=STUDENT_PROFILE)
    service = StudentService(
        UserRepo(profile=student),
        StudentRepo({"modules_not_done": 4, "exam_not_done": 1}),
        ClassroomRepo(classroom_info()),
        FakeDb(),
    )

    result = run(service.dashboard_student(StudentDashboardRequest(classroom_id=7), student_id=20, user_id=1))

    assert result.student_email == "murid@example.com"
    assert (result.modules_not_done, result.exam_not_done) == (4, 1)


def test_dashboard_siswa_menolak_kelas_yang_bukan_miliknya():
    student = SimpleNamespace(id=1, email="murid@example.com", teacher=None, student=STUDENT_PROFILE)
    service = StudentService(UserRepo(profile=student), StudentRepo(), ClassroomRepo(None), FakeDb())

    with pytest.raises(NotFoundException, match="tidak punya kelas"):
        run(service.dashboard_student(StudentDashboardRequest(classroom_id=7), student_id=20, user_id=1))
