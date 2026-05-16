from supabase import create_client, Client
import os
import json
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pywebpush import webpush, WebPushException

# ---------------- CONFIG ----------------


# ---------------- CONFIG (ENV VARS) ----------------
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY")
FROM_EMAIL = "ahmadsiddique.webdev@gmail.com"

VAPID_CLAIMS = {
    "sub": f"mailto:{FROM_EMAIL}"
}

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
        print(f"✅ Email sent ({to_email})")
    except Exception as e:
        print(f"❌ Email failed ({to_email})")


# ---------------- NOTIFICATIONS ----------------
def send_course_notifications(roll_number, course, unique):
    course_name = course.get("course_name", "Unknown Course")
    
    # 1. Send Email
    email = f"{str(roll_number)}@formanite.fccollege.edu.pk"
    subject = f"Seat Available: {course_name}"
    body = (
        f"Good news!\n\n"
        f"Seats are now available for:\n"
        f"{course_name} ({unique})\n\n"
        f"Please log in to the portal and register ASAP.\n\n"
        f"— FCCU Course Notifier"
    )
    send_email(email, subject, body)

    # 2. Send Push Notifications
    try:
        res = (
            supabase
            .table("users")
            .select("Notification_IDs")
            .eq("roll_number", roll_number)
            .single()
            .execute()
        )
        data = res.data
    except Exception as e:
        data = None

    notification_ids = []
    if data and data.get("Notification_IDs"):
        notification_ids = data.get("Notification_IDs")

    # Unique subscriptions
    seen = set()
    unique_subs = []
    for sub in notification_ids:
        if not isinstance(sub, dict): continue
        endpoint = sub.get("endpoint")
        if endpoint and endpoint not in seen:
            seen.add(endpoint)
            unique_subs.append(sub)

    push_sent_count = 0
    valid_subs = []
    
    payload = {
        "title": "Seat Available! 🎉",
        "body": f"Seats are now available for {course_name} ({unique})."
    }

    needs_cleanup = len(notification_ids) > 10

    if not VAPID_PRIVATE_KEY:
        print("⚠️ VAPID_PRIVATE_KEY not set. Skipping push notifications.")
    else:
        for sub in unique_subs:
            if not sub.get("endpoint") or not sub.get("keys"):
                continue
                
            success = False
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub["endpoint"],
                        "keys": {
                            "p256dh": sub["keys"].get("p256dh", ""),
                            "auth": sub["keys"].get("auth", "")
                        }
                    },
                    data=json.dumps(payload),
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=VAPID_CLAIMS,
                    timeout=10
                )
                push_sent_count += 1
                success = True
            except WebPushException as e:
                success = False
            except Exception as e:
                success = False

            if success or not needs_cleanup:
                valid_subs.append(sub)

    print(f"✅ Pushes sent: {push_sent_count} ({roll_number})")

    if needs_cleanup and len(valid_subs) < len(notification_ids):
        try:
            supabase.table("users").update({"Notification_IDs": valid_subs}).eq("roll_number", roll_number).execute()
            print(f"🧹 IDs cleaned ({roll_number})")
        except Exception as e:
            print(f"❌ Cleanup failed ({roll_number})")

