#!/usr/bin/env python3
"""Flag LoRA dataset image/caption pairs whose captions mention off-brand keywords.

Scans every .txt caption file in the dataset directory for a set of
case-insensitive keywords. Any matching pair (image + caption) is moved
(not deleted) into flagged_for_review/, preserving filenames. Safe to
re-run: files already in flagged_for_review are skipped, and files
already moved are not re-scanned as if still present.
"""

import shutil
import sys
from pathlib import Path

KEYWORDS = ["logo", "award", "laurel wreath", "trophy", "sponsor", "partner"]

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

DATASET_DIR = Path(__file__).resolve().parent
FLAGGED_DIR = DATASET_DIR / "flagged_for_review"


def find_matching_keywords(caption_text: str) -> list[str]:
    lowered = caption_text.lower()
    return [kw for kw in KEYWORDS if kw in lowered]


def find_image_for_caption(txt_path: Path) -> Path | None:
    stem = txt_path.stem
    for ext in IMAGE_EXTENSIONS:
        candidate = txt_path.with_name(stem + ext)
        if candidate.exists():
            return candidate
    return None


def main() -> None:
    FLAGGED_DIR.mkdir(exist_ok=True)

    txt_files = sorted(
        p
        for p in DATASET_DIR.glob("*.txt")
        if p.parent == DATASET_DIR  # top-level only, skip flagged_for_review itself
    )

    scanned = 0
    flagged: list[tuple[str, list[str]]] = []
    skipped_no_image: list[str] = []

    for txt_path in txt_files:
        scanned += 1
        caption_text = txt_path.read_text(encoding="utf-8", errors="replace")
        matches = find_matching_keywords(caption_text)
        if not matches:
            continue

        image_path = find_image_for_caption(txt_path)
        if image_path is None:
            skipped_no_image.append(txt_path.name)
            continue

        dest_txt = FLAGGED_DIR / txt_path.name
        dest_img = FLAGGED_DIR / image_path.name

        if not dest_txt.exists():
            shutil.move(str(txt_path), str(dest_txt))
        if not dest_img.exists():
            shutil.move(str(image_path), str(dest_img))

        flagged.append((image_path.name, matches))

    print("=" * 60)
    print("LoRA dataset cleanup summary")
    print("=" * 60)
    print(f"Total caption files scanned: {scanned}")
    print(f"Total flagged for review:    {len(flagged)}")
    if skipped_no_image:
        print(f"Captions with no matching image (skipped): {len(skipped_no_image)}")
        for name in skipped_no_image:
            print(f"  - {name}")
    print()
    if flagged:
        print("Flagged files (image, matched keywords):")
        for name, matches in flagged:
            print(f"  - {name}  [{', '.join(matches)}]")
    else:
        print("No files matched the keyword list.")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(main())
