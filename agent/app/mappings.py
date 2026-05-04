from datetime import datetime
from decimal import Decimal
from typing import Annotated, TypeVar
from uuid import UUID, uuid4

from pydantic import EmailStr
from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import mapped_column

T = TypeVar("T")

# Pre-defined indexes
Indexed = Annotated[T, mapped_column(index=True)]
PrimaryKey = Annotated[T, mapped_column(primary_key=True)]

# use for composite integer primary keys (single PK int will have it auto enabled)
PKAutoIncrement = Annotated[T, mapped_column(primary_key=True, autoincrement=True)]

Unique = Annotated[T, mapped_column(unique=True)]
UniqueIndex = Annotated[T, mapped_column(index=True, unique=True)]

# Relationship types
type OneToMany[T] = list[T]
type ManyToOne[T] = T

# Custom types
datetime_tz = Annotated[datetime, mapped_column(DateTime(timezone=True))]
UUIDPrimaryKey = Annotated[UUID, mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)]
CreatedAt = Annotated[datetime, mapped_column(DateTime(timezone=True), server_default=func.now())]
UpdatedAt = Annotated[datetime, mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())]
email = Annotated[EmailStr, mapped_column(String)]

str_10 = Annotated[str, mapped_column(String(10))]
str_50 = Annotated[str, mapped_column(String(50))]
str_100 = Annotated[str, mapped_column(String(100))]
str_255 = Annotated[str, mapped_column(String(255))]

numeric_10_3 = Annotated[Decimal, mapped_column(Numeric(10, 3))]
numeric_10_2 = Annotated[Decimal, mapped_column(Numeric(10, 2))]
numeric_15_5 = Annotated[Decimal, mapped_column(Numeric(15, 5))]
