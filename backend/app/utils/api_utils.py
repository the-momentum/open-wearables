from collections.abc import Callable
from functools import wraps

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.utils.hateoas import get_hateoas_item, get_hateoas_list


def format_response(extra_rels: list[dict] = [], status_code: int = 200) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> JSONResponse:
            if not (request := kwargs.get("request")):
                raise ValueError("Request object not found in kwargs")

            base_url = str(request.base_url).rstrip("/")
            full_url = str(request.url)
            result = await func(*args, **kwargs)
            if type(result) is list:
                page = kwargs["page"]
                limit = kwargs["limit"]
                formatted = get_hateoas_list(result, page, limit, base_url)
            else:
                formatted = get_hateoas_item(result, base_url, full_url, extra_rels)
            return JSONResponse(content=jsonable_encoder(formatted), status_code=status_code)

        return wrapper

    return decorator
