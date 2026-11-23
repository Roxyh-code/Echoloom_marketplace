"""Unified prototype story allowance: first 40 generated/revealed sentences.

All non-demo casts (private/private, mixed, public/public) use this rule.
This file cannot grant paid access: only a future server-verified wallet
receipt can enable generation and reveal beyond the free allowance.

We meter GENERATED sentences across all versions and retries, not buttons.
Read/preview/export are server-restricted to the first 40 story sentences.
Existing Scenes without a stored counter are migrated lazily from their
distinct already-persisted AI nodes. New Scenes have no account requirement
for their initial free preview; wallet/auth is required for later paid use.
"""
from copy import deepcopy

from fastapi import HTTPException

from .rehearsal_domain import history, sentences

FREE_SENTENCE_LIMIT = 40
UNLOCK_MESSAGE = (
    "The free story ends at 40 sentences. Connect a wallet and purchase "
    "a verified unlock to continue. Wallet checkout is not available yet."
)


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
    return sum(
        len(sentences(block["text"]))
        for node in doc.get("nodes", {}).values()
        if node.get("source") in ("ai", "demo")
        for block in node["blocks"]
        if not block.get("user_edited")
    )


def generated(doc):
    return max(doc.get("free_generated_sentences", 0), _legacy_used(doc))


def remaining(doc):
    if not is_metered(doc):
        return None
    return max(0, FREE_SENTENCE_LIMIT - generated(doc))


def check_generation(doc):
    if is_metered(doc) and remaining(doc) == 0:
        raise HTTPException(402, UNLOCK_MESSAGE)


def mark_generated(doc, block):
    """After a generated block is accepted, persist its sentence debit.

    This runs in the same Scene commit as the block, so failed/no-output
    operations do not consume the allowance, and partial output does.
    """
    previous = generated(doc)
    doc["free_generated_sentences"] = previous + len(sentences(block["text"]))


def check_read(doc, requested):
    if is_metered(doc) and requested > FREE_SENTENCE_LIMIT:
        raise HTTPException(402, UNLOCK_MESSAGE)


def reserve(db, row, root_operation_id):
    check_generation(row.document)
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
    return {
        "mode": "metered",
        "free_sentence_limit": FREE_SENTENCE_LIMIT,
        "generated_sentences": used,
        "free_sentences_remaining": max(0, FREE_SENTENCE_LIMIT - used),
        "payment_required": used >= FREE_SENTENCE_LIMIT,
        "wallet_checkout_available": False,
    }


def preview(doc):
    """Strip text beyond the free allowance from ALL Scene read DTOs.

    Do not trust hiding a Next line button: a raw Scene or old Job event
    could otherwise expose all generated text. This server copy retains
    only the first 40 sentences of EACH branch and discards unreachable
    nodes/hidden result state. Actual durable documents are untouched.

    For newly generated Scenes the worker itself truncates at sentence 40.
    This projection additionally protects legacy scenes created earlier.
    """
    if not is_metered(doc):
        return deepcopy(doc)
    d = deepcopy(doc)
    safe_nodes = {}
    for v in d.get("versions", {}).values():
        available = FREE_SENTENCE_LIMIT
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
        v["revealed"] = min(v.get("revealed", FREE_SENTENCE_LIMIT),
                            FREE_SENTENCE_LIMIT)
    d["nodes"] = safe_nodes
    # Source excerpt and saved-state metadata can contain unrevealed text.
    if d.get("source"):
        d["source"].pop("excerpt", None)
    if d.get("result"):
        result = d["result"]
        if result.get("head") not in safe_nodes or generated(doc) > FREE_SENTENCE_LIMIT:
            d["result"] = None
    return d
