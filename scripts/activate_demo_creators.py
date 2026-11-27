"""Explicit local operator tool for two existing Devnet demo listings."""
import argparse
import json
from pathlib import Path
from uuid import UUID

from echoloom.db import make_engine, sessions
from echoloom.payments.creator_demo import activate_demo_pair


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path, help="Existing migrated local SQLite demo DB")
    parser.add_argument("--listing", required=True, action="append", type=UUID)
    parser.add_argument("--confirm-devnet-demo-consent", action="store_true")
    args = parser.parse_args()
    if not args.confirm_devnet_demo_consent:
        parser.error("Explicit consent from both creators and Devnet-only use required")
    if not args.db.is_file():
        parser.error("Database must already exist")
    engine = make_engine("sqlite:///" + args.db.resolve().as_posix())
    try:
        with sessions(engine)() as db:
            try:
                result = activate_demo_pair(db, [str(x) for x in args.listing])
                db.commit()
            except ValueError as exc:
                db.rollback()
                parser.error(str(exc))
        print(json.dumps(result, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
