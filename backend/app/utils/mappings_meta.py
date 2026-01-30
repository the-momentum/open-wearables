from typing import Any, get_args, get_origin

from sqlalchemy.orm import Mapped, relationship
from sqlalchemy.orm.decl_api import DeclarativeAttributeIntercept

from app.mappings import ManyToOne, OneToMany, OneToOne

DEFAULT_ONE_TO_MANY = dict(cascade="all, delete-orphan", passive_deletes=True)
DEFAULT_MANY_TO_ONE = dict()
DEFAULT_ONE_TO_ONE = dict(uselist=False)
RELATION_TYPES: dict[Any, dict] = {
    ManyToOne: DEFAULT_MANY_TO_ONE,
    OneToMany: DEFAULT_ONE_TO_MANY,
    OneToOne: DEFAULT_ONE_TO_ONE,
}


class AutoRelMeta(DeclarativeAttributeIntercept):
    """Metaclass for auto-creating SQLAlchemy relationships from type annotations."""

    _registry: dict[str, dict[str, tuple[str, str]]] = {}

    def __new__(mcls, name: str, bases: tuple, namespace: dict, **kw):
        annotations = dict(namespace.get("__annotations__", {}))
        local_rels = {}

        for attr, ann in list(annotations.items()):
            if get_origin(ann) is not Mapped:
                continue

            inner = get_args(ann)[0]
            inner_origin = get_origin(inner)
            inner_args = get_args(inner)

            if inner_origin not in RELATION_TYPES or not inner_args:
                continue

            mcls._add_relation(attr, inner, namespace, local_rels)

            annotations.pop(attr, None)

        if local_rels:
            mcls._registry[name] = local_rels

        if annotations:
            namespace["__annotations__"] = annotations

        cls = super().__new__(mcls, name, bases, namespace, **kw)

        mcls._handle_back_populates(cls, local_rels)

        return cls

    @staticmethod
    def _extract_target_name(tp: Any) -> str | None:
        """Extract the string name of target class, handling ForwardRef and str literals."""
        if isinstance(tp, str):
            return tp
        if getattr(tp, "__forward_arg__", None):
            return tp.__forward_arg__
        if isinstance(tp, type):
            return tp.__name__
        return None

    @classmethod
    def _add_relation(cls, attr: str, inner: Any, namespace: dict, local_rels: dict) -> None:
        """Add relationship from inner type using registered RELATION_TYPES."""
        inner_origin = get_origin(inner)
        inner_args = get_args(inner)

        target_type = inner_args[0]
        opts = inner_args[1] if len(inner_args) > 1 and isinstance(inner_args[1], dict) else {}
        target_name = cls._extract_target_name(target_type)
        if not target_name:
            return

        options = RELATION_TYPES[inner_origin].copy()
        options.update(opts)

        namespace[attr] = relationship(target_name, **options)

        if inner_origin is OneToMany:
            kind = "one"
        elif inner_origin is ManyToOne:
            kind = "many"
        else:  # OneToOne
            kind = "single"
        local_rels[attr] = (kind, target_name)

    @classmethod
    def _handle_back_populates(cls, mapped_cls: type, local_rels: dict) -> None:
        """Optionally auto-link back_populates for opposite relations."""
        for my_attr, (my_type, target_name) in local_rels.items():
            target_rels = cls._registry.get(target_name, {})
            for tgt_attr, (tgt_type, tgt_target) in target_rels.items():
                if tgt_target == mapped_cls.__name__ and tgt_type != my_type:
                    setattr(mapped_cls, my_attr, relationship(target_name, back_populates=tgt_attr))
