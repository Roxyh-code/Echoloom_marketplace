"""Copy real Playwright captures and refresh the README's screenshot gallery.

Run after the editorial, mobile-character, marketplace and rehearsal tests.
The input PNGs must exist; missing files fail without creating broken links.
No screenshots are generated or fabricated by this script.
"""
from pathlib import Path
import argparse
import shutil

ROOT = Path(__file__).resolve().parents[1]
GROUPS = [
    ("Discover & create", [
        ("marketplace", "Discover"), ("character-library", "Character library"), ("research-create", "Research-enabled creation"),
    ]),
    ("Build a character identity", [
        ("character-detail", "Character profile"), ("research-update", "Research update"), ("voice-selection", "Voice selection & audition"),
    ]),
    ("Cast & direct a scene", [
        ("public-listing", "Public character"), ("cast", "Choose a cast"), ("story-setup", "Scene setup"),
    ]),
    ("Read, listen & revise", [
        ("voiced-reader", "Inline voice playback"), ("story-intervention", "Story direction"), ("story-review", "Story review"),
    ]),
    ("Creator economy", [
        ("listing-management", "Manage listing"), ("story-unlock", "Story unlock"), ("creator-earnings", "Creator earnings"),
    ]),
]
START = "<!-- product-gallery:start -->"
END = "<!-- product-gallery:end -->"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--screens", type=Path, default=ROOT / "web/test-results")
    parser.add_argument("--run-url", default="")
    args = parser.parse_args()
    dest = ROOT / "docs/assets/screenshots"
    readme = ROOT / "README.md"
    original = readme.read_text(encoding="utf-8")
    needed = ["editorial-" + key + ".png" for _, items in GROUPS for key, _ in items]
    for name in needed:
        p = args.screens / name
        if not p.is_file() or not p.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            raise SystemExit("Missing or invalid screenshot: " + str(p))
    dest.mkdir(parents=True, exist_ok=True)
    for name in needed:
        shutil.copyfile(args.screens / name, dest / name)
    # Keep the original four PNGs synchronized for any historical references.
    for name in ("editorial-character-creation.png", "editorial-story-reader.png"):
        if (args.screens / name).is_file():
            shutil.copyfile(args.screens / name, dest / name)

    lines = [START, "## Product gallery", "",
        "Explore the actual mobile-first application, from creating a character to directing and monetizing stories.", ""]
    for group, items in GROUPS:
        lines += ["### " + group, "", "<table>", "  <tr>"]
        for key, label in items:
            path = "docs/assets/screenshots/editorial-" + key + ".png"
            lines.append('    <td align="center"><a href="' + path + '"><img src="' + path + '" alt="' + label.replace("&","&amp;") + '" width="210" /></a></td>')
        lines += ["  </tr>", "  <tr>"]
        lines.extend('    <td align="center"><b>' + label.replace("&","&amp;") + '</b></td>' for _,label in items)
        lines += ["  </tr>", "</table>", ""]
    lines += ["<p><small>Actual Playwright screenshots of the running application using deterministic test fixtures. Research and voice screens use mocked provider responses; creator earnings shows a zero-income account and checkout is disabled. These images are not evidence of live Firecrawl research, ElevenLabs synthesis, or Solana settlement."
        + (' <a href="'+args.run_url+'">Capture run</a>.' if args.run_url else "") + "</small></p>", END]
    gallery = "\n".join(lines)
    if START in original and END in original:
        left, rest = original.split(START, 1)
        _, right = rest.split(END, 1)
        updated = left + gallery + right
    else:
        begin = original.index("<table>", original.index("</div>"))
        end = original.index("</p>", original.index('<p align="center"><small>Actual running application screenshots',begin)) + len("</p>")
        updated = original[:begin] + gallery + original[end:]
    readme.write_text(updated,encoding="utf-8")
    print("Updated", len(needed), "product screenshots.")
if __name__ == "__main__":
    main()
