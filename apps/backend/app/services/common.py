from pydantic import BaseModel


def apply_patch(target: object, patch: BaseModel) -> None:
    """Copy only the fields the client actually sent onto the ORM object."""
    for name, value in patch.model_dump(exclude_unset=True).items():
        setattr(target, name, value)
