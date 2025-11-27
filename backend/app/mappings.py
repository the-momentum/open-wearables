from datetime import datetime
from decimal import Decimal
from typing import Annotated, NewType, TypeVar
from uuid import UUID

from pydantic import EmailStr
from sqlalchemy import DateTime, ForeignKey, Numeric, String
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
email = Annotated[EmailStr, mapped_column(String)]

str_10 = Annotated[str, mapped_column(String(10))]
str_50 = Annotated[str, mapped_column(String(50))]
str_64 = NewType("str_64", int)  # it's mapped in database.py, because it didn't work with PrimaryKey
str_100 = Annotated[str, mapped_column(String(100))]
str_255 = Annotated[str, mapped_column(String(255))]

numeric_10_3 = Annotated[Decimal, mapped_column(Numeric(10, 3))]
numeric_10_2 = Annotated[Decimal, mapped_column(Numeric(10, 2))]
numeric_15_5 = Annotated[Decimal, mapped_column(Numeric(15, 5))]

# Custom foreign keys
FKDeveloper = Annotated[UUID, mapped_column(ForeignKey("developer.id", ondelete="SET NULL"))]
FKUser = Annotated[UUID, mapped_column(ForeignKey("user.id", ondelete="CASCADE"))]
FKWorkout = Annotated[UUID, mapped_column(ForeignKey("workout.id", ondelete="CASCADE"))]
FKRecord = Annotated[UUID, mapped_column(ForeignKey("record.id", ondelete="CASCADE"))]
