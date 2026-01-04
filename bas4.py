import requests
from bs4 import BeautifulSoup
import json
import time
import os
import re
import random

# ================= CONFIG =================
BASE_URL = "https://mysis-fccollege.empower-xl.com"
CATALOG_URL = f"{BASE_URL}/fusebox.cfm?fuseaction=CourseCatalog&rpt=1"
API_URL = f"{BASE_URL}/cfcs/courseCatalog.cfc?method=GetList"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/143.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 Chrome/116.0.5845.96 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) Gecko/20100101 Firefox/116.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/116.0.5845.110 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_4 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
]

HEADERS_TEMPLATE = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": BASE_URL,
    "Referer": CATALOG_URL,
    "X-Requested-With": "XMLHttpRequest"
}

DATA_DIR = "course_data"
LATEST_TERM_FILE = os.path.join(DATA_DIR, "latest_term.json")

# =============== HELPERS ===============
def get_random_headers():
    headers = HEADERS_TEMPLATE.copy()
    headers["User-Agent"] = random.choice(USER_AGENTS)
    return headers

def load_latest_term():
    if os.path.exists(LATEST_TERM_FILE):
        with open(LATEST_TERM_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_latest_term(term_code, term_name):
    with open(LATEST_TERM_FILE, "w", encoding="utf-8") as f:
        json.dump({"term_code": term_code, "term_name": term_name}, f, indent=2)

def fetch_latest_term_from_catalog():
    """Fetch the catalog page and get the first non-empty option in term select."""
    print("→ Fetching latest term from catalog page...")
    resp = requests.get(CATALOG_URL, headers=get_random_headers(), timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    select = soup.find("select", id="empower_global_term_id")
    if not select:
        raise Exception("⚠ Term select box not found!")
    for option in select.find_all("option"):
        value = option.get("value", "").strip()
        text = option.get_text(strip=True)
        if value:
            print(f"✓ Latest term found: {text} ({value})")
            return text, value
    raise Exception("⚠ No valid term found!")

# ================= SESSION =================
def create_session():
    session = requests.Session()
    session.headers.update(get_random_headers())
    print("→ Initializing session...")
    resp = session.get(CATALOG_URL, timeout=30)
    if resp.status_code == 200:
        print("✓ Session initialized successfully")
        soup = BeautifulSoup(resp.text, "html.parser")
        token_input = soup.find("input", {"name": "TOKEN"}) or soup.find("input", {"name": "token"})
        token = token_input["value"] if token_input else None
        if token:
            print(f"✓ Token found: {token[:10]}...")
        else:
            print("⚠ No token found in catalog page")
        return session, token
    else:
        print(f"✗ Failed to initialize session, HTTP {resp.status_code}")
        return None, None

def get_token_from_user():
    token = input("Enter TOKEN (or press Enter to use default): ").strip()
    return token if token else "FFCCEB852C16EC9C9F4DB28054C02272DAA09A9A"

# ================= FETCH =================
def fetch_courses_for_term(session, token, term_value):
    print(f"→ Fetching courses for term {term_value}...")
    data = {
        "method": "GetList",
        "fuseaction": "CourseCatalog",
        "screen_width": "1920",
        "token": token,
        "empower_global_term_id": term_value,
        "cs_descr": "",
        "empower_global_dept_id": "",
        "empower_global_course_id": "",
        "cs_sess_id": "",
        "cs_loca_id": "",
        "cs_inst_id": "",
        "cs_classroom": "",
        "cs_emph_id": "",
        "CS_time_start": "", "CS_time_end": "",
        "MON": "", "TUE": "", "WED": "", "THU": "", "FRI": "", "SAT": "", "SUN": "",
        "status": "1"
    }
    resp = session.post(API_URL, data=data, headers=get_random_headers(), timeout=30)
    if resp.status_code == 200:
        try:
            return resp.json()
        except:
            print("✗ Failed to decode JSON from API response")
            return None
    else:
        print(f"✗ HTTP {resp.status_code} from API")
    return None

# ================= PARSE =================
def parse_courses_from_html(html_content, skip_first_n=2):
    soup = BeautifulSoup(html_content, "html.parser")
    rows = [r for r in soup.find_all("div", class_="ui-grid-row") if r.get("style") and "background-color" in r.get("style")]
    courses = []
    skip_count = 0
    current_course = None
    re_start = re.compile(r"start[:\s]*([\d/]{8,10})", re.IGNORECASE)
    re_time = re.compile(r"(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})")
    re_days = re.compile(r"\b([MTWRFSU]{1,2}(?:\s+[MTWRFSU]{1,2})*)\b", re.IGNORECASE)

    for row in rows:
        if skip_count < skip_first_n:
            skip_count += 1
            continue
        cols = row.find_all("div", class_=lambda x: x and "ui-grid-col-" in x)
        if not cols: 
            continue

        course_col = next((c for c in cols if "nbsp" in str(c) or ("<br" in str(c) and re.search(r"[A-Z]{2,}\s*\d{3}", c.get_text()))), None)
        if course_col:
            if current_course:
                courses.append(current_course)
            lines = [ln.strip() for ln in course_col.get_text(separator="\n").split("\n") if ln.strip()]
            course_code = lines[0] if len(lines) > 0 else ""
            course_name = lines[1] if len(lines) > 1 else ""
            credits = cols[2].get_text(strip=True).replace("\xa0", "").strip() if len(cols) > 2 else ""
            has_error = "empower_error.gif" in str(cols[0]) if len(cols) > 0 else False
            current_course = {"course_code": course_code, "course_name": course_name, "credits": credits, "has_error": has_error, "sections":[]}

        if current_course and len(cols) >= 8:
            classroom = cols[3].get_text(separator=" ", strip=True)
            schedule = cols[4].get_text(separator=" ", strip=True)
            instructor = cols[5].get_text(strip=True)
            capacity = cols[6].get_text(strip=True)
            available = cols[7].get_text(strip=True)
            start_date = re_start.search(schedule).group(1) if re_start.search(schedule) else ""
            time_span = re_time.search(schedule).group(1) if re_time.search(schedule) else ""
            days = re_days.search(schedule).group(1) if re_days.search(schedule) else ""
            inst_anchor = cols[5].find("a")
            inst_cid = inst_anchor.get("data-cid") if inst_anchor else ""
            inst_token = inst_anchor.get("data-token") if inst_anchor else ""
            detail_token = ""
            detail_anchor = row.find("a", attrs={"title": "Detail"})
            if detail_anchor and detail_anchor.has_attr("data-token"):
                detail_token = detail_anchor["data-token"]
            current_course["sections"].append({
                "classroom": classroom, "schedule_raw": schedule, "start_date": start_date,
                "days": days, "time": time_span, "instructor": instructor,
                "instructor_cid": inst_cid, "instructor_token": inst_token,
                "capacity": capacity, "available": available, "detail_token": detail_token
            })
    if current_course:
        courses.append(current_course)
    return courses

# ================= MAIN =================
def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    session, token = create_session()
    if not token:
        token = get_token_from_user()

    # ==== Latest Term Only ====
    latest_term_saved = load_latest_term()
    term_name, term_value = fetch_latest_term_from_catalog()

    # Already scraped latest term
    if latest_term_saved.get("term_code") == term_value:
        print("→ Latest term already scraped, checking if data changed...")

        data_file = f"{DATA_DIR}/{term_value}_latest.json"
        result = fetch_courses_for_term(session, token, term_value)
        if result and result.get("html"):
            courses = parse_courses_from_html(result["html"], skip_first_n=2)
            new_data = {"term_code": term_value, "term_name": term_name, "courses": courses}

            # Compare with existing file
            if os.path.exists(data_file):
                with open(data_file, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                if old_data == new_data:
                    print("✓ No changes in course data. Skipping write.")
                    return
            with open(data_file, "w", encoding="utf-8") as f:
                json.dump(new_data, f, indent=2, ensure_ascii=False)
            print(f"✓ Course data updated for {term_name}")
        return

    # New term, fetch and save
    print(f"→ Scraping courses for latest term ({term_name})...")
    result = fetch_courses_for_term(session, token, term_value)
    if result and result.get("html"):
        courses = parse_courses_from_html(result["html"], skip_first_n=2)
        data_file = f"{DATA_DIR}/{term_value}_latest.json"
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump({"term_code": term_value, "term_name": term_name, "courses": courses}, f, indent=2, ensure_ascii=False)
        save_latest_term(term_value, term_name)
        print(f"✓ Saved {len(courses)} courses for latest term ({term_name})")

if __name__ == "__main__":
    main()
