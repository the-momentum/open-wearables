from decimal import Decimal
from typing import Annotated, Any, TypeVar
from uuid import UUID

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

T = TypeVar("T")

# Pre-defined indexes
Indexed = Annotated[T, mapped_column(index=True)]
PrimaryKey = Annotated[T, mapped_column(primary_key=True)]
PKAutoIncrement = Annotated[
    T,
    mapped_column(primary_key=True, autoincrement=True),
]  # use for composite integer primary keys (single PK int will have it auto enabled)
Unique = Annotated[T, mapped_column(unique=True)]

# Relationship types
type OneToMany[T] = list[T]
type ManyToOne[T] = T
type OneToOne[T] = T

# Custom types
json_binary = Annotated[list[dict[str, Any]], mapped_column(JSONB)]
email = Annotated[str, mapped_column(String)]
str_10 = Annotated[str, mapped_column(String(10))]
str_32 = Annotated[str, mapped_column(String(32))]
str_50 = Annotated[str, mapped_column(String(50))]
str_64 = Annotated[str, mapped_column(String(64))]
str_100 = Annotated[str, mapped_column(String(100))]
str_255 = Annotated[str, mapped_column(String(255))]
numeric_5_2 = Annotated[Decimal, mapped_column(Numeric(5, 2))]
numeric_6_3 = Annotated[Decimal, mapped_column(Numeric(6, 3))]
numeric_10_3 = Annotated[Decimal, mapped_column(Numeric(10, 3))]
numeric_10_2 = Annotated[Decimal, mapped_column(Numeric(10, 2))]
numeric_15_5 = Annotated[Decimal, mapped_column(Numeric(15, 5))]

# Custom foreign keys
FKDeveloper = Annotated[UUID, mapped_column(ForeignKey("developer.id", ondelete="SET NULL"))]
FKUser = Annotated[UUID, mapped_column(ForeignKey("user.id", ondelete="CASCADE"))]
FKEventRecord = Annotated[
    UUID,
    mapped_column(ForeignKey("event_record.id", ondelete="CASCADE"), primary_key=True),
]
FKEventRecordDetail = Annotated[
    UUID,
    mapped_column(ForeignKey("event_record_detail.record_id", ondelete="CASCADE"), primary_key=True),
]
FKDataSource = Annotated[
    UUID,
    mapped_column(ForeignKey("data_source.id", ondelete="CASCADE")),
]
FKUserConnection = Annotated[
    UUID | None,
    mapped_column(ForeignKey("user_connection.id", ondelete="SET NULL"), nullable=True),
]
FKSeriesTypeDefinition = Annotated[
    int,
    mapped_column(ForeignKey("series_type_definition.id", ondelete="RESTRICT")),
]
