from enum import Enum

from sqlalchemy import Enum as SAEnum


def enum_column[E: Enum](enum_cls: type[E]) -> SAEnum:
    """Store enum *values* as VARCHAR with a CHECK constraint (easy to migrate, unlike PG enums)."""
    return SAEnum(
        enum_cls,
        name=enum_cls.__name__.lower(),
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )
