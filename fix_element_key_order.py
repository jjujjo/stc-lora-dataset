#!/usr/bin/env python3
"""Fix compositional_deconstruction.elements key order/missing 'text' in caption JSON files.

Musubi Tuner's Ideogram 4 caption verifier expects each element dict to have
keys in the exact order: "type", "text", "desc". This script scans every
per-image caption JSON in the dataset directory and:
  - adds "text": "" where missing
  - reorders keys to exactly type, text, desc (any extra keys kept after, in
    their original relative order)

Only files whose top-level shape matches the expected schema
(compositional_deconstruction.elements) are touched; other JSON files
(e.g. import_data.json, dataset_ready.json) are skipped and reported
separately. Run with --dry-run first (default); pass --apply to write
changes, which also makes a full backup of the dataset directory first.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

DATASET_DIR = Path(__file__).resolve().parent
BACKUP_DIR = DATASET_DIR.parent / "stc-lora-dataset_backup"

REQUIRED_ORDER = ["type", "text", "desc"]


def fix_element(element: dict) -> tuple[dict, bool, bool]:
    """Return (new_element, text_was_added, was_reordered)."""
    text_added = "text" not in element
    working = dict(element)
    if text_added:
        working["text"] = ""

    original_keys = list(element.keys())
    new_keys = [k for k in REQUIRED_ORDER if k in working]
    extra_keys = [k for k in working if k not in REQUIRED_ORDER]
    ordered_keys = new_keys + extra_keys

    new_element = {k: working[k] for k in ordered_keys}
    was_reordered = (not text_added) and (original_keys != ordered_keys)

    return new_element, text_added, was_reordered


def process_file(path: Path):
    """Return (new_data_or_None, text_added_count, reordered_count, is_target_schema)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, 0, 0, False

    if not isinstance(data, dict):
        return None, 0, 0, False

    cd = data.get("compositional_deconstruction")
    if not isinstance(cd, dict) or "elements" not in cd or not isinstance(cd["elements"], list):
        return None, 0, 0, False

    text_added_count = 0
    reordered_count = 0
    changed = False
    new_elements = []

    for element in cd["elements"]:
        if not isinstance(element, dict):
            new_elements.append(element)
            continue
        new_element, text_added, was_reordered = fix_element(element)
        if text_added:
            text_added_count += 1
            changed = True
        elif was_reordered:
            reordered_count += 1
            changed = True
        new_elements.append(new_element)

    if not changed:
        return None, 0, 0, True

    new_data = dict(data)
    new_cd = dict(cd)
    new_cd["elements"] = new_elements
    new_data["compositional_deconstruction"] = new_cd
    return new_data, text_added_count, reordered_count, True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write changes (default is dry run)")
    parser.add_argument("--show-examples", type=int, default=3)
    args = parser.parse_args()

    json_files = sorted(DATASET_DIR.glob("*.json"))

    total_scanned = 0
    total_modified = 0
    total_skipped_non_target = 0
    total_text_added = 0
    total_reordered_only = 0
    examples = []
    to_write = []

    for path in json_files:
        total_scanned += 1
        new_data, text_added, reordered, is_target = process_file(path)

        if not is_target:
            total_skipped_non_target += 1
            continue

        if new_data is None:
            continue  # target schema, but nothing needed fixing

        total_modified += 1
        total_text_added += text_added
        total_reordered_only += reordered
        to_write.append((path, new_data))

        if len(examples) < args.show_examples:
            original = json.loads(path.read_text(encoding="utf-8"))
            examples.append((path.name, original, new_data))

    print("=" * 60)
    print(f"{'DRY RUN' if not args.apply else 'APPLY'} - element key-order fix")
    print("=" * 60)
    print(f"Total JSON files scanned:        {total_scanned}")
    print(f"Skipped (not target schema):     {total_skipped_non_target}")
    print(f"Files that would be modified:    {total_modified}")
    print(f"Elements with 'text' added:      {total_text_added}")
    print(f"Elements reordered only:         {total_reordered_only}")
    print()

    if not args.apply:
        print(f"--- Example before/after diffs (showing {len(examples)}) ---")
        for name, before, after in examples:
            print(f"\n[{name}]")
            print("BEFORE:")
            print(json.dumps(before, indent=2, ensure_ascii=False))
            print("AFTER:")
            print(json.dumps(after, indent=2, ensure_ascii=False))
        print()
        print("Dry run only — no files written. Re-run with --apply to write changes.")
        return

    print(f"Backing up dataset directory to: {BACKUP_DIR}")
    if BACKUP_DIR.exists():
        print(f"ERROR: backup directory already exists at {BACKUP_DIR}, refusing to overwrite.")
        sys.exit(1)
    shutil.copytree(DATASET_DIR, BACKUP_DIR, ignore=shutil.ignore_patterns(".git"))
    print("Backup complete.")

    for path, new_data in to_write:
        path.write_text(json.dumps(new_data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {len(to_write)} updated JSON files.")


if __name__ == "__main__":
    sys.exit(main())
