"""A safety net: a new repository query that forgets `user_id` would leak data between users."""

import importlib
import inspect
import pkgutil

import app.repositories as repositories_pkg
from app.repositories.base import BaseRepository

# Auth-internal repositories are looked up by secrets or ids, not by "whose data is this".
# The provider ledger is deployment-wide state (AI budgets), not user data.
UNSCOPED_ON_PURPOSE = {"app.repositories.user", "app.repositories.provider_ledger"}


def _repository_classes() -> list[type]:
    classes: list[type] = []
    for module_info in pkgutil.iter_modules(repositories_pkg.__path__):
        name = f"app.repositories.{module_info.name}"
        if name in UNSCOPED_ON_PURPOSE or module_info.name == "base":
            continue
        module = importlib.import_module(name)
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ == name:
                classes.append(cls)
    return classes


def test_every_query_in_a_per_user_repository_filters_by_user() -> None:
    offenders: list[str] = []
    classes = _repository_classes()
    assert len(classes) >= 10  # guards against the scan silently finding nothing
    for cls in classes:
        for method_name, method in inspect.getmembers(cls, inspect.isfunction):
            source = inspect.getsource(method)
            if "select(" in source and "user_id" not in source:
                offenders.append(f"{cls.__name__}.{method_name}")
    assert offenders == []


def test_per_user_repositories_inherit_the_scoped_base_or_take_a_user_id() -> None:
    for cls in _repository_classes():
        params = inspect.signature(cls).parameters
        assert issubclass(cls, BaseRepository) or "user_id" in params, cls.__name__
