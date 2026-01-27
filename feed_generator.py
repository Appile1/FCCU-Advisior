import json
import os
import datetime
import shutil

# ================= CONFIG =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "course_data")
FEED_FILE = os.path.join(DATA_DIR, "feed_events.json")
PREVIOUS_STATE_FILE = os.path.join(DATA_DIR, "previous_state.json")
LATEST_TERM_FILE = os.path.join(DATA_DIR, "latest_term.json")
MAX_FEED_ITEMS = 50

# ================= FILTERS =================
# We only care about:
# 1. Seats > 0 (when previously <= 0)
# 2. New section added
# 3. Instructor changed (from TBD or one name to another)
# 4. Schedule changed

def load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return None

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_latest_term_code():
    data = load_json(LATEST_TERM_FILE)
    if not data:
        return None
    # Support multiple formats just in case
    return data.get("term_code") or data.get("term") or data.get("latest_term")

def normalize_course_data(courses_list):
    """
    Convert list of courses to a dict keyed by 'unique' identifier.
    """
    return {c["unique"]: c for c in courses_list if "unique" in c}

def parse_seats(value):
    """
    Safely parse seat count. 
    Treats non-numeric strings (e.g., 'Closed', 'Full', '') as 0.
    """
    if not value:
        return 0
    try:
        return int(value)
    except ValueError:
        return 0

def generate_feed():
    print("→ Starting Feed Generation...")
    
    # 1. Get current data
    term_code = get_latest_term_code()
    if not term_code:
        print("❌ Could not find latest term code.")
        return

    courses_file = os.path.join(DATA_DIR, f"{term_code}_courses.json")
    current_data_full = load_json(courses_file)
    if not current_data_full:
        print(f"❌ Could not find courses file: {courses_file}")
        return

    current_courses = normalize_course_data(current_data_full.get("courses", []))
    
    # 2. Get previous data
    previous_courses_list = load_json(PREVIOUS_STATE_FILE) or []
    previous_courses = normalize_course_data(previous_courses_list)

    # 3. Diff and Generate Events
    events = []
    timestamp = datetime.datetime.now().isoformat()

    # If previous_courses is empty, this might be the first run.
    first_run = len(previous_courses) == 0

    if not first_run:
        for unique_id, curr in current_courses.items():
            prev = previous_courses.get(unique_id)

            if not prev:
                # Event: New Section Added
                events.append({
                    "type": "NEW_SECTION",
                    "course_code": curr.get("course_code"),
                    "section": curr.get("section"),
                    "course_name": curr.get("course_name"),
                    "details": "New section added",
                    "timestamp": timestamp
                })
                continue
            
            # Event: Seats Available (Transition from <=0 to >0)
            curr_avail = parse_seats(curr.get("available"))
            prev_avail = parse_seats(prev.get("available"))
            
            # Check for explicit change from <=0 to >0
            if prev_avail <= 0 < curr_avail:
                    events.append({
                    "type": "SEATS_AVAILABLE",
                    "course_code": curr.get("course_code"),
                    "section": curr.get("section"),
                    "course_name": curr.get("course_name"),
                    "details": f"{curr_avail} seat(s) now available",
                    "timestamp": timestamp
                })

            # Event: Instructor Change
            curr_inst = (curr.get("instructor") or "").strip()
            prev_inst = (prev.get("instructor") or "").strip()
            
            if curr_inst != prev_inst:
                # Ignore minor whitespace differences if logic wasn't stripped above
                if curr_inst and prev_inst: # Changed from X to Y
                     events.append({
                        "type": "INSTRUCTOR_CHANGE",
                        "course_code": curr.get("course_code"),
                        "section": curr.get("section"),
                        "course_name": curr.get("course_name"),
                        "details": f"Instructor changed: {prev_inst} → {curr_inst}",
                        "timestamp": timestamp
                    })
                elif curr_inst and not prev_inst: # Assigned
                    events.append({
                        "type": "INSTRUCTOR_ASSIGNED",
                        "course_code": curr.get("course_code"),
                        "section": curr.get("section"),
                        "course_name": curr.get("course_name"),
                        "details": f"Instructor assigned: {curr_inst}",
                        "timestamp": timestamp
                    })

            # Event: Schedule Change
            curr_sched = (curr.get("schedule_raw") or "").strip()
            prev_sched = (prev.get("schedule_raw") or "").strip()
            
            if curr_sched != prev_sched:
                 events.append({
                    "type": "SCHEDULE_CHANGE",
                    "course_code": curr.get("course_code"),
                    "section": curr.get("section"),
                    "course_name": curr.get("course_name"),
                    "details": f"Schedule changed: {prev_sched} → {curr_sched}",
                    "timestamp": timestamp
                })

    # 4. Update Feed File
    if events:
        print(f"✓ Found {len(events)} new events.")
        existing_events = load_json(FEED_FILE) or []
        # Prepend new events
        updated_feed = events + existing_events
        # Trim
        updated_feed = updated_feed[:MAX_FEED_ITEMS]
        save_json(FEED_FILE, updated_feed)
    else:
        if not os.path.exists(FEED_FILE):
            save_json(FEED_FILE, [])
        print("✓ No significant changes found.")

    # 5. Update Previous State (Save list form to match structure)
    save_json(PREVIOUS_STATE_FILE, current_data_full.get("courses", []))
    print("✓ State updated.")

    # 6. Copy to Frontend Public (for local dev)
    # Assuming standard folder structure: root/FCCU-Advisior and root/fccuadvisiorfronetend
    frontend_public = os.path.join(os.path.dirname(BASE_DIR), "fccuadvisiorfronetend", "public")
    if os.path.exists(frontend_public):
        dest = os.path.join(frontend_public, "feed_events.json")
        try:
           shutil.copy2(FEED_FILE, dest)
           print(f"✓ Copied feed to frontend: {dest}")
        except Exception as e:
           print(f"⚠ Could not copy to frontend: {e}")

if __name__ == "__main__":
    generate_feed()
