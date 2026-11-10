from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PatchModel(BaseModel):
    """Base for PATCH bodies: omitted fields are untouched; listed fields reject explicit null."""

    non_nullable: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _reject_null_for_required_fields(self) -> Self:
        for name in self.model_fields_set & self.non_nullable:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self
