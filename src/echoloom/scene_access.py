"""Meter generation and reveal using free plus verified per-scene grants."""
from copy import deepcopy

from fastapi import HTTPException

from .rehearsal_domain import history, sentences

FREE_SENTENCE_LIMIT = 40
UNLOCK_MESSAGE = "Story allowance exhausted. Purchase a verified unlock to continue."


def is_metered(doc):
    return not doc.get("demo", False)


def is_marketplace(doc):
    """Cast provenance, deliberately independent of AI story billing."""
    return any(a.get("source_listing_id") for a in doc.get("cast", []))


def ensure_access(db, row):
    """Compatibility hook; no browser/client can grant access here."""
    return None


def _legacy_used(doc):
    # Count unique AI-created text even if a version was forked, so forks
    # cannot recycle a 40-sentence free allocation.
    seen = set()
    count = 0
    for node in doc.get("nodes", {}).values():
        if node.get("source") not in ("ai", "demo"):
            continue
        for block in node["blocks"]:
            if not block.get("user_edited") and block["id"] not in seen:
                seen.add(block["id"])
                count += len(sentences(block["text"]))
    return count


def generated(doc):
    # Once a Scene starts the new persistent counter, forked read-prefix
    # copies and manual edits cannot change or reset its spent allowance.
    if "free_generated_sentences" in doc:
        return doc["free_generated_sentences"]
    return _legacy_used(doc)


def total_limit(db, row):
    """Never trust a limit stored in the scene document or supplied by a client."""
    if not is_metered(row.document):
        return None
    if not row.owner_id:
        return FREE_SENTENCE_LIMIT
    from .payments.orders import paid_sentence_allowance

    return FREE_SENTENCE_LIMIT + paid_sentence_allowance(db, row.id, row.owner_id)


def remaining(doc, limit=FREE_SENTENCE_LIMIT):
    if not is_metered(doc):
        return None
    return max(0, limit - generated(doc))


def check_generation(doc, limit=FREE_SENTENCE_LIMIT):
    if is_metered(doc) and remaining(doc, limit) == 0:
        raise HTTPException(402, UNLOCK_MESSAGE)


def mark_generated(doc, block):
    """After a generated block is accepted, persist its sentence debit.

    This runs in the same Scene commit as the block, so failed/no-output
    operations do not consume the allowance, and partial output does.
    """
    previous = generated(doc)
    doc["free_generated_sentences"] = previous + len(sentences(block["text"]))


def check_read(doc, requested, limit=FREE_SENTENCE_LIMIT):
    if is_metered(doc) and requested > limit:
        raise HTTPException(402, UNLOCK_MESSAGE)


def reserve(db, row, root_operation_id):
    check_generation(row.document, total_limit(db, row))
    return is_metered(row.document)


def finish(db, row, job, produced=False):
    """Generation is now charged by persisted sentence count, not job count."""
    return None


def status(db, row):
    doc = row.document
    if not is_metered(doc):
        return {
            "mode": "demo",
            "free_sentence_limit": None,
            "generated_sentences": 0,
            "free_sentences_remaining": None,
            "payment_required": False,
            "wallet_checkout_available": False,
        }
    used = generated(doc)
    limit = total_limit(db, row)
    return {
        "mode": "metered",
        "free_sentence_limit": limit,
        "generated_sentences": used,
        "free_sentences_remaining": max(0, limit - used),
        "payment_required": used >= limit,
        "wallet_checkout_available": False,
    }


def preview(doc, limit=FREE_SENTENCE_LIMIT):
    """Strip text beyond the free allowance from ALL Scene read DTOs.

    Do not trust hiding a Next line button: a raw Scene or old Job event
    could otherwise expose all generated text. This server copy retains
    only the authorized sentences of EACH branch and discards unreachable
    nodes/hidden result state. Actual durable documents are untouched.

    For newly generated Scenes the worker itself truncates at the current allowance.
    This projection additionally protects legacy scenes created earlier.
    """
    if not is_metered(doc):
        return deepcopy(doc)
    d = deepcopy(doc)
    safe_nodes = {}
    for v in d.get("versions", {}).values():
        available = limit
        final = None
        completed_blocks = set()
        for original in history(doc, v["head"]):
            if available <= 0:
                break
            filtered = []
            for block in original["blocks"]:
                if available <= 0:
                    break
                units = sentences(block["text"])
                if not units:
                    continue
                clipped = deepcopy(block)
                if len(units) > available:
                    clipped["text"] = "".join(units[:available]).rstrip()
                else:
                    completed_blocks.add(block["id"])
                filtered.append(clipped)
                available -= min(available, len(units))
            if not filtered:
                break
            node = deepcopy(original)
            node["parent"] = final
            node["blocks"] = filtered
            # Generated state attached to the original block may mention a
            # later sentence; never expose its unfiltered source derivation.
            for key in ("world_facts", "beliefs", "goals", "relationships", "threads"):
                node["state"][key] = [
                    fact for fact in node["state"][key]
                    if fact.get("source_node") not in doc["nodes"]
                    or fact.get("source_block") in completed_blocks
                ]
            safe_nodes[node["id"]] = node
            final = node["id"]
        v["head"] = final
        v["revealed"] = min(v.get("revealed", limit), limit)
    d["nodes"] = safe_nodes
    # Source excerpt and saved-state metadata can contain unrevealed text.
    if d.get("source"):
        d["source"].pop("excerpt", None)
    if d.get("result"):
        result = d["result"]
        if result.get("head") not in safe_nodes or generated(doc) > limit:
            d["result"] = None
    return d
