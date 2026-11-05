from typing import Annotated

from fastapi import APIRouter, Body, Depends, status

from app.core.response import COMMON_AUTH_RESPONSES, Response, get_response_message
from app.core.route import WrappedRoute
from app.core.security import CurrentUser
from app.domains.users.dependencies import get_user_service
from app.domains.users.schemas import Login, ProfileResponse
from app.domains.users.services import UserService

router_user = APIRouter(prefix="/users", tags=["users"], route_class=WrappedRoute)


@router_user.post(
    "/login",
    response_model=Response[str],
    status_code=status.HTTP_200_OK,
    responses={
        401: {
            "description": "Email or password is invalid",
        },
    },
)
async def login(
    dto: Annotated[Login, Body()],
    service: UserService = Depends(get_user_service),
):
    token = await service.login(dto)
    return Response(
        message=get_response_message(),
        data=token,
    )


@router_user.get(
    "/profile",
    response_model=Response[ProfileResponse],
    status_code=status.HTTP_200_OK,
    responses=COMMON_AUTH_RESPONSES,
)
async def profile(
    current_user: CurrentUser,
    service: UserService = Depends(get_user_service),
):
    user_id = int(current_user.sub)
    profile = await service.get_profile(user_id)
    return Response(
        message=get_response_message(),
        data=profile,
    )
