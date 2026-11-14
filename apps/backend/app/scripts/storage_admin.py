"""Operator tool for uploaded files: `uv run python -m app.scripts.storage_admin <command>`

gc [--delete] [--grace-minutes N]   list stored resume files no resume refers to; with
                                    --delete, remove them. Without --delete nothing changes.
"""

import argparse
from datetime import timedelta
from zoneinfo import ZoneInfo

from app.core.clock import Clock
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.storage_gc import collect
from app.storage import build_object_store


def cmd_gc(args: argparse.Namespace) -> None:
    settings = get_settings()
    store = build_object_store(settings)
    clock = Clock(tz=ZoneInfo(settings.timezone))
    with SessionLocal() as session:
        report = collect(
            session,
            store,
            clock.now(),
            delete=args.delete,
            grace=timedelta(minutes=args.grace_minutes),
        )
    print(f"scanned {report.scanned} objects, {len(report.orphans)} orphaned")
    for key in report.orphans:
        print(("deleted  " if args.delete else "orphan   ") + key)
    if report.orphans and not args.delete:
        print("dry run: re-run with --delete to remove them")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    gc = sub.add_parser("gc")
    gc.add_argument("--delete", action="store_true")
    gc.add_argument("--grace-minutes", type=int, default=60)
    gc.set_defaults(func=cmd_gc)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
