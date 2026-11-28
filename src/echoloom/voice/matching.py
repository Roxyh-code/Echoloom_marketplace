"""Bounded, profile-conditioned ranking of existing reviewed voices."""
import json
import re
from .schemas import VoiceRanking
from ..providers import ProviderError


def character_features(profile):
    # Do not send private-information, backstory or conversation records.
    return {
        "description": profile.short_description[:500],
        "age": profile.appearance.age_description[:200],
        "traits": [v[:80] for v in profile.personality.core_traits[:10]],
        "speech_style": {"tone": profile.speech_style.tone[:200],
                         "vocabulary": profile.speech_style.vocabulary[:200],
                         "habits": [v[:80] for v in profile.speech_style.speaking_habits[:6]]},
    }


def words(value):
    return set(re.findall(r"[\w]+", value.casefold()))


def fallback_sample(profile):
    traits = " ".join([profile.short_description, profile.speech_style.tone, *profile.personality.core_traits]).casefold()
    if any(w in traits for w in ("protect", "knight", "guard", "warrior", "authoritative")):
        return "Stay close. Whatever waits beyond that door, I will not let it take you."
    if any(w in traits for w in ("playful", "quirky", "cheerful", "mischiev")):
        return "You really thought I'd leave without one last adventure? Come on, before they notice."
    if any(w in traits for w in ("reserved", "mysterious", "quiet", "cold", "stoic")):
        return "Some things are better left unspoken. But tonight, I think you deserve the truth."
    if any(w in traits for w in ("warm", "kind", "gentle", "caring")):
        return "You don't have to carry this alone. Sit with me a little longer, and we'll find a way."
    return "I thought I knew how this story would end. Then you appeared, and everything changed."


def recommend(profile, voices, provider, *, with_sample=False):
    def finish(choices, method, sample=""):
        sample = sample.strip() if sample else fallback_sample(profile)
        return (choices, method, sample) if with_sample else (choices, method)
    features = character_features(profile)
    query = words(json.dumps(features, ensure_ascii=False))
    # No invented IDs. Prefilter to a bounded shortlist, then semantic ranking.
    def score(v):
        return len(query & words(v.name + " " + v.description + " " + " ".join(v.labels.values())))
    ordered = sorted(voices, key=lambda v: (-score(v), v.voice_id))[:16]
    if len(ordered) < 3:
        return finish([], "insufficient_voices")
    by_id = {v.voice_id: v for v in ordered}
    try:
        rank = getattr(provider, "rank_voices", None)
        if rank is not None:
            candidates = [{"voice_id": v.voice_id, "name": v.name,
                "description": v.description[:300], "labels": v.labels} for v in ordered]
            result = VoiceRanking.model_validate(rank(features, candidates))
            ids = [x.voice_id for x in result.choices]
            if len(set(ids)) == 3 and all(i in by_id for i in ids):
                return finish([by_id[x.voice_id].model_dump() | {"reason": x.reason} for x in result.choices], "ai", result.sample_text)
    except (ProviderError, ValueError, TypeError):
        pass
    # Deterministic fallback, favor variety of metadata across alternatives.
    picked = [ordered[0]]
    while len(picked) < 3:
        rest = [v for v in ordered if v not in picked]
        def diversity(v):
            labels = set(v.labels.items())
            return min(len(labels.symmetric_difference(set(p.labels.items()))) for p in picked)
        picked.append(max(rest, key=lambda v: (score(v), diversity(v))))
    return finish([v.model_dump() | {"reason": "Suggested from available voice metadata."} for v in picked], "metadata")
