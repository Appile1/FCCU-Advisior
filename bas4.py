import requests
from bs4 import BeautifulSoup
import json
import os
import re
import random
import urllib3
from collections import defaultdict


# ================= SSL FIX =================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ================= CONFIG =================
BASE_URL = "https://mysis-fccollege.empower-xl.com"
CATALOG_URL = f"{BASE_URL}/fusebox.cfm?fuseaction=CourseCatalog&rpt=1"
API_URL = f"{BASE_URL}/cfcs/courseCatalog.cfc?method=GetList"

DATA_DIR = "course_data"
LATEST_TERM_FILE = os.path.join(DATA_DIR, "latest_term.json")
COUNTS_FILE = os.path.join(DATA_DIR, "department_counts.json")
DEPART_FILE = "depart.txt"
INSTRUCTORS_FILE = os.path.join(DATA_DIR, "instructors.json")

USER_AGENTS = [
    # Windows Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.129 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.91 Safari/537.36",

    # Windows Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.129 Safari/537.36 Edg/122.0.2365.80",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.91 Safari/537.36 Edg/124.0.2478.67",

    # Windows Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",

    # Mac Chrome
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.122 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.184 Safari/537.36",

    # Mac Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",

    # Linux Chrome
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.86 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",

    # Android Chrome
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.86 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Samsung Galaxy S21) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.105 Mobile Safari/537.36",

    # iPhone Safari
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",

    # iPad Safari
    "Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
]

HEADERS_TEMPLATE = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": BASE_URL,
    "Referer": CATALOG_URL,
    "X-Requested-With": "XMLHttpRequest",
}

# ================= HELPERS =================
def random_headers():
    h = HEADERS_TEMPLATE.copy()
    h["User-Agent"] = random.choice(USER_AGENTS)
    return h

def load_departments():
    departments = {}
    if not os.path.exists(DEPART_FILE):
        return departments

    with open(DEPART_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if ":" in line:
                _, code = line.split(":", 1)
                departments[code.strip()] = 0
    return departments

def save_latest_term(code, name):
    with open(LATEST_TERM_FILE, "w", encoding="utf-8") as f:
        json.dump({"term_code": code, "term_name": name}, f, indent=2)

# ================= SESSION =================
def create_session():
    s = requests.Session()
    s.headers.update(random_headers())

    print("→ Initializing session...")
    r = s.get(CATALOG_URL, timeout=30, verify=False)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    token_input = soup.find("input", {"name": "TOKEN"}) or soup.find("input", {"name": "token"})
    token = token_input["value"] if token_input else None

    if token:
        print("✓ Token acquired")
    else:
        print("⚠ Token not found (using fallback)")

    return s, token or "FFCCEB852C16EC9C9F4DB28054C02272DAA09A9A"

# ================= TERM =================
def fetch_latest_term():
    print("→ Fetching latest term...")
    r = requests.get(CATALOG_URL, headers=random_headers(), timeout=30, verify=False)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    select = soup.find("select", id="empower_global_term_id")
    if not select:
        raise RuntimeError("Term selector not found")

    for opt in select.find_all("option"):
        val = opt.get("value", "").strip()
        txt = opt.get_text(strip=True)
        if val == "2026FA":
            print(f"✓ Latest term: {txt} ({val})")
            return txt, val

    raise RuntimeError("No valid term found")

# ================= FETCH COURSES =================
def fetch_courses(session, token, term):
    payload = {
        "method": "GetList",
        "fuseaction": "CourseCatalog",
        "token": token,
        "empower_global_term_id": term,
        "status": "1",
        "page": "1",
        "pageSize": "5000",  # Increase page size to fetch all
        "uiGridPageSize": "5000",
        "rows": "5000",
        "limit": "5000",
    }

    r = session.post(
        API_URL,
        data=payload,
        headers=random_headers(),
        timeout=60,
        verify=False
    )
    r.raise_for_status()

    data = r.json()
    html = data.get("html", "")
    print(f"✓ HTML size received: {len(html):,} characters")

    return html
# ================= build_instructor_course_data  =================
def build_instructor_course_data():

    # Directory where all scraped data is stored
    DATA_DIR = "course_data"

    # File that stores the latest term code (example: 2026FA)
    LATEST_TERM_FILE = os.path.join(DATA_DIR, "latest_term.json")

    # -------- Load the latest term --------
    # This tells us which course file to read
    with open(LATEST_TERM_FILE, "r", encoding="utf-8") as f:
        latest = json.load(f)

    term_code = latest["term_code"]

    # Build the filename for the courses of that term
    # Example: course_data/2026FA_courses.json
    course_file = os.path.join(DATA_DIR, f"{term_code}_courses.json")

    print(f"→ Loading course file: {course_file}")

    # Load all courses for that term
    with open(course_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    courses = data["courses"]

    print(f"✓ Courses loaded: {len(courses)}")

    # -------- Instructor Mapping --------
    # defaultdict automatically creates the structure
    # when we encounter a new instructor
    instructors = defaultdict(lambda: {
        "name": "",              # instructor name
        "departments": set(),    # departments they teach in (set avoids duplicates)
        "current_courses": [],   # courses they teach this semester
        "all_courses": set()     # unique course codes they teach
    })

    # Loop through every course in the dataset
    for course in courses:

        # Clean instructor name
        instructor = course["instructor"].strip()

        # Skip courses with no instructor
        if not instructor:
            continue

        # Example course code: "CS 210"
        course_code = course["course_code"]

        # Department is the first part of the course code
        # Example: "CS 210" -> "CS"
        dept = course_code.split()[0]

        # IMPORTANT:
        # Use instructor + department as key
        # This prevents merging different instructors
        # who share the same name
        key = f"{instructor}|{dept}"

        # Store instructor name
        instructors[key]["name"] = instructor

        # Add department to the department set
        instructors[key]["departments"].add(dept)

        # Add detailed course information for the current semester
        instructors[key]["current_courses"].append({
            "course_code": course_code,
            "section": course["section"],
            "course_name": course["course_name"],
            "schedule": course.get("schedule_raw", ""),  # class days/time
            "classroom": course.get("classroom", ""),    # room location
            "unique": course["unique"]                   # unique course identifier
        })

        # Store only the course code in the "all_courses" list
        # Using a set ensures duplicates are removed
        instructors[key]["all_courses"].add(course_code)

    print(f"✓ Instructor records created: {len(instructors)}")

    # -------- Convert sets to lists --------
    # JSON cannot store sets, so we convert them
    instructor_list = []

    for inst in instructors.values():

        inst["departments"] = sorted(list(inst["departments"]))
        inst["all_courses"] = sorted(list(inst["all_courses"]))

        instructor_list.append(inst)

    # Output file that will store instructor data
    output_file = os.path.join(DATA_DIR, f"{term_code}_instructors.json")

    # Save instructor data
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(instructor_list, f, indent=2, ensure_ascii=False)

    print(f"✓ Instructor data saved → {output_file}")

    # Return the instructor data in case we want to use it elsewhere
    return instructor_list
# ================= PARSER =================
def parse_courses_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("div.ui-grid-row")
    print(f"✓ UI-grid rows found: {len(rows)}")

    courses = []
    instructors_set = set()
    re_course = re.compile(r"([A-Z]{2,}\s*\d{3,})")

    def safe(cols, i):
        return cols[i].get_text(strip=True) if i < len(cols) else ""
    a = 0
    sep = False 
    for row in rows:
        cols = row.find_all("div", class_=lambda x: x and "ui-grid-col-" in x)
        if a < 2:
            a += 1 
            continue 
        
        if row.find("hr"):
            sep = True 
            continue 
        if sep:
            sep = False 
            schedule_col = cols[2] 
            schedule_text = schedule_col.get_text("\n", strip=True)
            schedule_parts = [p.strip() for p in schedule_text.split("\n") if p.strip()]
            days = ""
            time = ""
            for part in schedule_parts:
                if part.lower().startswith("start:"):
                    continue
                if "-" in part:
                    time = part
                elif re.match(r"^[A-Z\s]+$", part):
                    days = part

            schedule_raw = " | ".join(p for p in [days, time] if p)
            capacity = cols[4].get_text(strip=True) if len(cols) > 4 else ""
            available = cols[5].get_text(strip=True) if len(cols) > 5 else ""
            classroom = cols[1].get_text(strip=True) if len(cols) > 1 else ""
            
            classROOMS = courses[-1]["classroom"].split(" | ")
            if classroom not in classROOMS :
                courses[-1]["classroom"] += " | " + classroom
            courses[-1]["schedule_raw"] += " | " + schedule_raw
            courses[-1]["capacity"] = capacity
            courses[-1]["available"] = available
            continue 
             

        # ---- COURSE COLUMN ----
        course_col = cols[1]
        course_text = course_col.get_text("\n", strip=True)
        parts = [p.strip() for p in course_text.split("\n") if p.strip()]

        

        # First line: "ARTS 101 A"
        first_line = parts[0].replace("\xa0", " ")
        tokens = first_line.split()

       

        section = tokens[-1]                      # A
        course_code = " ".join(tokens[:-1])       # ARTS 101
        course_name = parts[-1]                   # Intro. Art & Design

        unique = f"{course_code}/{section}"

        # ---- SCHEDULE COLUMN ----
        schedule_col = cols[4]
        schedule_text = schedule_col.get_text("\n", strip=True)
        schedule_parts = [p.strip() for p in schedule_text.split("\n") if p.strip()]

        days = ""
        time = ""

        for part in schedule_parts:
            if part.lower().startswith("start:"):
                continue
            if "-" in part:
                time = part
            elif re.match(r"^[A-Z\s]+$", part):
                days = part

        schedule_raw = " | ".join(p for p in [days, time] if p)
        
        
            
        instructor = safe(cols, 5)
        if instructor:
            instructors_set.add(instructor)

        course = {
            "course_code": course_code,
            "section": section,
            "unique": unique,
            "course_name": course_name,
            "credits": safe(cols, 2),
            "classroom": safe(cols, 3),
            "schedule_raw": schedule_raw,
            "instructor": instructor,
            "capacity": safe(cols, 6),
            "available": safe(cols, 7),
        }

        courses.append(course)

    # Save instructors separately
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(INSTRUCTORS_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(instructors_set)), f, indent=2, ensure_ascii=False)

    print(f"✓ Instructors saved: {len(instructors_set)} unique names")
    print(f"✓ Courses parsed: {len(courses)}")

    return courses

# ================= COUNTS =================
def count_courses_by_department(courses, departments):
    total = len(courses)
    for course in courses:
        dept = course["course_code"].split()[0]
        departments.setdefault(dept, 0)
        departments[dept] += 1
    return total

# ================= MAIN =================
def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    session, token = create_session()
    term_name, term_code = fetch_latest_term()

    print(f"→ Fetching courses for {term_name}...")
    html = fetch_courses(session, token, term_code)

    courses = parse_courses_from_html(html)

    with open(os.path.join(DATA_DIR, f"{term_code}_courses.json"), "w", encoding="utf-8") as f:
        json.dump({
            "term_code": term_code,
            "term_name": term_name,
            "total_courses": len(courses),
            "courses": courses
        }, f, indent=2, ensure_ascii=False)

    departments = load_departments()
    total = count_courses_by_department(courses, departments)

    with open(COUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "total_courses": total,
            "departments": departments
        }, f, indent=2)

    save_latest_term(term_code, term_name)

    print(f"✅ DONE — {total} course rows saved")
    
    build_instructor_course_data()

# ================= RUN =================
if __name__ == "__main__":
    main()
