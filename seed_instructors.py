import json
import os
from supabase import create_client

# ================= CREDENTIALS =================
# For local runs: fill these in directly OR create a .env file and use python-dotenv
# For GitHub Actions: these come from repository secrets automatically
#
# Option A — Direct (local dev only, do NOT commit with real values):
# SUPABASE_URL = "https://xxxx.supabase.co"
# SUPABASE_KEY = "eyJhbGci..."   # service_role key (NOT anon key)
#
# Option B — Environment variables (recommended, works for both local & CI):
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "❌ Missing credentials.\n"
        "   Set SUPABASE_URL and SUPABASE_KEY environment variables.\n"
        "   Local: create a .env file and run:  python -m dotenv run python seed_instructors.py\n"
        "   OR paste your values directly into this script (lines 12-13) for a quick test."
    )

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= AUTO-DETECT TERM =================
# bas4.py always writes latest_term.json after every scrape.
# We read it here so there's NO hardcoded term code anywhere in this script.
LATEST_TERM_FILE = os.path.join("course_data", "latest_term.json")

if not os.path.exists(LATEST_TERM_FILE):
    raise FileNotFoundError(
        "❌ course_data/latest_term.json not found.\n"
        "   Run bas4.py first to scrape and generate this file."
    )

with open(LATEST_TERM_FILE, "r", encoding="utf-8") as f:
    latest = json.load(f)

TERM_CODE   = latest["term_code"]                          # e.g. "2026FA"
TERM_NAME   = latest.get("term_name", TERM_CODE)          # e.g. "Fall 2026"
SOURCE_FILE = os.path.join("course_data", f"{TERM_CODE}_instructors.json")

print(f"→ Active term  : {TERM_NAME}  ({TERM_CODE})")
print(f"→ Source file  : {SOURCE_FILE}")

if not os.path.exists(SOURCE_FILE):
    raise FileNotFoundError(
        f"❌ {SOURCE_FILE} not found.\n"
        f"   Run bas4.py first to generate the instructor data for {TERM_CODE}."
    )

# ================= LOAD INSTRUCTORS =================
with open(SOURCE_FILE, "r", encoding="utf-8") as f:
    instructors = json.load(f)

print(f"→ Instructors in JSON: {len(instructors)}")

# ================= FETCH EXISTING ROWS =================
# One call to get all existing names → id mapping (O(1) lookup later)
print("→ Fetching existing rows from Supabase...")

existing_resp = (
    supabase
    .table("instructors")
    .select("id, name")
    .execute()
)

# name → id  (exact match)
existing_map = {row["name"]: row["id"] for row in (existing_resp.data or [])}
print(f"   Found {len(existing_map)} existing rows in Supabase")

# ================= SPLIT: UPDATE vs INSERT =================
to_insert = []
to_update = []   # list of (id, patch_dict)

for inst in instructors:
    # Only course-related fields — contact info is NEVER touched on update
    course_patch = {
        "departments":     inst.get("departments", []),
        "current_courses": inst.get("current_courses", []),
        "all_courses":     inst.get("all_courses", []),
    }

    if inst["name"] in existing_map:
        to_update.append((existing_map[inst["name"]], course_patch))
    else:
        to_insert.append({
            "name":          inst["name"],
            "email":         "",       # blank — filled manually later
            "office":        "",
            "office_hours":  "",
            **course_patch,
        })

print(f"   {len(to_update)} rows to update  |  {len(to_insert)} new rows to insert")

# ================= BATCH INSERT (new instructors) =================
BATCH_SIZE = 500
inserted_count = 0

if to_insert:
    for i in range(0, len(to_insert), BATCH_SIZE):
        batch = to_insert[i : i + BATCH_SIZE]
        supabase.table("instructors").insert(batch).execute()
        inserted_count += len(batch)
        print(f"   ✅ Inserted batch {i // BATCH_SIZE + 1}  ({len(batch)} rows)")
else:
    print("   ✅ No new instructors to insert")

# ================= UPDATE EXISTING ROWS =================
# Updates ONLY: departments, current_courses, all_courses
# NEVER updates: email, office, office_hours
updated_count = 0

for row_id, patch in to_update:
    supabase.table("instructors").update(patch).eq("id", row_id).execute()
    updated_count += 1

# ================= SUMMARY =================
print()
print("=" * 50)
print(f"✅ Sync complete for {TERM_NAME} ({TERM_CODE})")
print(f"   Inserted : {inserted_count}")
print(f"   Updated  : {updated_count}  (email/office/office_hours preserved)")
print(f"   Deleted  : 0  (no rows ever deleted)")
print("=" * 50)
