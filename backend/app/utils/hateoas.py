from app.config import settings
from app.database import BaseDbModel
from app.utils.conversion import base_to_dict


def _build_query(base_url: str, name: str, inst_id: str | None = "") -> str:
    return f"{base_url}{settings.api_latest}/{name}s/{inst_id}"


def _generate_item_links(
    built_url: str,
    url: str,
    extra_rels: list[dict] | None = None,
) -> list[dict[str, str]]:
    links = [
        {"rel": "self", "href": url},
        {"rel": "update", "href": built_url, "method": "PUT"},
        {"rel": "delete", "href": built_url, "method": "DELETE"},
    ]
    if extra_rels:
        for relation in extra_rels:
            link = {}
            link["rel"] = relation.get("rel")
            link["href"] = built_url + relation.get("endpoint", "")
            link["method"] = relation.get("method")
            links.append(link)
            if overwrite := relation.get("overwrite"):
                links = [lnk for lnk in links if lnk.get("rel") != overwrite]
    return links


def _generate_collection_links(
    page: int,
    limit: int,
    base_url: str,
) -> list[dict[str, str]]:
    links = [
        {"rel": "self", "href": f"{base_url}?page={page}&limit={limit}", "method": "GET"},
        {"rel": "next", "href": f"{base_url}?page={page + 1}&limit={limit}", "method": "GET"},
    ]
    if page > 1:
        links.append({"rel": "prev", "href": f"{base_url}?page={page - 1}&limit={limit}"})
    return links


def get_hateoas_item(
    instance: BaseDbModel,
    base_url: str,
    url: str,
    extra_rels: list[dict] | None = None,
) -> dict[str, str | None | list[dict[str, str]]]:
    name = instance.__tablename__
    inst_id = instance.id_str
    built_url = _build_query(base_url, name, inst_id)
    return {
        **base_to_dict(instance),
        "_links": _generate_item_links(built_url, url, extra_rels),
    }


def get_hateoas_list(
    items: list[BaseDbModel],
    page: int,
    limit: int,
    base_url: str,
) -> dict[str, list[dict[str, str]]]:
    name = items[0].__tablename__ if len(items) else ""
    built_url = _build_query(base_url, name)
    return {
        "items": [base_to_dict(item) for item in items],
        "_links": _generate_collection_links(page, limit, built_url),
    }
