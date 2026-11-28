"""Server-owned creator records; no fake provider is installed in live mode."""

import json
import logging
import time
from contextlib import ExitStack
from copy import deepcopy
from threading import Event, Lock, Thread
from uuid import UUID

from fastapi import HTTPException, Request
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy import select

from .creator_domain import (
    apply_action,
    demo_output,
    generate_context,
    new_document,
    path,
    sample_cast,
)
from .creator_schemas import (
    CreatorAction,
    CreatorCharacterInput,
    CreatorCreate,
    CreatorDocument,
    CreatorImageInput,
    CreatorImport,
    CreatorOutput,
)
from .db import (
    Character,
    Conversation,
    CreatorRequest,
    CreatorWork,
    Portrait,
    ProfileRevision,
    now,
    uid,
)
from .providers import ProviderError
from .portrait_prompt import portrait_prompt
from .character_research import CharacterResearch, ResearchIdentity, ResearchError
from datetime import UTC, datetime
from .schemas import ImageInput, Profile


logger = logging.getLogger(__name__)


def references(factory, value):
    """Protect portraits/characters pinned by any active, archived or saved draft."""
    with factory() as db:
        return any(
            value in json.dumps(w.document) for w in db.scalars(select(CreatorWork))
        )


def register_creator(app, factory, locks, settings, image_render, serialize_character):
    # Single-process prototype worker. Creation requests return as soon as the
    # profile is saved; a daemon worker finishes the expensive image API call.
    # A durable queue is required before deploying this with multiple workers.
    active_portraits = {}
    active_portraits_guard = Lock()
    research_agent = CharacterResearch(settings)
    active_research = set()
    research_guard = Lock()

    def owner(request):
        return request.state.user_id

    def character(db, cid, user):
        c = db.get(Character, str(cid))
        if not c or c.owner_id != user:
            raise HTTPException(404, "Character not found.")
        return c

    def snapshot(db, c):
        r = db.scalar(
            select(ProfileRevision).where(
                ProfileRevision.character_id == c.id,
                ProfileRevision.version == c.current_profile_version,
            )
        )
        pending = next(
            (
                j
                for j in db.scalars(
                    select(CreatorRequest).where(
                        CreatorRequest.scope == "character",
                        CreatorRequest.owner_id == c.owner_id,
                        CreatorRequest.status == "pending",
                    )
                )
                if (j.result or {}).get("character_id") == c.id
            ),
            None,
        )
        return {
            "id": c.id,
            "character_id": c.id,
            "creation_job_id": pending.id if pending else None,
            "profile": Profile.model_validate(r.profile_json).model_dump(),
            "version": c.current_profile_version,
            "portrait_id": c.current_image_id,
            "portrait_url": f"/api/characters/{c.id}/images/{c.current_image_id}/file"
            if c.current_image_id
            else None,
        }

    def work(db, wid, user):
        w = db.get(CreatorWork, str(wid))
        if not w or w.owner_id != user:
            raise HTTPException(404, "Story not found.")
        return w

    def pack(w):
        return {
            "id": w.id,
            "revision": w.revision,
            "document": w.document,
            "updated_at": w.updated_at,
        }

    def record(db, rid, user, scope, payload):
        row = db.get(CreatorRequest, str(rid))
        if row and (
            row.owner_id != user or row.scope != scope or row.payload != payload
        ):
            raise HTTPException(
                409,
                "This request ID belongs to another operation. Reload before retrying.",
            )
        if not row:
            row = CreatorRequest(
                id=str(rid),
                owner_id=user,
                scope=scope,
                payload=payload,
                status="pending",
            )
            db.add(row)
            db.commit()
        return row

    def fail(db, rid, detail):
        db.rollback()
        r = db.get(CreatorRequest, str(rid))
        r.status = "failed"
        r.result = {"detail": detail}
        db.commit()

    def generate(doc, line, event):
        if doc["demo"]:
            return demo_output(doc, event["instruction"], event["operation"])
        context = generate_context(doc, line, event, settings)
        out = CreatorOutput.model_validate(app.state.text.creator(context))
        return out

    def save_doc(w, doc):
        validated = CreatorDocument.model_validate(doc).model_dump()
        if len(json.dumps(validated).encode()) > 4 * 1024 * 1024:
            raise HTTPException(
                413, "Story is too large. Export a backup and start a new story."
            )
        w.document = validated
        w.revision += 1
        w.updated_at = now()

    @app.get("/api/creator/characters")
    def characters(request: Request, archived: bool = False):
        with factory() as db:
            return [
                serialize_character(db, c) | {"archived": c.archived}
                for c in db.scalars(
                    select(Character)
                    .where(
                        Character.owner_id == owner(request),
                        Character.archived == archived,
                    )
                    .order_by(Character.updated_at.desc())
                )
            ]

    def complete_initial_portrait(rid, user, prompt, profile_ready):
        started = time.monotonic()
        try:
            # Use the same committed visual profile as regeneration.
            data = None
            image_error = None
            # Recovery: if the same request was completed and the portrait
            # already saved, never pay for another image API call.
            with factory() as check_db:
                existing_job = check_db.get(CreatorRequest, rid)
                if not existing_job or existing_job.status != "pending":
                    return
                existing_cid = (existing_job.result or {}).get("character_id")
                existing_image = (
                    check_db.scalar(
                        select(Portrait.id)
                        .where(Portrait.character_id == existing_cid)
                        .order_by(Portrait.version.asc())
                    )
                    if existing_cid else None
                )
            if not existing_image:
                try:
                    data = app.state.images.render(prompt)
                except (ProviderError, HTTPException) as exc:
                    image_error = exc.detail if isinstance(exc, HTTPException) else str(exc)
                except Exception as exc:
                    logger.warning(
                        "creator parallel image request failed type=%s", type(exc).__name__
                    )
                    image_error = "Portrait generation failed. Your character is saved."
            # Synchronize on the PROFILE COMMIT, not on the user's HTTP request.
            # If images finish first, the worker waits; if the Profile finishes
            # first, the HTTP client can immediately navigate to Character detail.
            profile_ready.wait()
            with locks.hold("creator-portrait-job:" + rid), factory() as db:
                request_job = db.get(CreatorRequest, rid)
                if (not request_job or request_job.owner_id != user
                        or request_job.status != "pending"):
                    return
                cid = (request_job.result or {}).get("character_id")
                if not cid:
                    return
                c = character(db, cid, user)
                image = db.scalar(
                    select(Portrait)
                    .where(Portrait.character_id == cid)
                    .order_by(Portrait.version.asc())
                )
                try:
                    if not image and not image_error:
                        result = image_render(
                            UUID(cid),
                            ImageInput(expected_image_id=c.current_image_id),
                            False, db,
                            prepared_data=data,
                            prepared_prompt=prompt,
                        )
                        image = db.get(Portrait, result["id"])
                    if image:
                        with locks.hold(cid):
                            db.refresh(c)
                            # Editing the Profile while its first portrait is
                            # rendering must NOT orphan the image. Only an
                            # explicit portrait selection should supersede it.
                            if c.current_image_id is None:
                                c.current_image_id = image.id
                                db.commit()
                except (ProviderError, HTTPException) as exc:
                    db.rollback()
                    image_error = (exc.detail if isinstance(exc, HTTPException)
                                   else str(exc))
                except Exception as exc:
                    db.rollback()
                    # Do not log raw provider errors, prompts or private profile.
                    logger.warning(
                        "creator portrait worker failed type=%s", type(exc).__name__
                    )
                    image_error = "Portrait generation failed. The saved character is safe."

                if image and not image_error:
                    pinned_ids = list(db.scalars(
                        select(CreatorWork.id)
                        .where(CreatorWork.owner_id == user)
                    ))
                    db.rollback()
                    for wid in pinned_ids:
                        with locks.hold("creator-work:" + wid):
                            pinned = db.get(CreatorWork, wid, populate_existing=True)
                            if not pinned:
                                continue
                            doc = deepcopy(pinned.document)
                            changed = False
                            for members in doc["casts"].values():
                                for member in members:
                                    if (
                                        member.get("creation_job_id") == rid
                                        and member["character_id"] == cid
                                        and member["version"] == 1
                                        and not member["portrait_id"]
                                    ):
                                        member["portrait_id"] = image.id
                                        member["portrait_url"] = (
                                            f"/api/characters/{cid}/images/{image.id}/file"
                                        )
                                        changed = True
                            if changed:
                                pinned.document = CreatorDocument.model_validate(
                                    doc
                                ).model_dump()
                                # The arrival of an asynchronous portrait is
                                # presentation-only. Do NOT bump the creative
                                # revision or invalidate an in-flight scene
                                # edit holding the previously fetched revision.
                                db.commit()
                request_job = db.get(CreatorRequest, rid, populate_existing=True)
                if request_job and request_job.status == "pending":
                    request_job.status = "succeeded"
                    request_job.result = {
                        **(request_job.result or {}),
                        "character_id": cid,
                        "phase": "portrait_failed" if image_error else "ready",
                        "image_error": image_error,
                    }
                    db.commit()
                logger.info(
                    "creator stage=portrait finished seconds=%.2f success=%s",
                    time.monotonic() - started, not bool(image_error),
                )
        except Exception as exc:
            # A rare DB/pinning failure must not leave a permanently pending
            # request. Preserve the profile and flag an image-only retry.
            logger.warning(
                "creator portrait completion error type=%s", type(exc).__name__
            )
            try:
                with factory() as db:
                    row = db.get(CreatorRequest, rid)
                    if row and row.owner_id == user and row.status == "pending":
                        row.status = "succeeded"
                        row.result = {
                            **(row.result or {}),
                            "character_id": (row.result or {}).get("character_id"),
                            "phase": "portrait_failed",
                            "image_error": "Portrait generation was interrupted. Your character is saved.",
                        }
                        db.commit()
            except Exception as saving_error:
                logger.warning("creator portrait recovery error type=%s",
                               type(saving_error).__name__)
        finally:
            with active_portraits_guard:
                active_portraits.pop(rid, None)

    def start_initial_portrait(rid, user, prompt):
        # Only one paid image request may be in flight for this request_id.
        with active_portraits_guard:
            if rid in active_portraits:
                return active_portraits[rid]
            ready = Event()
            active_portraits[rid] = ready
        try:
            Thread(
                target=complete_initial_portrait,
                args=(rid, user, prompt, ready),
                name="creator-portrait-" + rid[:8],
                daemon=True,
            ).start()
        except Exception:
            with active_portraits_guard:
                active_portraits.pop(rid, None)
            raise
        return ready

    def update_research(cid, user, state):
        with locks.hold(str(cid)), factory() as db:
            c=db.get(Character,str(cid))
            if not c or c.owner_id!=user or c.archived:
                return False
            current=c.research_data or {}
            if current.get("status") not in {"queued","identifying","searching","researching"}:
                return False
            c.research_data=current|state
            db.commit()
            return True

    def research_worker(cid,user,description,base_version,base_profile):
        # Separate from the portrait request record: the two workers never
        # overwrite one another's result. Existing profile stays usable.
        try:
            if not update_research(cid,user,{"status":"identifying"}):return
            identity=ResearchIdentity.model_validate(app.state.text.identify_research_character(description))
            if identity.kind!="existing_fictional" or not identity.name or not identity.work:
                update_research(cid,user,{"status":"skipped"})
                return
            lore=research_agent.cached(identity)
            if lore is None:
                with locks.hold("firecrawl-budget"), factory() as db:
                    today=datetime.now(UTC).date().isoformat()
                    runs=[r for r in db.scalars(select(CreatorRequest).where(
                        CreatorRequest.scope.in_(["character","character-research"]),
                        CreatorRequest.created_at>=today))
                        if (r.result or {}).get("research_attempted")]
                    if (len(runs)>=settings.firecrawl_daily_runs_global
                            or sum(r.owner_id==user for r in runs)>=settings.firecrawl_daily_runs_per_account):
                        update_research(cid,user,{"status":"unavailable","reason":"Daily research limit reached."})
                        return
                    db.add(CreatorRequest(id=uid(),owner_id=user,scope="character-research",
                        payload={"character_id":cid},status="succeeded",
                        result={"research_attempted":True}))
                    db.commit()
                if not update_research(cid,user,{"status":"searching"}):return
                discovered=research_agent.discover(identity)
                if not update_research(cid,user,{"status":"researching",
                        "discovered_sources":[d["url"] for d in discovered]}):return
                lore=research_agent.research(identity,discovered=discovered)
            proposed=Profile.model_validate(app.state.text.generate_researched(description,lore))
            # The initial visual identity is already used for the portrait.
            # Research is a reviewable update, not a silent identity change.
            proposal=proposed.model_dump()
            for key in ("name","appearance","visual_style"):
                proposal[key]=base_profile[key]
            update_research(cid,user,lore|{"status":"proposal","base_version":base_version,
                "proposal":Profile.model_validate(proposal).model_dump()})
        except Exception as exc:
            logger.warning("character research worker failed type=%s",type(exc).__name__)
            try:
                update_research(cid,user,{"status":"unavailable","reason":"Research unavailable. Your character is ready."})
            except Exception:
                logger.warning("character research state update failed")
        finally:
            with research_guard:
                active_research.discard(cid)

    def start_research(cid,user,description,version,profile):
        with research_guard:
            if cid in active_research:return
            active_research.add(cid)
        try:
            Thread(target=research_worker,args=(cid,user,description,version,profile),
                   name="character-research-"+cid[:8],daemon=True).start()
        except Exception:
            with research_guard:active_research.discard(cid)
            update_research(cid,user,{"status":"unavailable"})

    @app.get("/api/creator/characters/{cid}/research")
    def read_research(cid: UUID,request: Request):
        with factory() as db:
            c=character(db,cid,owner(request))
            data=c.research_data
            if data and data.get("status") in {"queued","identifying","searching","researching"}:
                with research_guard:
                    if c.id not in active_research:
                        return data|{"status":"unavailable","reason":"Research interrupted by server restart."}
            return data

    @app.post("/api/creator/characters/{cid}/research/apply")
    def apply_research(cid: UUID,request: Request):
        with locks.hold(str(cid)),factory() as db:
            c=character(db,cid,owner(request))
            data=c.research_data or {}
            if data.get("status")=="applied":
                return serialize_character(db,c)
            if c.archived or data.get("status")!="proposal":
                raise HTTPException(409,"No research update available.")
            if c.current_profile_version!=data.get("base_version"):
                raise HTTPException(409,"Profile has changed. Review the research sources without overwriting your edits.")
            p=Profile.model_validate(data["proposal"])
            version=c.current_profile_version+1
            db.add(ProfileRevision(character_id=c.id,version=version,
                profile_json=p.model_dump(),change_summary="Accepted Firecrawl research update"))
            c.current_profile_version=version
            c.updated_at=now()
            c.research_data={k:v for k,v in data.items() if k!="proposal"}|{"status":"applied","profile_version":version}
            db.commit()
            return serialize_character(db,c)

    @app.post("/api/creator/characters", status_code=201)
    def create_character(body: CreatorCharacterInput, request: Request):
        if len(body.description) > settings.max_profile_input_chars:
            raise HTTPException(
                422, "The character description exceeds the configured limit."
            )
        user = owner(request)
        rid = str(body.request_id)
        started = time.monotonic()
        with locks.hold("creator-request:" + rid), factory() as db:
            row = record(db, rid, user, "character", body.model_dump(mode="json", exclude_defaults=True))
            if row.status == "succeeded":
                return row.result
            cid = (row.result or {}).get("character_id")
            if not cid and user is None:
                from .companion_models import Account

                with locks.hold("account-bootstrap"):
                    if db.scalar(select(Account.id).limit(1)):
                        raise HTTPException(
                            401, "Please sign in before saving your character."
                        )

            profile=None
            ready=None
            try:
                if not cid:
                    if row.status == "failed":
                        row.status = "pending"
                        db.commit()
                    row.result=(row.result or {})|{"phase":"building_profile"}
                    db.commit()
                    try:
                        profile=Profile.model_validate(app.state.text.generate(body.description))
                    except ProviderError as exc:
                        saved=dict(row.result or {})
                        fail(db,rid,str(exc))
                        row=db.get(CreatorRequest,rid)
                        row.result=saved|{"detail":str(exc)}
                        db.commit()
                        raise
                    with locks.hold("account-bootstrap"):
                        from .companion_models import Account

                        if user is None and db.scalar(select(Account.id).limit(1)):
                            raise HTTPException(
                                401, "Please sign in before saving your character."
                            )
                        c = Character(owner_id=user, original_description=body.description,
                                      research_data={"status":"queued","base_version":1}
                                      if body.research and user is not None and research_agent.enabled() else None)
                        db.add(c)
                        db.flush()
                        db.add(
                            ProfileRevision(
                                character_id=c.id,
                                version=1,
                                profile_json=profile.model_dump(),
                                change_summary="Character profile creation",
                            )
                        )
                        db.add(Conversation(character_id=c.id))
                        row.result = (row.result or {}) | {"character_id": c.id, "phase": "portrait_pending"}
                        row.result = {k:v for k,v in row.result.items() if k!="research_lore"}
                        db.commit()
                        cid = c.id
                if ready is None:
                    c = character(db,cid,user)
                    p = Profile.model_validate(snapshot(db,c)["profile"])
                    ready = start_initial_portrait(rid,user,portrait_prompt(p))
                    if (c.research_data or {}).get("status")=="queued":
                        start_research(cid,user,c.original_description,c.current_profile_version,p.model_dump())
                logger.info(
                    "creator stage=profile response_seconds=%.2f portrait=background",
                    time.monotonic() - started,
                )
                return {"character_id": cid, "phase": "portrait_pending"}
            finally:
                # Wake the image worker whether Profile succeeded or failed.
                # A failed profile leaves no character for image attachment.
                if ready is not None:
                    ready.set()

    @app.get("/api/creator/jobs/{rid}")
    def job(rid: UUID, request: Request):
        with factory() as db:
            r = db.get(CreatorRequest, str(rid))
            if not r or r.owner_id != owner(request):
                raise HTTPException(404, "Job not found.")
            public_result={k:v for k,v in (r.result or {}).items() if k not in {"research_lore","research_attempted"}}
            return {"status":r.status,"result":public_result if r.result is not None else None}

    @app.get("/api/creator/characters/{cid}/portrait/status")
    def portrait_status(cid: UUID, request: Request):
        with factory() as db:
            c = character(db, cid, owner(request))
            if c.current_image_id:
                return {"state": "ready", "error": None}
            jobs = [j for j in db.scalars(select(CreatorRequest).where(
                CreatorRequest.owner_id == c.owner_id,
                CreatorRequest.scope == "character"
            ).order_by(CreatorRequest.created_at.desc()))
                if (j.result or {}).get("character_id") == c.id]
            with active_portraits_guard:
                if any(j.status == "pending" and j.id in active_portraits for j in jobs):
                    return {"state": "pending", "error": None}
            if any(j.status == "pending" for j in jobs):
                return {"state": "missing", "error": "Portrait generation was interrupted."}
            error = next(((j.result or {}).get("image_error") for j in jobs
                          if (j.result or {}).get("image_error")), None)
            return {"state": "missing", "error": error}

    @app.post("/api/creator/characters/{cid}/portrait")
    def portrait(cid: UUID, body: CreatorImageInput, request: Request):
        user = owner(request)
        rid = str(body.request_id)
        with locks.hold("creator-request:" + rid), factory() as db:
            character(db, cid, user)
            for initial in db.scalars(
                select(CreatorRequest).where(
                    CreatorRequest.owner_id == user,
                    CreatorRequest.scope == "character",
                    CreatorRequest.status == "pending",
                )
            ):
                if (initial.result or {}).get("character_id") == str(cid):
                    with active_portraits_guard:
                        if initial.id in active_portraits:
                            raise HTTPException(409,
                                "The initial portrait is still generating. Please wait before requesting another.")
                        initial.status = "succeeded"
                        initial.result = (initial.result or {}) | {
                            "phase": "portrait_failed",
                            "image_error": "Portrait generation was interrupted."}
                        db.commit()
            row = record(
                db, rid, user, "portrait:" + str(cid), body.model_dump(mode="json")
            )
            if row.status == "succeeded":
                return row.result
            if row.status == "pending" and row.result and row.result.get("started"):
                raise HTTPException(
                    409,
                    "This image request was interrupted. Check portrait history before starting another request.",
                )
            row.result = {"started": True}
            db.commit()
            try:
                result = image_render(
                    cid,
                    ImageInput(
                        instruction=body.instruction,
                        expected_image_id=body.expected_image_id,
                    ),
                    body.editing,
                    db,
                )
            except (ProviderError, HTTPException) as exc:
                fail(
                    db, rid, exc.detail if isinstance(exc, HTTPException) else str(exc)
                )
                raise
            row = db.get(CreatorRequest, rid)
            row.status = "succeeded"
            row.result = result
            db.commit()
            return result

    @app.post("/api/creator/characters/{cid}/duplicate", status_code=201)
    def duplicate_character(cid: UUID, body: CreatorImageInput, request: Request):
        user = owner(request)
        with (
            locks.hold("creator-request:" + str(body.request_id)),
            locks.hold(str(cid)),
            factory() as db,
        ):
            c = character(db, cid, user)
            job = record(
                db,
                body.request_id,
                user,
                "duplicate:" + str(cid),
                body.model_dump(mode="json"),
            )
            if job.status == "succeeded":
                return serialize_character(
                    db, character(db, job.result["character_id"], user)
                )
            original = snapshot(db, c)
            profile = deepcopy(original["profile"])
            profile["name"] = profile["name"][:50] + " · copy"
            clone = Character(
                owner_id=user, original_description=c.original_description
            )
            db.add(clone)
            db.flush()
            db.add(
                ProfileRevision(
                    character_id=clone.id,
                    version=1,
                    profile_json=profile,
                    change_summary="Duplicate character",
                )
            )
            db.add(Conversation(character_id=clone.id))
            target = None
            if c.current_image_id:
                image = db.get(Portrait, c.current_image_id)
                image_id = uid()
                source = settings.image_directory / image.file_path
                if source.is_file():
                    target = settings.image_directory / (image_id + ".png")
                    target.write_bytes(source.read_bytes())
                    db.add(
                        Portrait(
                            id=image_id,
                            character_id=clone.id,
                            parent_image_id=None,
                            provider=image.provider,
                            model=image.model,
                            prompt=image.prompt,
                            file_path=image_id + ".png",
                            version=1,
                        )
                    )
                    clone.current_image_id = image_id
            job.status = "succeeded"
            job.result = {"character_id": clone.id}
            try:
                db.commit()
            except Exception:
                if target:
                    target.unlink(missing_ok=True)
                raise
            return serialize_character(db, clone)

    @app.patch("/api/creator/characters/{cid}/archive")
    def archive_character(cid: UUID, request: Request):
        with locks.hold(str(cid)), factory() as db:
            c = character(db, cid, owner(request))
            c.archived = not c.archived
            db.commit()
            return {"archived": c.archived}

    @app.get("/api/creator/works")
    def works(request: Request):
        with factory() as db:
            return [
                pack(w)
                for w in db.scalars(
                    select(CreatorWork)
                    .where(CreatorWork.owner_id == owner(request))
                    .order_by(CreatorWork.updated_at.desc())
                )
            ]

    @app.post("/api/creator/works", status_code=201)
    def create(body: CreatorCreate, request: Request):
        user = owner(request)
        rid = str(body.request_id)
        with (
            locks.hold("creator-request:" + rid),
            locks.hold("account-bootstrap"),
            ExitStack() as stack,
            factory() as db,
        ):
            from .companion_models import Account

            if user is None and db.scalar(select(Account.id).limit(1)):
                raise HTTPException(401, "Please sign in before saving a story.")
            row = record(db, rid, user, "work", body.model_dump(mode="json"))
            if row.status == "succeeded":
                return pack(work(db, row.result["work_id"], user))
            for cid in sorted({str(c) for c in body.character_ids}):
                stack.enter_context(locks.hold(cid))
            if body.demo:
                cast = sample_cast()
            else:
                if len(set(body.character_ids)) != len(body.character_ids):
                    raise HTTPException(422, "Choose different characters.")
                expected = 1 if body.mode == "play" else 2
                if len(body.character_ids) != expected:
                    raise HTTPException(422, f"Choose {expected} character(s).")
                cast = [
                    snapshot(db, character(db, c, user)) for c in body.character_ids
                ]
                if body.mode == "play":
                    cast.append(
                        {
                            "id": "player",
                            "character_id": None,
                            "profile": Profile(
                                name=body.player_name,
                                short_description=body.player_description
                                or "Played by the author",
                            ).model_dump(),
                            "version": 1,
                            "portrait_id": None,
                            "portrait_url": None,
                        }
                    )
            d = new_document(body, cast)
            w = CreatorWork(owner_id=user, document=d)
            db.add(w)
            db.flush()
            row.status = "succeeded"
            row.result = {"work_id": w.id}
            db.commit()
            return pack(w)

    @app.get("/api/creator/works/{wid}")
    def read(wid: UUID, request: Request):
        with factory() as db:
            return pack(work(db, wid, owner(request)))

    @app.post("/api/creator/works/{wid}/actions")
    def action(wid: UUID, body: CreatorAction, request: Request):
        user = owner(request)
        rid = str(body.request_id)
        with locks.hold("creator-work:" + str(wid)), factory() as db:
            w = work(db, wid, user)
            row = record(
                db, rid, user, "work:" + str(wid), body.model_dump(mode="json")
            )
            if row.status == "succeeded":
                return pack(w)
            if w.revision != body.expected_revision:
                raise HTTPException(
                    409,
                    "This story changed in another window. Reload before retrying; your input is kept.",
                )

            def refresh_cast(cast):
                result = []
                for member in cast:
                    if member["character_id"]:
                        c = character(db, member["character_id"], user)
                        fresh = snapshot(db, c)
                        fresh["id"] = member["id"]
                        result.append(fresh)
                    else:
                        result.append(member)
                return result

            try:
                d = apply_action(w.document, body, generate, refresh_cast)
                save_doc(w, d)
                row.status = "succeeded"
                row.result = {"work_id": w.id}
                db.commit()
            except (ProviderError, HTTPException, ValueError, ValidationError) as exc:
                detail = (
                    exc.detail
                    if isinstance(exc, HTTPException)
                    else str(exc)
                    if isinstance(exc, ProviderError)
                    else "The generated story could not be validated. Your previous draft is safe."
                )
                fail(db, rid, detail)
                if isinstance(exc, (ProviderError, HTTPException)):
                    raise
                raise HTTPException(422, detail) from None
            return pack(w)

    @app.delete("/api/creator/works/{wid}", status_code=204)
    def delete(wid: UUID, request: Request):
        with locks.hold("creator-work:" + str(wid)), factory() as db:
            w = work(db, wid, owner(request))
            for previous in db.scalars(
                select(CreatorRequest).where(CreatorRequest.owner_id == owner(request))
            ):
                if (
                    previous.scope == "work:" + w.id
                    or (previous.result or {}).get("work_id") == w.id
                ):
                    previous.payload = {}
                    previous.status = "deleted"
                    previous.result = {"work_id": w.id, "deleted": True}
            db.delete(w)
            db.commit()

    @app.post("/api/creator/import", status_code=201)
    def import_work(body: CreatorImport, request: Request):
        user = owner(request)
        rid = str(body.request_id)
        if len(body.model_dump_json().encode()) > 5 * 1024 * 1024:
            raise HTTPException(413, "Backups must be smaller than 5 MiB.")
        with locks.hold("creator-request:" + rid), factory() as db:
            row = record(db, rid, user, "import", body.model_dump(mode="json"))
            if row.status == "succeeded":
                return pack(work(db, row.result["work_id"], user))
            d = body.document.model_dump()
            all_ids = (
                set(d["nodes"])
                | set(d["lines"])
                | set(d["casts"])
                | set(d["scenes"])
                | {c["id"] for c in d["checkpoints"]}
                | {f["id"] for f in d["facts"]}
            )
            ids = {key: uid() for key in all_ids}

            def map_values(value):
                if isinstance(value, dict):
                    return {
                        ids.get(k, k): map_values(v)
                        if k
                        not in (
                            "text",
                            "instruction",
                            "name",
                            "title",
                            "premise",
                            "portrait_url",
                            "character_id",
                            "portrait_id",
                            "profile",
                        )
                        else v
                        for k, v in value.items()
                    }
                if isinstance(value, list):
                    return [map_values(v) for v in value]
                return ids.get(value, value) if isinstance(value, str) else value

            d = map_values(d)
            d["title"] = d["title"][:85] + " · imported"
            for members in d["casts"].values():
                for m in members:
                    if m["character_id"]:
                        c = db.get(Character, m["character_id"])
                        image = (
                            db.get(Portrait, m["portrait_id"])
                            if m["portrait_id"]
                            else None
                        )
                        if (
                            not c
                            or c.owner_id != user
                            or (
                                m["portrait_id"]
                                and (not image or image.character_id != c.id)
                            )
                        ):
                            m.update(
                                character_id=None, portrait_id=None, portrait_url=None
                            )
            d = CreatorDocument.model_validate(d).model_dump()
            w = CreatorWork(owner_id=user, document=d)
            db.add(w)
            db.flush()
            row.status = "succeeded"
            row.result = {"work_id": w.id}
            db.commit()
            return pack(w)

    @app.get("/api/creator/works/{wid}/export")
    def export(
        wid: UUID,
        request: Request,
        format: str = "script",
        line_id: str = "",
        scene_id: str = "",
        checkpoint_id: str = "",
    ):
        if format not in ("script", "prose", "json"):
            raise HTTPException(422, "Choose script, prose or json.")
        with factory() as db:
            w = work(db, wid, owner(request))
            d = w.document
            if format == "json":
                text = json.dumps(d, ensure_ascii=False, indent=2)
                ext = "json"
                media = "application/json"
            else:
                line = d["lines"].get(line_id or d["active_line"])
                if checkpoint_id:
                    c = next(
                        (c for c in d["checkpoints"] if c["id"] == checkpoint_id), None
                    )
                    if not c:
                        raise HTTPException(404, "Saved version not found.")
                    line = c["line"]
                if not line:
                    raise HTTPException(404, "Storyline not found.")
                sections = [f"# {d['title']}", f"*{line['name']} · Draft*"]
                previous = None
                for n in path(d, line["head"]):
                    if scene_id and n["scene_id"] != scene_id:
                        continue
                    if previous != n["scene_id"]:
                        sections.append("## " + d["scenes"][n["scene_id"]]["title"])
                        previous = n["scene_id"]
                    names = {
                        m["id"]: m["profile"]["name"] for m in d["casts"][n["cast_id"]]
                    }
                    for b in n["blocks"]:
                        if b["type"] == "dialogue":
                            sections.append(
                                f"**{names[b['speaker']]}**\n\n{b['text']}"
                                if format == "script"
                                else f"{names[b['speaker']]}: “{b['text']}”"
                            )
                        elif b["type"] == "action":
                            sections.append(f"*{b['text']}*")
                        else:
                            sections.append(b["text"])
                text = "\n\n".join(sections)
                ext = "md"
                media = "text/markdown"
            return Response(
                text,
                media_type=media,
                headers={
                    "Content-Disposition": f'attachment; filename="echoloom-story.{ext}"'
                },
            )
