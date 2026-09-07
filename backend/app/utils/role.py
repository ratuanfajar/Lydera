from enum import Enum


class Role(Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"

class AllowedRole(str, Enum):
    STUDENT = Role.STUDENT.value
    TEACHER = Role.TEACHER.value