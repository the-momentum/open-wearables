from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from typing import Annotated, NewType, TypeVar
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Numeric
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

# Custom types
datetime_tz = Annotated[datetime, mapped_column(DateTime(timezone=True))]
date_col = Annotated[date_type, mapped_column(Date)]

# it's mapped in database.py, because it didn't work with PrimaryKey/Unique
email = NewType("email", str)
str_10 = NewType("str_10", str)
str_32 = NewType("str_32", str)
str_50 = NewType("str_50", str)
str_64 = NewType("str_64", str)
str_100 = NewType("str_100", str)
str_255 = NewType("str_255", str)

numeric_5_2 = Annotated[Decimal, mapped_column(Numeric(5, 2))]
numeric_10_3 = Annotated[Decimal, mapped_column(Numeric(10, 3))]
numeric_10_2 = Annotated[Decimal, mapped_column(Numeric(10, 2))]
numeric_15_5 = Annotated[Decimal, mapped_column(Numeric(15, 5))]

# Custom foreign keys
FKDeveloper = Annotated[UUID, mapped_column(ForeignKey("developer.id", ondelete="SET NULL"))]
FKUser = Annotated[UUID, mapped_column(ForeignKey("user.id", ondelete="CASCADE"))]
UniqueFkUser = Annotated[UUID, mapped_column(ForeignKey("user.id", ondelete="CASCADE"), unique=True)]
FKEventRecord = Annotated[
    UUID,
    mapped_column(ForeignKey("event_record.id", ondelete="CASCADE"), primary_key=True),
]
FKEventRecordDetail = Annotated[
    UUID,
    mapped_column(ForeignKey("event_record_detail.record_id", ondelete="CASCADE"), primary_key=True),
]
FKExternalMapping = Annotated[
    UUID,
    mapped_column(ForeignKey("external_device_mapping.id", ondelete="CASCADE")),
]
FKSeriesTypeDefinition = Annotated[
    int,
    mapped_column(ForeignKey("series_type_definition.id", ondelete="RESTRICT")),
]
FKDevice = Annotated[UUID, mapped_column(ForeignKey("device.id", ondelete="CASCADE"))]
