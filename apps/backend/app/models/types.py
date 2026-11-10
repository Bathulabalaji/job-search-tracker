from enum import Enum

from sqlalchemy import Enum as SAEnum


def enum_column[E: Enum](enum_cls: type[E], name: str | None = None) -> SAEnum:
    """Store enum *values* as VARCHAR with a CHECK constraint (easy to migrate, unlike PG enums).

    Pass `name` when a table has two columns of the same enum (constraint names must differ).
    """
    return SAEnum(
        enum_cls,
        name=name or enum_cls.__name__.lower(),
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )
