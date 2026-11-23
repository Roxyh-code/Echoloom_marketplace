"""Opt-in real-model Marketplace acceptance against an isolated temporary DB.

Requires explicit --allow-billable flag, LLM_API_KEY and LLM_MODEL.
Produces two AI segments; schema repair attempts may make extra paid calls.
Does NOT create images, initiate Solana payments or use the normal user DB.
"""
import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from echoloom.api import create_app
from echoloom.companion_models import Account
from echoloom.config import Settings
from echoloom.db import Base, Character, ProfileRevision, make_engine, sessions
from echoloom.schemas import Profile


PRIVATE_CANARY = "SECRET_QA_FIELD_MUST_NOT_ENTER_PUBLIC_SCENES"
PREMISE = (
    "At the midnight rail station, Mira must convince Rowan to carry a "
    "sealed letter to the lighthouse before the last train departs. "
    "Neither character may open the letter."
)
DIRECTION = (
    "Let Rowan discover a handwritten warning on the OUTSIDE of the sealed "
    "letter. Mira reacts with restraint; neither person opens the letter."
)
ROLES = [
    ("Mira", "An observant archivist who values trust and speaks precisely.",
     ["Observant", "Deliberate", "Protective of trust"]),
    ("Rowan", "A skeptical lighthouse keeper who dislikes evasions and speaks plainly.",
     ["Skeptical", "Direct", "Compassionate"]),
]
RUBRIC = [
    "Distinct character voices consistent with the published public traits",
    "Second segment advances events without repeating the first",
    "Hard scene rule respected: the sealed letter stays unopened",
    "No unexplained mind-reading or invented private knowledge",
    "Language, pacing, dialogue attribution and mobile-reader quality",
]


class SmokeFailure(RuntimeError):
    pass


def check(condition, message):
    if not condition:
        raise SmokeFailure(message)


def run_command(client, scene, kind, **extra):
    response = client.post("/api/rehearsal/scenes/" + scene["id"] + "/commands",
                           json={"operation_id": str(uuid4()),
                                 "expected_revision": scene["revision"],
                                 "kind": kind, **extra})
    check(response.status_code == 200,
          f"{kind} API call failed (HTTP {response.status_code}).")
    return response.json()


def await_job(client, job_id, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        reply = client.get("/api/rehearsal/jobs/" + job_id)
        check(reply.status_code == 200, "Could not retrieve generation job.")
        job = reply.json()
        if job["status"] in ("completed", "failed", "cancelled"):
            check(job["status"] == "completed", "Generation ended as " + job["status"])
            return job
        time.sleep(0.3)
    raise SmokeFailure("Generation timed out; no additional request started.")


def text_in(scene):
    return "\n".join(
        block["text"]
        for node in scene["document"]["nodes"].values()
        for block in node["blocks"]
    )


def run_acceptance(config, *, text_provider=None, timeout_seconds=240):
    """Same production API/worker paths. text_provider injection is CI-only."""
    with tempfile.TemporaryDirectory(prefix="echoloom-liveqa-") as folder:
        root = Path(folder)
        settings = config.model_copy(update={
            "database_url": "sqlite:///" + str(root / "smoke.db"),
            "image_directory": root / "images",
            "memory_enabled": False,
            "chat_memory_enabled": False,
            "rehearsal_consistency_enabled": False,
            "companion_worker_enabled": False,
            "allow_additional_accounts": False,
        })
        report = {
            "mode": "REAL_OPENAI" if text_provider is None else "FAKE_TEST_PROVIDER",
            "model": config.llm_model if text_provider is None else "test-only",
            "checks": {},
            "generated": [],
            "manual_quality_review": [
                {"criterion": criterion, "score_1_to_5": None, "notes": ""}
                for criterion in RUBRIC
            ],
        }
        engine = make_engine(settings.database_url)
        try:
            Base.metadata.create_all(engine)
            app = create_app(settings, text_provider=text_provider, engine=engine)
            with TestClient(app) as client:
                registration = client.post(
                    "/api/account/register",
                    json={"username": "acceptance_qa", "password": uuid4().hex},
                )
                check(registration.status_code == 200, "QA account registration failed.")
                with sessions(engine)() as db:
                    account = db.scalar(
                        select(Account).where(Account.username == "acceptance_qa")
                    )
                    check(account is not None, "Isolated test account missing.")
                    character_ids = []
                    for name, description, traits in ROLES:
                        character = Character(
                            owner_id=account.id, original_description=PRIVATE_CANARY
                        )
                        db.add(character)
                        db.flush()
                        profile = Profile.model_validate({
                            "name": name,
                            "short_description": description,
                            "personality": {"core_traits": traits},
                            "backstory": PRIVATE_CANARY,
                            "private_information": PRIVATE_CANARY,
                        })
                        db.add(ProfileRevision(
                            character_id=character.id,
                            version=1,
                            profile_json=profile.model_dump(),
                            change_summary="Temporary original-character QA seed",
                        ))
                        character_ids.append(character.id)
                    db.commit()

                sources = []
                for cid, (name, description, traits) in zip(
                    character_ids, ROLES, strict=True
                ):
                    response = client.post("/api/marketplace/listings", json={
                        "character_id": cid,
                        "name": name,
                        "short_description": description,
                        "public_personality": traits,
                        "tags": ["Original", "Mystery"],
                        "rights_basis": "original",
                        "rights_confirmed": True,
                    })
                    check(response.status_code == 200,
                          "Public test listing could not be published.")
                    listing = response.json()
                    sources.append({
                        "source": "listing",
                        "listing_id": listing["listing_id"],
                        "expected_revision": listing["latest_revision"],
                    })
                report["checks"]["two_public_listings"] = True

                created = client.post("/api/rehearsal/scenes", json={
                    "operation_id": str(uuid4()),
                    "cast_sources": sources,
                    "setup": {
                        "premise": PREMISE,
                        "location": "A midnight railway platform",
                        "goal": "Decide whether Rowan accepts the delivery.",
                        "language": "en",
                        "rules": ["The letter must stay sealed."],
                    },
                })
                check(created.status_code == 201, "QA Scene creation failed.")
                scene = created.json()
                public_json = json.dumps(scene, ensure_ascii=False)
                check(PRIVATE_CANARY not in public_json,
                      "Private character data leaked into public Scene.")
                actors = scene["document"]["cast"]
                check(len(actors) == 2 and len(set(a["id"] for a in actors)) == 2,
                      "Cast must have two different actors.")
                check(all(a["source_character_id"] is None for a in actors),
                      "Private character ID exposed in public Scene.")
                report["checks"]["safe_cast_snapshot"] = True
                scene_id = scene["id"]
                allowance = client.get(
                    "/api/rehearsal/scenes/" + scene_id + "/access"
                )
                check(allowance.status_code == 200
                      and allowance.json()["mode"] == "metered"
                      and allowance.json()["free_sentence_limit"] == 40
                      and allowance.json()["generated_sentences"] == 0,
                      "The 40-sentence story preview is not available.")
                report["checks"]["40_sentence_preview_available"] = True

                for kind, values in (
                    ("continue", {}),
                    ("direction", {"text": DIRECTION}),
                ):
                    started = time.monotonic()
                    submitted = run_command(client, scene, kind, **values)
                    check(bool(submitted.get("job_id")),
                          "Generation request did not enqueue a job.")
                    job = await_job(client, submitted["job_id"], timeout_seconds)
                    scene = job["scene"]
                    prose = text_in(scene)
                    check(bool(prose.strip()), "AI returned no saved story prose.")
                    check(PRIVATE_CANARY not in json.dumps(scene, ensure_ascii=False),
                          "Private character data appeared in generated Scene.")
                    blocks = [
                        b for node in scene["document"]["nodes"].values()
                        for b in node["blocks"]
                    ]
                    valid_ids = {a["id"] for a in actors}
                    check(all(b["character_id"] is None
                              or b["character_id"] in valid_ids for b in blocks),
                          "AI output attributed a block to an unknown actor.")
                    report["generated"].append({
                        "kind": kind,
                        "duration_seconds": round(time.monotonic() - started, 2),
                        "saved_block_count": len(blocks),
                        "text": prose,
                    })
                report["checks"]["opening_and_direction_persisted"] = True

                quota = client.get(
                    "/api/rehearsal/scenes/" + scene_id + "/access"
                ).json()
                check(quota["mode"] == "metered"
                      and quota["free_sentence_limit"] == 40
                      and 0 < quota["generated_sentences"] <= 40,
                      "Expected a 40-sentence free Scene allowance.")
                report["checks"]["40_sentence_allowance_active"] = True
                # The Reader cannot reveal a sentence beyond the free cap,
                # even if one AI segment produced more than 40 sentences.
                forbidden_read = client.post(
                    "/api/rehearsal/scenes/" + scene_id + "/commands",
                    json={"operation_id": str(uuid4()),
                          "expected_revision": scene["revision"],
                          "kind": "read", "revealed": 41},
                )
                check(forbidden_read.status_code == 402,
                      "Reader permitted the 41st unpaid sentence.")
                report["checks"]["41st_sentence_requires_unlock"] = True

                saved = run_command(client, scene, "result")
                check(saved["document"]["status"] == "saved",
                      "Saving the story failed.")
                read = client.get("/api/rehearsal/scenes/" + scene_id)
                check(read.status_code == 200, "Saved story could not reopen.")
                restored = read.json()
                check(restored["document"]["result"]["head"]
                      == saved["document"]["result"]["head"],
                      "Saved result changed after reopening.")
                check(text_in(restored) == text_in(saved),
                      "Generated story text changed on reload.")
                check(PRIVATE_CANARY not in read.text,
                      "Private data leaked on saved scene reload.")
                report["checks"]["saved_story_reopens_unchanged"] = True
                report["status"] = "AUTOMATED_PASS"
        finally:
            engine.dispose()
        return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-billable", action="store_true",
                        help="Authorize exactly this run to request billable model generation.")
    parser.add_argument("--output", type=Path,
                        default=Path("work/qa/marketplace-live-acceptance.json"))
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args(argv)
    if not args.allow_billable:
        parser.error("No AI call made; use --allow-billable to opt in.")
    settings = Settings()
    if (settings.llm_provider != "openai" or not settings.llm_model
            or not settings.llm_api_key.get_secret_value()):
        parser.error("Configure LLM_PROVIDER=openai, LLM_MODEL and LLM_API_KEY first.")
    if not (30 <= args.timeout <= 600):
        parser.error("--timeout must be between 30 and 600 seconds.")
    try:
        report = run_acceptance(settings, timeout_seconds=args.timeout)
    except SmokeFailure as exc:
        print("LIVE SMOKE FAILED: " + str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        # Do not print model responses or provider exception bodies.
        print("LIVE SMOKE FAILED: " + type(exc).__name__, file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Automated acceptance passed. Human quality assessment is still needed.")
    print("Report: " + str(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
