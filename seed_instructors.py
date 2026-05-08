import json
import os
from supabase import create_client

# ================= CREDENTIALS =================
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
        "   OR paste your values directly into lines 8-9 for a quick test."
    )

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= AUTO-DETECT TERM =================
LATEST_TERM_FILE = os.path.join("course_data", "latest_term.json")

if not os.path.exists(LATEST_TERM_FILE):
    raise FileNotFoundError(
        "❌ course_data/latest_term.json not found.\n"
        "   Run bas4.py first."
    )

with open(LATEST_TERM_FILE, "r", encoding="utf-8") as f:
    latest = json.load(f)

TERM_CODE   = latest["term_code"]
TERM_NAME   = latest.get("term_name", TERM_CODE)
SOURCE_FILE = os.path.join("course_data", f"{TERM_CODE}_instructors.json")

print(f"→ Active term  : {TERM_NAME}  ({TERM_CODE})")
print(f"→ Source file  : {SOURCE_FILE}")

if not os.path.exists(SOURCE_FILE):
    raise FileNotFoundError(f"❌ {SOURCE_FILE} not found. Run bas4.py first.")

# ================= LOAD INSTRUCTORS =================
with open(SOURCE_FILE, "r", encoding="utf-8") as f:
    instructors = json.load(f)

print(f"→ Instructors in JSON: {len(instructors)}")

# ================= DETECT MULTI-DEPT INSTRUCTORS =================
# Find names that appear more than once (same person, different departments)
# e.g. "M Imran" in BIOL and "M Imran" in BIOT → two separate rows in DB
name_count = {}
for inst in instructors:
    name_count[inst["name"]] = name_count.get(inst["name"], 0) + 1

multi_dept = [inst for inst in instructors if name_count[inst["name"]] > 1]

if multi_dept:
    multi_file = os.path.join("course_data", "multi_dept_instructors.json")
    with open(multi_file, "w", encoding="utf-8") as f:
        json.dump(multi_dept, f, indent=2, ensure_ascii=False)
    print(f"→ Multi-dept instructors : {len(multi_dept)} entries saved → {multi_file}")
else:
    print("→ No multi-dept instructors found")

# ================= BUILD ROWS WITH dept_key =================
# Each row is uniquely identified by name + dept_key
# dept_key = the primary department for this entry (departments[0])
# This matches how bas4.py internally keys them as "name|dept"

rows = []
for inst in instructors:
    depts = inst.get("departments", [])
    dept_key = depts[0] if depts else ""   # primary department for this entry

    rows.append({
        "name":            inst["name"],
        "dept_key":        dept_key,
        "departments":     depts,
        "current_courses": inst.get("current_courses", []),
        "all_courses":     inst.get("all_courses", []),
    })

# ================= FETCH EXISTING ROWS =================
print("→ Fetching existing rows from Supabase...")

existing_resp = (
    supabase
    .table("instructors")
    .select("id, name, dept_key")
    .execute()
)

# lookup key: "name|dept_key" → id
existing_map = {
    f"{row['name']}|{row['dept_key']}": row["id"]
    for row in (existing_resp.data or [])
}
print(f"   Found {len(existing_map)} existing rows in Supabase")

# ================= SPLIT: UPDATE vs INSERT =================
to_insert = []
to_update = []

for row in rows:
    lookup_key = f"{row['name']}|{row['dept_key']}"

    course_patch = {
        "departments":     row["departments"],
        "current_courses": row["current_courses"],
        "all_courses":     row["all_courses"],
    }

    if lookup_key in existing_map:
        to_update.append((existing_map[lookup_key], course_patch))
    else:
        to_insert.append({
            "name":          row["name"],
            "dept_key":      row["dept_key"],
            "email":         "",       # filled manually, never overwritten
            "office":        "",
            "office_hours":  "",
            **course_patch,
        })

print(f"   {len(to_update)} rows to update  |  {len(to_insert)} new rows to insert")

# ================= BATCH INSERT =================
BATCH_SIZE = 500
inserted_count = 0

if to_insert:
    for i in range(0, len(to_insert), BATCH_SIZE):
        batch = to_insert[i : i + BATCH_SIZE]
        supabase.table("instructors").insert(batch).execute()
        inserted_count += len(batch)
        print(f"   ✅ Inserted batch {i // BATCH_SIZE + 1}  ({len(batch)} rows)")
else:
    print("   ✅ No new rows to insert")

# ================= UPDATE EXISTING ROWS =================
# ONLY updates course data — email/office/office_hours are never touched
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
print(f"   Deleted  : 0")
print("=" * 50)
