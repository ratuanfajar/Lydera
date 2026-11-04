from fastapi import APIRouter, Depends, status

from app.core.response import Response
from app.core.route import WrappedRoute
from app.domains.classrooms.depedencies import get_classroom_type_service
from app.domains.classrooms.schemas import ClassroomTypeResponse
from app.domains.classrooms.services import ClassroomTypeService

router_classrooms_types = APIRouter(
    prefix="/classroom-types",
    tags=["classroom-types"],
    route_class=WrappedRoute,
)


@router_classrooms_types.get(
    "",
    description="Get a list of all available classroom types. Publicly accessible.",
    response_model=Response[list[ClassroomTypeResponse]],
    status_code=status.HTTP_200_OK,
)
async def get_list_classroom_types(
    service: ClassroomTypeService = Depends(get_classroom_type_service),
):
    types = await service.get_classroom_types()
    return Response(
        data=types,
        message="Classroom types retrieved successfully",
    )
