#!/usr/bin/env python3
"""Permanently delete images flagged in issues_report.csv, plus their sidecar files.

A row is flagged if any of these columns is True:
  is_near_duplicates_issue, is_exact_duplicates_issue, is_low_information_issue,
  is_dark_issue, is_blurry_issue, is_light_issue, is_odd_aspect_ratio_issue,
  is_odd_size_issue

For each flagged image, matching sidecar files with the same base filename but
.txt/.json extensions are also deleted, if present. No trash, no backup -
deletions are permanent.
"""

import csv
import sys
from pathlib import Path

CSV_PATH = "/root/.claude/uploads/08a41467-eece-53d2-9db5-18a5c9da906e/0ed8296c-issues_report.csv"
DATASET_DIR = Path(__file__).resolve().parent

ISSUE_COLUMNS = [
    "is_near_duplicates_issue",
    "is_exact_duplicates_issue",
    "is_low_information_issue",
    "is_dark_issue",
    "is_blurry_issue",
    "is_light_issue",
    "is_odd_aspect_ratio_issue",
    "is_odd_size_issue",
]

SIDECAR_EXTENSIONS = [".txt", ".json"]


def main():
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    path_column = reader.fieldnames[0]  # unnamed first column holding the file path

    flagged_basenames = []
    for row in rows:
        if any(row.get(col, "").strip() == "True" for col in ISSUE_COLUMNS):
            basename = Path(row[path_column].strip()).name
            flagged_basenames.append(basename)

    images_deleted = 0
    sidecars_deleted = 0
    images_not_found = 0

    for basename in flagged_basenames:
        image_path = DATASET_DIR / basename
        if not image_path.exists():
            images_not_found += 1
            continue

        image_path.unlink()
        print(f"deleted: {image_path.name}")
        images_deleted += 1

        stem = image_path.stem
        for ext in SIDECAR_EXTENSIONS:
            sidecar_path = DATASET_DIR / (stem + ext)
            if sidecar_path.exists():
                sidecar_path.unlink()
                print(f"deleted: {sidecar_path.name}")
                sidecars_deleted += 1

    remaining_images = sum(
        1
        for p in DATASET_DIR.glob("*")
        if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
    )

    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Flagged rows in CSV:         {len(flagged_basenames)}")
    print(f"Flagged images not found:    {images_not_found} (already removed in prior cleanup)")
    print(f"Images deleted:              {images_deleted}")
    print(f"Sidecar files deleted:       {sidecars_deleted}")
    print(f"Images remaining in dataset: {remaining_images}")


if __name__ == "__main__":
    sys.exit(main())
