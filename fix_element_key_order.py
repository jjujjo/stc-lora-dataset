#!/usr/bin/env python3
"""Fix compositional_deconstruction.elements to match musubi_tuner's CaptionVerifier rules.

Source of truth: musubi_tuner/ideogram4/caption_verifier.py (CaptionVerifier class).
  - type == "obj":  expected key order is (type, [bbox], desc, [color_palette])
                    -> "text" is NEVER allowed on obj elements.
  - type == "text": expected key order is (type, [bbox], text, desc, [color_palette])
                    -> "text" is required, placed after bbox (if present) and before desc.
  bbox / color_palette are optional and only checked when actually present.

This corrects an earlier version of this script that added "text": "" to every
element regardless of type, which is invalid for "obj" elements.

Run with --dry-run first (default); pass --apply to write changes, which also
makes a full backup of the dataset directory first.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

DATASET_DIR = Path(__file__).resolve().parent
BACKUP_DIR = DATASET_DIR.parent / "stc-lora-dataset_backup_v2"

ORDER_OBJ = ["type", "bbox", "desc", "color_palette"]
ORDER_TEXT = ["type", "bbox", "text", "desc", "color_palette"]


def fix_element(element: dict) -> tuple[dict, str]:
    """Return (new_element, action) where action in
    {"unchanged", "removed_text", "added_text", "reordered_only"}."""
    elem_type = element.get("type")

    if elem_type == "obj":
        expected_order = ORDER_OBJ
        working = dict(element)
        removed_text = "text" in working
        working.pop("text", None)
    elif elem_type == "text":
        expected_order = ORDER_TEXT
        working = dict(element)
        removed_text = False
        if "text" not in working:
            working["text"] = ""
    else:
        # Unknown/missing type: leave completely untouched, flagged separately.
        return element, "unknown_type"

    original_keys = list(element.keys())

    ordered_keys = [k for k in expected_order if k in working]
    extra_keys = [k for k in working if k not in expected_order]
    ordered_keys += extra_keys

    new_element = {k: working[k] for k in ordered_keys}

    if elem_type == "obj" and removed_text:
        action = "removed_text"
    elif elem_type == "text" and "text" not in original_keys:
        action = "added_text"
    elif original_keys != ordered_keys:
        action = "reordered_only"
    else:
        action = "unchanged"

    return new_element, action


def process_file(path: Path):
    """Return (new_data_or_None, counts_dict, is_target_schema, unknown_type_flag)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, {}, False, False

    if not isinstance(data, dict):
        return None, {}, False, False

    cd = data.get("compositional_deconstruction")
    if not isinstance(cd, dict) or "elements" not in cd or not isinstance(cd["elements"], list):
        return None, {}, False, False

    counts = {"removed_text": 0, "added_text": 0, "reordered_only": 0}
    changed = False
    unknown_type = False
    new_elements = []

    for element in cd["elements"]:
        if not isinstance(element, dict):
            new_elements.append(element)
            continue
        new_element, action = fix_element(element)
        if action == "unknown_type":
            unknown_type = True
            new_elements.append(element)
            continue
        if action != "unchanged":
            counts[action] += 1
            changed = True
        new_elements.append(new_element)

    if not changed:
        return None, counts, True, unknown_type

    new_data = dict(data)
    new_cd = dict(cd)
    new_cd["elements"] = new_elements
    new_data["compositional_deconstruction"] = new_cd
    return new_data, counts, True, unknown_type


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write changes (default is dry run)")
    parser.add_argument("--show-examples", type=int, default=3)
    args = parser.parse_args()

    json_files = sorted(DATASET_DIR.glob("*.json"))

    total_scanned = 0
    total_modified = 0
    total_skipped_non_target = 0
    total_removed_text = 0
    total_added_text = 0
    total_reordered_only = 0
    unknown_type_files = []
    examples = []
    to_write = []

    for path in json_files:
        total_scanned += 1
        new_data, counts, is_target, unknown_type = process_file(path)

        if not is_target:
            total_skipped_non_target += 1
            continue

        if unknown_type:
            unknown_type_files.append(path.name)

        if new_data is None:
            continue

        total_modified += 1
        total_removed_text += counts["removed_text"]
        total_added_text += counts["added_text"]
        total_reordered_only += counts["reordered_only"]
        to_write.append((path, new_data))

        if len(examples) < args.show_examples and counts["removed_text"] > 0:
            original = json.loads(path.read_text(encoding="utf-8"))
            examples.append((path.name, original, new_data))

    # Ensure we show at least a few examples even if none had removed_text
    if len(examples) < args.show_examples:
        for path, new_data in to_write:
            if len(examples) >= args.show_examples:
                break
            if path.name in [e[0] for e in examples]:
                continue
            original = json.loads(path.read_text(encoding="utf-8"))
            examples.append((path.name, original, new_data))

    print("=" * 60)
    print(f"{'DRY RUN' if not args.apply else 'APPLY'} - element key-order fix v2 (type-aware)")
    print("=" * 60)
    print(f"Total JSON files scanned:        {total_scanned}")
    print(f"Skipped (not target schema):     {total_skipped_non_target}")
    print(f"Files that would be modified:    {total_modified}")
    print(f"'text' removed from obj elements:{total_removed_text:>6}")
    print(f"'text' added to text elements:   {total_added_text:>6}")
    print(f"Elements reordered only:         {total_reordered_only:>6}")
    print(f"Files with unknown element type: {len(unknown_type_files)}")
    for name in unknown_type_files:
        print(f"  - {name}")
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
