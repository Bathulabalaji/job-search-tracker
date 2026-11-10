class DomainError(Exception):
    """Base class for errors the API maps to HTTP responses."""


class NotFoundError(DomainError):
    def __init__(self, entity: str, entity_id: int) -> None:
        super().__init__(f"{entity} {entity_id} not found")


class ConflictError(DomainError):
    pass