def process_new_section_notifications():
    from dateutil.parser import parse as parse_date
    import datetime
    
    response = (
        supabase
        .table("new_section_notifications")
        .select("*")
        .eq("status", "pending")
        .execute()
    )
    pending_notifs = response.data or []
    if not pending_notifs: return

    changes_path = os.path.join(COURSE_DATA_DIR, "latestterm_changes.json")
    if not os.path.exists(changes_path): return

    with open(changes_path, "r", encoding="utf-8") as f:
        try:
            changes = json.load(f)
        except json.JSONDecodeError:
            changes = []

    new_section_changes = [c for c in changes if c.get("type") == "NEW_SECTION"]
    if not new_section_changes: return

    for notif in pending_notifs:
        notif_id = notif.get("id")
        roll_number = notif.get("roll_number")
        course_code = notif.get("course_code")
        requested_at_str = notif.get("requested_at")

        if not requested_at_str:
            continue
            
        try:
            req_time = parse_date(requested_at_str)
        except Exception:
            continue

        found_changes = []
        for c in new_section_changes:
            if c.get("course_code") == course_code:
                c_time_str = c.get("timestamp")
                if c_time_str:
                    try:
                        c_time = parse_date(c_time_str)
                        # Ensure both are naive or both are timezone-aware for comparison
                        if req_time.tzinfo is not None and c_time.tzinfo is None:
                            c_time = c_time.replace(tzinfo=datetime.timezone.utc)
                        elif req_time.tzinfo is None and c_time.tzinfo is not None:
                            req_time = req_time.replace(tzinfo=datetime.timezone.utc)
                        
                        if c_time > req_time:
                            found_changes.append(c)
                    except Exception:
                        pass
        
        if found_changes:
            # Send Notification
            sections_info = "\n".join([f"- Section {c.get('section')} with {c.get('instructor', 'Unknown')}" for c in found_changes])
            
            # Send Email
            email = f"{str(roll_number)}@formanite.fccollege.edu.pk"
            subject = f"New Section Alert: {course_code}"
            body = (
                f"Good news!\n\n"
                f"New sections have been added for {course_code}:\n\n"
                f"{sections_info}\n\n"
                f"Please log in to the portal and register ASAP.\n\n"
                f"— FCCU Course Notifier"
            )
            send_email(email, subject, body)

            # Send Push Notification
            try:
                res = supabase.table("users").select("Notification_IDs").eq("roll_number", roll_number).single().execute()
                data = res.data
            except Exception as e:
                data = None

            notification_ids = []
            if data and data.get("Notification_IDs"):
                notification_ids = data.get("Notification_IDs")

            seen = set()
            unique_subs = []
            for sub in notification_ids:
                if not isinstance(sub, dict): continue
                endpoint = sub.get("endpoint")
                if endpoint and endpoint not in seen:
                    seen.add(endpoint)
                    unique_subs.append(sub)

            push_sent_count = 0
            valid_subs = []
            
            payload = {
                "title": "New Section Alert! 🎉",
                "body": f"New sections for {course_code} are now available!"
            }

            needs_cleanup = len(notification_ids) > 10

            if not VAPID_PRIVATE_KEY:
                print("⚠️ VAPID_PRIVATE_KEY not set. Skipping push notifications.")
            else:
                for sub in unique_subs:
                    if not sub.get("endpoint") or not sub.get("keys"):
                        continue
                        
                    success = False
                    try:
                        webpush(
                            subscription_info={
                                "endpoint": sub["endpoint"],
                                "keys": {
                                    "p256dh": sub["keys"].get("p256dh", ""),
                                    "auth": sub["keys"].get("auth", "")
                                }
                            },
                            data=json.dumps(payload),
                            vapid_private_key=VAPID_PRIVATE_KEY,
                            vapid_claims=VAPID_CLAIMS,
                            timeout=10
                        )
                        push_sent_count += 1
                        success = True
                    except WebPushException:
                        success = False
                    except Exception:
                        success = False

                    if success or not needs_cleanup:
                        valid_subs.append(sub)

            print(f"✅ New Section Pushes sent: {push_sent_count} ({roll_number})")

            if needs_cleanup and len(valid_subs) < len(notification_ids):
                try:
                    supabase.table("users").update({"Notification_IDs": valid_subs}).eq("roll_number", roll_number).execute()
                except Exception:
                    pass

            # Mark as sent
            supabase.table("new_section_notifications").update({"status": "sent"}).eq("id", notif_id).execute()

# ---------------- MAIN LOGIC ----------------
def main():
    term_code = get_latest_term_code()
    courses_by_unique = load_courses_for_term(term_code)
    notifications = get_pending_notifications()
    print(f"✓ Term: {term_code} | Courses: {len(courses_by_unique)} | Pending Alerts: {len(notifications)}")

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
            send_course_notifications(roll_number, course, unique)
            mark_as_sent(notif_id)

    # Process new section notifications
    process_new_section_notifications()

if __name__ == "__main__":
    main()
