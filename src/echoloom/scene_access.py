"""Meter AI generation at the server boundary for Marketplace-cast scenes.

This is *not* a payment verifier. Until Phase 4, it can grant only an account's
first free opening + one free user-directed generation. Paid credits must be
issued later by a trusted, receipt-verified backend path, never request JSON.

The account in this local prototype is not independently verified identity.
Do not market it as Sybil-resistant or publicly deploy it as-is.
"""
from fastapi import HTTPException
from sqlalchemy import select, update

from .scene_access_models import SceneAccess, SceneTrialClaim, SceneUsage


def is_marketplace(doc):
    return any(a.get("source_listing_id") for a in doc.get("cast", []))


def ensure_access(db, row):
    """Existing scenes are lazily brought under access control after migration."""
    if not is_marketplace(row.document):
        return None
    if not row.owner_id:
        raise HTTPException(401, "Sign in to use Marketplace characters.")
    access = db.get(SceneAccess, row.id)
    if access is None:
        access = SceneAccess(scene_id=row.id, account_id=row.owner_id)
        db.add(access)
        db.flush()
    if access.account_id != row.owner_id:
        raise HTTPException(404, "Scene access not found.")
    return access


def status(db, row):
    access = ensure_access(db, row)
    if access is None:
        return {
            "mode": "private",
            "opening_available": None,
            "directions_available": None,
            "opening_consumed": False,
            "trial_eligible": False,
            "payment_required": False,
        }
    db.refresh(access)
    claim = db.get(SceneTrialClaim, row.owner_id)
    eligible = claim is None or claim.scene_id == row.id
    return {
        "mode": "marketplace",
        "opening_available": access.opening_available,
        "directions_available": access.directions_available,
        "opening_consumed": access.opening_consumed,
        "trial_eligible": not access.opening_consumed and eligible,
        "payment_required": (access.directions_available == 0 if access.opening_consumed
                             else access.opening_available == 0 and not eligible),
    }


def _spend(db, scene_id, field):
    column = getattr(SceneAccess, field)
    updated = db.execute(
        update(SceneAccess)
        .where(SceneAccess.scene_id == scene_id, column > 0)
        .values({field: column - 1})
    )
    if updated.rowcount != 1:
        raise HTTPException(402, "Free story allowance exhausted. A verified unlock is required.")


def reserve(db, row, root_operation_id):
    """Atomically reserve 1 unit; caller commits with the queued generation.

    root_operation_id stays unchanged across the worker's retry attempts.
    """
    access = ensure_access(db, row)
    if access is None:
        return False
    previous = db.get(SceneUsage, str(root_operation_id))
    if previous:
        if previous.account_id != row.owner_id or previous.scene_id != row.id:
            raise HTTPException(409, "Generation allowance belongs to another scene.")
        if previous.status in ("reserved", "charged"):
            return True
        category = previous.category
    else:
        category = "direction" if access.opening_consumed else "opening"

    if category == "opening" and access.opening_consumed:
        # Only an existing charged retry may reuse the opening entitlement.
        raise HTTPException(409, "This opening has already been generated.")

    if category == "opening" and access.opening_available == 0:
        claim = db.get(SceneTrialClaim, row.owner_id)
        if claim is None:
            # Unique PK prevents concurrent cross-scene double claims at DB level.
            db.add(SceneTrialClaim(account_id=row.owner_id, scene_id=row.id))
            access.trial_granted = True
            access.opening_available = 1
            access.directions_available += 1
            db.flush()
        elif claim.scene_id != row.id:
            raise HTTPException(402, "The free story was already used. Unlock a new scene.")
    _spend(db, row.id, "opening_available" if category == "opening" else "directions_available")
    if previous:
        previous.status = "reserved"
    else:
        db.add(SceneUsage(
            operation_id=str(root_operation_id),
            scene_id=row.id,
            account_id=row.owner_id,
            category=category,
            status="reserved",
        ))
    return True


def finish(db, row, job, produced=False):
    """Commit an allowance once a usable AI block is persisted; else refund it.

    Called in the SAME transaction that saves the block or terminal job state.
    A root already charged by a partial attempt is not charged again by retry.
    """
    if not is_marketplace(row.document):
        return
    root = job.result.get("usage_root", job.id)
    usage = db.get(SceneUsage, str(root))
    if not usage or usage.status != "reserved":
        return
    if usage.scene_id != row.id or usage.account_id != row.owner_id:
        raise HTTPException(409, "Generation allowance ownership mismatch.")
    if produced:
        usage.status = "charged"
        if usage.category == "opening":
            db.execute(
                update(SceneAccess).where(SceneAccess.scene_id == row.id)
                .values(opening_consumed=True)
            )
        return

    usage.status = "refunded"
    access = ensure_access(db, row)
    if usage.category == "direction":
        db.execute(
            update(SceneAccess).where(SceneAccess.scene_id == row.id)
            .values(directions_available=SceneAccess.directions_available + 1)
        )
        return

    if access.trial_granted and not access.opening_consumed:
        # An opening that never produced a block must not burn the only trial.
        claim = db.get(SceneTrialClaim, row.owner_id)
        if claim and claim.scene_id == row.id:
            db.delete(claim)
        db.execute(
            update(SceneAccess).where(SceneAccess.scene_id == row.id)
            .values(trial_granted=False, opening_available=0, directions_available=0)
        )
    else:
        db.execute(
            update(SceneAccess).where(SceneAccess.scene_id == row.id)
            .values(opening_available=SceneAccess.opening_available + 1)
        )
