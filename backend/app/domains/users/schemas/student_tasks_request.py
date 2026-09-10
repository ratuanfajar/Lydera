from typing import Annotated

from fastapi import Query

from app.domains.users.schemas.student_dashboard_request import StudentDashboardRequest, StudentTaskStatus


class StudentTaskRequest(StudentDashboardRequest):
    status: Annotated[
            StudentTaskStatus,
            Query(
                default=StudentTaskStatus.ALL,
                examples=[StudentTaskStatus.ALL],
                description="Filter tasks by status: 'Semua', 'Materi', or 'Soal Ujian'"
            )
        ]