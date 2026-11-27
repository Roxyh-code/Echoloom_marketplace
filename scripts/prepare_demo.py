"""Create a dedicated local demo DB or prepare a metered checkout scene."""
import argparse
import json
from pathlib import Path
from alembic.config import Config
from alembic import command

from echoloom.db import make_engine, sessions
from echoloom.payments.demo_seed import seed_accounts, prepare_scene


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init", "scene"])
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--confirm-disposable-demo", action="store_true")
    args = parser.parse_args()
    if not args.confirm_disposable_demo:
        parser.error("Use only a separate disposable demo database.")
    path = args.db.resolve()
    if args.action == "init" and path.exists():
        parser.error("Refusing to overwrite an existing database.")
    if args.action == "scene" and not path.is_file():
        parser.error("Demo database does not exist.")
    url = "sqlite:///" + path.as_posix()
    if args.action == "init":
        path.parent.mkdir(parents=True, exist_ok=True)
        # Explicit URL via Alembic environment; never migrate the normal DB.
        import os
        os.environ["DATABASE_URL"] = url
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        command.upgrade(config, "head")
    engine = make_engine(url)
    try:
        with sessions(engine)() as db:
            result = seed_accounts(db) if args.action == "init" else prepare_scene(db)
            print(json.dumps(result, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
