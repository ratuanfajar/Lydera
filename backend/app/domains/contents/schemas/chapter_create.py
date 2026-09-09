from typing import Annotated, Optional

from fastapi import Form


class ChapterCreate:
    def __init__(
        self,
        module_id: Annotated[int, Form(...)],
        title: Annotated[str, Form(...)],
        cp_id: Annotated[int, Form(...)],
        number: Annotated[Optional[int], Form()] = None,
        # start_page: Annotated[int, Form(...)],
        # end_page: Annotated[int, Form(...)],
    ):
        self.module_id = module_id
        self.number = number
        self.title = title
        self.cp_id = cp_id