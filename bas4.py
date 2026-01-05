import requests
from bs4 import BeautifulSoup
import json
import os
import re
import random
import time

# ================= CONFIG =================
BASE_URL = "https://mysis-fccollege.empower-xl.com"
CATALOG_URL = f"{BASE_URL}/fusebox.cfm?fuseaction=CourseCatalog&rpt=1"
API_URL = f"{BASE_URL}/cfcs/courseCatalog.cfc?method=GetList"

DATA_DIR = "course_data"
LATEST_TERM_FILE = os.path.join(DATA_DIR, "latest_term.json")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/143.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 Chrome/116.0.5845.96 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/116.0.5845.110 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) Gecko/20100101 Firefox/116.0",
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


def load_latest_term():
    if os.path.exists(LATEST_TERM_FILE):
        with open(LATEST_TERM_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_latest_term(code, name):
    with open(LATEST_TERM_FILE, "w", encoding="utf-8") as f:
        json.dump({"term_code": code, "term_name": name}, f, indent=2)


# ================= SESSION =================
def create_session():
    s = requests.Session()
    s.headers.update(random_headers())

    print("→ Initializing session...")
    r = s.get(CATALOG_URL, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    token_input = soup.find("input", {"name": "TOKEN"}) or soup.find("input", {"name": "token"})
    token = token_input["value"] if token_input else None

    if token:
        print("✓ Token acquired")
    else:
        print("⚠ Token not found (fallback may be required)")

    return s, token


# ================= TERM =================
def fetch_latest_term():
    print("→ Fetching latest term...")
    r = requests.get(CATALOG_URL, headers=random_headers(), timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    select = soup.find("select", id="empower_global_term_id")
    if not select:
        raise RuntimeError("Term selector not found")

    for opt in select.find_all("option"):
        val = opt.get("value", "").strip()
        txt = opt.get_text(strip=True)
        if val:
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
    }

    r = session.post(API_URL, data=payload, headers=random_headers(), timeout=30)
    r.raise_for_status()

    return r.json()


# ================= PARSER (FIXED) =================
def parse_courses_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("div.ui-grid-row")

    courses = {}

    re_course = re.compile(r"([A-Z]{2,}\s*\d{3,})")
    re_time = re.compile(r"(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})")
    re_day = re.compile(r"\b(MON|TUE|WED|THU|FRI|SAT|SUN)\b", re.I)
    re_start = re.compile(r"start[:\s]*([\d/]{8,10})", re.I)

    for row in rows:
        cols = row.find_all("div", class_=lambda x: x and "ui-grid-col-" in x)
        if len(cols) < 8:
            continue

        text = row.get_text(" ", strip=True)
        match = re_course.search(text)
        if not match:
            continue

        course_code = match.group(1)

        if course_code not in courses:
            courses[course_code] = {
                "course_code": course_code,
                "course_name": cols[1].get_text(strip=True),
                "credits": cols[2].get_text(strip=True),
                "sections": []
            }

        schedule = cols[4].get_text(" ", strip=True)

        section = {
            "classroom": cols[3].get_text(strip=True),
            "schedule_raw": schedule,
            "start_date": re_start.search(schedule).group(1) if re_start.search(schedule) else "",
            "days": " ".join(sorted(set(re_day.findall(schedule)))),
            "time": re_time.search(schedule).group(1) if re_time.search(schedule) else "",
            "instructor": cols[5].get_text(strip=True),
            "capacity": cols[6].get_text(strip=True),
            "available": cols[7].get_text(strip=True),
        }

        courses[course_code]["sections"].append(section)

    return list(courses.values())


# ================= MAIN =================
def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    session, token = create_session()
    if not token:
        token = "FFCCEB852C16EC9C9F4DB28054C02272DAA09A9A"

    saved = load_latest_term()
    term_name, term_code = fetch_latest_term()

    print(f"→ Fetching courses for {term_name}...")
    result = fetch_courses(session, token, term_code)

    if not result or "html" not in result:
        print("✗ No HTML returned")
        return

    courses = parse_courses_from_html(result["html"])

    output = {
        "term_code": term_code,
        "term_name": term_name,
        "courses": courses,
    }

    out_file = os.path.join(DATA_DIR, f"{term_code}_latest.json")

    if os.path.exists(out_file):
        with open(out_file, "r", encoding="utf-8") as f:
            if json.load(f) == output:
                print("✓ No changes detected")
                return

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    save_latest_term(term_code, term_name)
    print(f"✓ Saved {len(courses)} courses")


if __name__ == "__main__":
    main()
