"""Task-scoped visual input. Provider moderation remains unchanged."""
import json
from .schemas import Profile

def portrait_prompt(profile: Profile) -> str:
    visual = {
        "character_name": profile.name,
        "visual_style": profile.visual_style,
        "appearance": profile.appearance.model_dump(exclude_defaults=True),
    }
    return (
        "Create a single fictional character portrait based on the supplied visual profile. "
        "Respect the character identity and appearance, without depicting narrative events. "
        "Portrait composition, simple background, no text or watermark. "
        "Visual profile: " + json.dumps(visual, ensure_ascii=False)
    )
