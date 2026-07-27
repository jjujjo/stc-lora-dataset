#!/usr/bin/env python3
"""Permanently delete images flagged in issues_report.csv, plus their sidecar files.

Usage (PowerShell, from inside the dataset folder):
    python delete_flagged_images_local.py
    python delete_flagged_images_local.py C:\\path\\to\\issues_report.csv
    python delete_flagged_images_local.py C:\\path\\to\\issues_report.csv C:\\path\\to\\dataset_folder

If no arguments are given, it looks for issues_report.csv in the same
folder as this script, and treats that same folder as the dataset
directory.

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
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def main():
    script_dir = Path(__file__).resolve().parent
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else script_dir / "issues_report.csv"
    dataset_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else script_dir

    if not csv_path.exists():
        print(f"ERROR: CSV not found at {csv_path}")
        sys.exit(1)
    if not dataset_dir.is_dir():
        print(f"ERROR: dataset folder not found at {dataset_dir}")
        sys.exit(1)

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    path_column = reader.fieldnames[0]  # unnamed first column holding the file path

    flagged_basenames = []
    for row in rows:
        if any(row.get(col, "").strip() == "True" for col in ISSUE_COLUMNS):
            raw_path = row[path_column].strip().replace("\\", "/")
            basename = raw_path.rsplit("/", 1)[-1]
            flagged_basenames.append(basename)

    images_deleted = 0
    sidecars_deleted = 0
    images_not_found = 0

    for basename in flagged_basenames:
        image_path = dataset_dir / basename
        if not image_path.exists():
            images_not_found += 1
            continue

        image_path.unlink()
        print(f"deleted: {image_path.name}")
        images_deleted += 1

        stem = image_path.stem
        for ext in SIDECAR_EXTENSIONS:
            sidecar_path = dataset_dir / (stem + ext)
            if sidecar_path.exists():
                sidecar_path.unlink()
                print(f"deleted: {sidecar_path.name}")
                sidecars_deleted += 1

    remaining_images = sum(
        1
        for p in dataset_dir.glob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )

    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"CSV used:                    {csv_path}")
    print(f"Dataset folder:              {dataset_dir}")
    print(f"Flagged rows in CSV:         {len(flagged_basenames)}")
    print(f"Flagged images not found:    {images_not_found}")
    print(f"Images deleted:              {images_deleted}")
    print(f"Sidecar files deleted:       {sidecars_deleted}")
    print(f"Images remaining in dataset: {remaining_images}")


if __name__ == "__main__":
    sys.exit(main())
