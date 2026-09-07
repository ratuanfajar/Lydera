import json
from typing import Callable

from fastapi import Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from app.core.response import get_response_message, _response_message


class WrappedRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_handler = super().get_route_handler()

        async def custom_handler(request: Request) -> Response:
            token = _response_message.set("success")
            try:
                response = await original_handler(request)

                if not isinstance(response, JSONResponse):
                    return response

                body = json.loads(response.body)

                if isinstance(body, dict) and "data" in body and "message" in body:
                    return response

                wrapped = {
                    "message": get_response_message(),
                    "data": body,
                }
                return JSONResponse(
                    content=jsonable_encoder(wrapped),
                    status_code=response.status_code,
                )
            finally:
                _response_message.reset(token)

        return custom_handler