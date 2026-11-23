"""Ephemeral test-only FastAPI server for extracted mobile Playwright flows.

This is not a production fake-provider mode. It never touches real accounts,
wallets or local user databases and only runs when ECHOLOOM_TEST_SERVER=1.
"""

import os
import tempfile
from threading import Event
from pathlib import Path

import uvicorn
from conftest import FakeImages, FakeText
from io import BytesIO
from PIL import Image
from echoloom.schemas import Profile
from echoloom.rehearsal_schema import Performance, Block
from sqlalchemy import delete

from echoloom.api import create_app
from echoloom.config import Settings
from echoloom.db import Base, make_engine

class ShowcaseText(FakeText):
    """Deterministic scripted profile for one demo recording, never production AI."""

    def generate(self, description):
        self.calls.append(("generate", description))
        return Profile.model_validate({
            "name": "Kael Ashford",
            "short_description": "A silver-haired strategist who leads the city's underground network.",
            "appearance": {
                "age_description": "A man in his late twenties",
                "hair": "Silver-white, swept back",
                "eyes": "Gray-violet",
                "clothing": "Tailored black suit and a dark burgundy coat"
            },
            "personality": {
                "core_traits": ["Composed", "Calculating", "Protective"],
                "values": ["Loyalty", "Duty", "Keeping his promises"]
            },
            "wants": "Keep his people safe without exposing the underground network.",
            "why_it_matters": "One wrong decision could endanger everyone he protects.",
            "fear": "Betraying the trust of the people who depend on him.",
            "backstory": "Once a royal intelligence officer, Kael now leads a clandestine network beneath a moonlit city.",
            "speech_style": {"tone": "Quiet, deliberate, dry wit"},
            "visual_style": "Anime",
        })


class BrowserText(FakeText):
    """Can produce an oversized reply to test the server's 40-line clamp."""

    long_story = False

    def rehearsal(self, context):
        if self.long_story:
            return Performance(blocks=[
                Block(type="narration", character_id=None,
                      text=" ".join(f"QA sentence {i}." for i in range(1, 47)))
            ])
        return super().rehearsal(context)


class ShowcaseImages(FakeImages):
    """Demo art comes from an existing licensed-to-this-repo static sample."""

    def render(self, prompt, source=None):
        self.sources.append(source)
        image = Image.open("web/public/portraits/leo.webp").convert("RGB")
        output = BytesIO()
        image.resize((400, 600)).save(output, format="PNG")
        return output.getvalue()


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
        demo_mode = os.environ.get("ECHOLOOM_RECORD_DEMO") == "1"
        app = create_app(
            settings,
            ShowcaseText() if demo_mode else BrowserText(),
            ShowcaseImages() if demo_mode else FakeImages(),
            engine,
        )
        # Delay image output on demand to prove character profiles return
        # without waiting for a slow provider. Never used outside test server.
        image_gate = Event()
        image_gate.set()
        original_image_render = app.state.images.render

        def gated_image_render(prompt, source=None):
            if not image_gate.wait(timeout=20):
                raise RuntimeError("Timed out waiting for E2E image release")
            return original_image_render(prompt, source)

        app.state.images.render = gated_image_render
        print("TEST ONLY: mocked AI providers; temporary database.", flush=True)
        if demo_mode:
            print("SHOWCASE MODE: scripted profile + repository portrait asset.", flush=True)

        @app.post("/__test/reset")
        def reset():
            image_gate.set()
            with engine.begin() as conn:
                for table in reversed(Base.metadata.sorted_tables):
                    conn.execute(delete(table))
            app.state.images.fail = False
            if hasattr(app.state.text, "long_story"):
                app.state.text.long_story = False
            return {"reset": True}

        @app.post("/__test/long-story/{enabled}")
        def long_story(enabled: bool):
            if hasattr(app.state.text, "long_story"):
                app.state.text.long_story = enabled
            return {"long_story": enabled}

        @app.post("/__test/image-failure/{failed}")
        def image_failure(failed: bool):
            app.state.images.fail = failed
            return {"image_failure": failed}

        @app.post("/__test/image-delay/{enabled}")
        def image_delay(enabled: bool):
            if enabled:
                image_gate.clear()
            else:
                image_gate.set()
            return {"image_delay": enabled}

        uvicorn.run(app, host="127.0.0.1", port=8001)
        engine.dispose()
