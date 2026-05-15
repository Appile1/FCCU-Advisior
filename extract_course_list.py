"""
extract_course_list.py
----------------------
Reads every *_courses.json file in the course_data/ directory,
merges them all, and produces ONE compact file:

    course_data/latest_course_list.json

This file contains every unique course_code ever seen across all terms,
with the most-recently-seen course_name and credits preserved.
Later terms override earlier terms if the same code appears in both.

Run from the FCCU-Advisior root:
    python extract_course_list.py
"""

import json
import glob
import os

COURSE_DATA_DIR = os.path.join(os.path.dirname(__file__), "course_data")
OUT_FILENAME = "latest_course_list.json"


def main():
    pattern = os.path.join(COURSE_DATA_DIR, "*_courses.json")
    # Sort so that later terms (e.g. 2026SP > 2025FA) are processed last
    # and therefore "win" when there are duplicates.
    files = sorted(glob.glob(pattern))

    if not files:
        print(f"No *_courses.json files found in {COURSE_DATA_DIR}")
        return

    # Dict keyed by course_code so later terms naturally overwrite earlier ones
    merged: dict[str, dict] = {}
    terms_processed = []

    for filepath in files:
        basename = os.path.basename(filepath)
        print(f"  Reading: {basename}")

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        term_code = data.get("term_code", basename)
        terms_processed.append(term_code)

        for c in data.get("courses", []):
            code = (c.get("course_code") or "").strip()
            name = (c.get("course_name") or "").strip()
            credits = str(c.get("credits") or "3.00").strip()

            if not code:
                continue

            merged[code] = {"code": code, "name": name, "credits": credits}

    # Sort alphabetically
    unique_courses = sorted(merged.values(), key=lambda x: x["code"])

    result = {
        "generated_from": terms_processed,
        "total_unique_courses": len(unique_courses),
        "courses": unique_courses,
    }

    out_path = os.path.join(COURSE_DATA_DIR, OUT_FILENAME)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    total_input_kb = sum(os.path.getsize(fp) for fp in files) / 1024
    out_kb = os.path.getsize(out_path) / 1024
    reduction = (1 - out_kb / total_input_kb) * 100

    print(f"\n✓  Output : {OUT_FILENAME}")
    print(f"   Terms   : {', '.join(terms_processed)}")
    print(f"   Courses : {len(unique_courses)} unique")
    print(f"   Size    : {total_input_kb:.0f}KB (combined input) -> {out_kb:.0f}KB ({reduction:.0f}% smaller)")
    print(f"\nDone! Push course_data/{OUT_FILENAME} to GitHub.")


if __name__ == "__main__":
    main()
