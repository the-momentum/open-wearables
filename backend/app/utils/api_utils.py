from collections.abc import Callable
from functools import wraps
from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.utils.hateoas import get_hateoas_item, get_hateoas_list


def inline_schema_defs(schema: dict[str, Any]) -> dict[str, Any]:
    """Inline local ``#/$defs/`` references produced by ``model_json_schema()``.

    ``openapi_extra`` is embedded verbatim into the OpenAPI document, where local
    ``$defs`` refs don't resolve (validators look them up at the document root).
    Pydantic has no built-in inlining (pydantic/pydantic#12023).
    """
    defs: dict[str, Any] = schema.get("$defs", {})

    def resolve(node: Any, seen: tuple[str, ...]) -> Any:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                name = ref.removeprefix("#/$defs/")
                if name in seen:
                    raise ValueError(f"Circular $defs reference: {name}")
                if name not in defs:
                    raise ValueError(f"Unknown $defs reference: {name}")
                target = resolve(defs[name], (*seen, name))
                siblings = {key: resolve(value, seen) for key, value in node.items() if key != "$ref"}
                return {**target, **siblings}
            return {key: resolve(value, seen) for key, value in node.items() if key != "$defs"}
        if isinstance(node, list):
            return [resolve(item, seen) for item in node]
        return node

    return resolve(schema, ())


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
