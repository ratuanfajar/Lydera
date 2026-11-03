from typing import Annotated

from fastapi import APIRouter, Depends, Path as FastAPIPath, status

from app.core.exceptions import BadRequestException
from app.core.response import Response, get_response_message
from app.core.route import WrappedRoute
from app.core.security import Roles
from app.domains.evaluaizer.depedencies import get_evaluaizer_service
from app.domains.evaluaizer.services import EvaluaizerService
from app.domains.quizzer.schemas import QuizResultItem
from app.utils.role import Role

router_evaluaizer = APIRouter(prefix="/evaluaizer", tags=["evaluaizer"], route_class=WrappedRoute)


@router_evaluaizer.get(
    "/student/quizzes/{quiz_request_id}/results",
    description=(
        "Requires the STUDENT role. Hasil kuis siswa yang login: opsi benar, langkah_kunci, dan kesimpulan dari Quizzer "
        "selalu ada. Untuk soal yang dijawab salah DAN punya langkah tertulis siswa, letak_kesalahan (langkah_ke, kutipan, "
        "keterangan, dapat_ditentukan) biasanya sudah dievaluasi di background saat kuis selesai; bila belum, dievaluasi di sini "
        "lalu disimpan. Jawaban benar dan jawaban salah tanpa langkah tidak dianalisis (letak_kesalahan null). "
        "Soal dengan evaluasi_diproses true sedang dievaluasi proses lain: ulangi permintaan beberapa detik kemudian."
    ),
    response_model=Response[list[QuizResultItem]],
    status_code=status.HTTP_200_OK,
)
async def get_my_quiz_results(
    student: Roles(Role.STUDENT),
    quiz_request_id: Annotated[int, FastAPIPath()],
    service: EvaluaizerService = Depends(get_evaluaizer_service),
):
    try:
        results = await service.get_quiz_results(quiz_request_id, student.profile_id)
        return Response(message=get_response_message(), data=results)
    except ValueError as e:
        raise BadRequestException(str(e))
