from supabase import create_client, Client
import os
import json
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ---------------- CONFIG ----------------


# ---------------- CONFIG (ENV VARS) ----------------
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
FROM_EMAIL = "ahmadsiddique.webdev@gmail.com"

COURSE_DATA_DIR = "course_data"
# --------------------------------------------------

if not all([SUPABASE_URL, SUPABASE_KEY, SENDGRID_API_KEY]):
    raise RuntimeError("❌ Missing required environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ---------------- SUPABASE ----------------
def get_pending_notifications():
    response = (
        supabase
        .table("seed_availability_notifications")
        .select("*")
        .eq("status", "pending")
        .execute()
    )
    return response.data or []


def mark_as_sent(notification_id):
    supabase.table("seed_availability_notifications") \
        .update({"status": "sent"}) \
        .eq("id", notification_id) \
        .execute()


# ---------------- COURSE DATA ----------------
def get_latest_term_code():
    path = os.path.join(COURSE_DATA_DIR, "latest_term.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    term_code = data.get("term_code")
    if not term_code:
        raise ValueError("No term_code found")

    return term_code


def load_courses_for_term(term_code):
    path = os.path.join(COURSE_DATA_DIR, f"{term_code}_courses.json")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, str):
        data = json.loads(data)

    courses = data.get("courses", [])
    courses_by_unique = {}

    for course in courses:
        unique = course.get("unique")
        if unique:
            courses_by_unique[unique] = course

    return courses_by_unique


# ---------------- EMAIL ----------------
def send_email(to_email, subject, body):
    """Send an email using Gmail SMTP."""
    try:
        msg = MIMEMultipart()
        msg['From'] = FROM_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()  # Secure connection
        server.login(FROM_EMAIL, SENDGRID_API_KEY)
        server.sendmail(FROM_EMAIL, to_email, msg.as_string())
        server.quit()
        print(f"✅ Email sent to {to_email}")
    except Exception as e:
        print(f"❌ Failed to send email to {to_email} | Error: {e}")


# ---------------- MAIN LOGIC ----------------
def main():
    term_code = get_latest_term_code()
    print(f"✓ Latest term code: {term_code}")

    courses_by_unique = load_courses_for_term(term_code)
    print(f"✓ Loaded {len(courses_by_unique)} courses")

    notifications = get_pending_notifications()
    print(f"✓ Pending notifications: {len(notifications)}")

    for notif in notifications:
        notif_id = notif.get("id")
        roll_number = notif.get("roll_number")
        unique = notif.get("uniqueness")

        course = courses_by_unique.get(unique)
        if not course:
            continue

        try:
            available = int(course.get("available", 0))
        except ValueError:
            available = 0

        if available > 0:
            email = f"{str(roll_number)}@formanite.fccollege.edu.pk"
            subject = f"Seat Available: {course.get('course_name')}"
            body = (
                f"Good news!\n\n"
                f"Seats are now available for:\n"
                f"{course.get('course_name')} ({unique})\n\n"
                f"Please log in to the portal and register ASAP.\n\n"
                f"— FCCU Course Notifier"
            )

            send_email(email, subject, body)
            mark_as_sent(notif_id)


if __name__ == "__main__":
    main()
