"""Ephemeral test-only FastAPI server for extracted mobile Playwright flows.

This is not a production fake-provider mode. It never touches real accounts,
wallets or local user databases and only runs when ECHOLOOM_TEST_SERVER=1.
"""

import os
import tempfile
from pathlib import Path

import uvicorn
from conftest import FakeImages, FakeText
from sqlalchemy import delete

from echoloom.api import create_app
from echoloom.config import Settings
from echoloom.db import Base, make_engine

if __name__ == "__main__":
    if os.environ.get("ECHOLOOM_TEST_SERVER") != "1":
        raise SystemExit("Test server only: invoke through npm run test:e2e.")
    with tempfile.TemporaryDirectory(prefix="echoloom-marketplace-e2e-") as directory:
        settings = Settings(
            _env_file=None,
            companion_worker_enabled=False,
            app_origin="http://127.0.0.1:3001",
            database_url=f"sqlite:///{directory}/test.db",
            image_directory=Path(directory) / "images",
            llm_api_key="test-only",
            llm_model="test-only",
            image_api_key="test-only",
            image_model="test-only",
        )
        engine = make_engine(settings.database_url)
        Base.metadata.create_all(engine)
        app = create_app(settings, FakeText(), FakeImages(), engine)
        print("TEST ONLY: mocked AI providers; temporary database.", flush=True)

        @app.post("/__test/reset")
        def reset():
            with engine.begin() as conn:
                for table in reversed(Base.metadata.sorted_tables):
                    conn.execute(delete(table))
            app.state.images.fail = False
            return {"reset": True}

        @app.post("/__test/image-failure/{failed}")
        def image_failure(failed: bool):
            app.state.images.fail = failed
            return {"image_failure": failed}

        uvicorn.run(app, host="127.0.0.1", port=8001)
        engine.dispose()
