from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel, PatchModel


def _check_file_name(value: str | None) -> str | None:
    """File name only. A path, or anything that looks like one, is rejected."""
    if value is not None and any(ch in value for ch in "/\\"):
        raise ValueError("file_name must be a file name, not a path")
    return value


FileName = Annotated[str, Field(max_length=255)]


class ResumeCreate(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    focus: str | None = Field(default=None, max_length=200)
    file_name: FileName | None = None
    version: str = Field(default="1", min_length=1, max_length=50)
    notes: str | None = Field(default=None, max_length=4000)

    _file_name_ok = field_validator("file_name")(_check_file_name)


class ResumeUpdate(PatchModel):
    non_nullable = frozenset({"label", "version"})

    label: str | None = Field(default=None, min_length=1, max_length=200)
    focus: str | None = Field(default=None, max_length=200)
    file_name: FileName | None = None
    version: str | None = Field(default=None, min_length=1, max_length=50)
    notes: str | None = Field(default=None, max_length=4000)

    _file_name_ok = field_validator("file_name")(_check_file_name)


class ResumeRead(ORMModel):
    id: int
    label: str
    focus: str | None
    file_name: str | None
    version: str
    notes: str | None
