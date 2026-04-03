import os
import json
from supabase import create_client
from pywebpush import webpush , WebPushException

# ---------- CONFIG ----------


ROLL_NUMBER = 281134833 # Replace with the student's roll number you want to test

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# VAPID claims required for web push protocol
VAPID_CLAIMS = {
    "sub": "mailto:ahmadsiddique.webdev@gmail.com"
}


# ---------- GET USER'S NOTIFICATION IDs ----------
def get_user_notification_ids():
    """
    Fetches the array of notification IDs for the given roll number from the 'users' table.
    Returns an empty list if user not found or no notifications.
    """
    res = (
        supabase
        .table("users")
        .select("Notification_IDs")
        .eq("roll_number", ROLL_NUMBER)
        .single()
        .execute()
    )

    if not res.data:
        print("❌ User not found")
        return []

    return res.data.get("Notification_IDs", [])





# ---------- SEND PUSH NOTIFICATION ----------
def send_push(subscription):
    """
    Sends a push notification to a single subscription object.
    subscription format:
    {
        "endpoint": "...",
        "keys": {"p256dh": "...", "auth": "..."},
        "device": "...",
        ...
    }
    """
    # Skip invalid subscriptions
    if not subscription.get("endpoint") or not subscription.get("keys"):
        print(f"❌ Skipping invalid subscription: {subscription.get('device', 'unknown')}")
        return

    payload = {
        "title": "Test Notification",
        "body": "Push notifications are working 🎉"
    }

    try:
        webpush(
            subscription_info={
                "endpoint": subscription["endpoint"],
                "keys": {
                    "p256dh": subscription["keys"].get("p256dh", ""),
                    "auth": subscription["keys"].get("auth", "")
                }
            },
            data=json.dumps(payload),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS,
            timeout=10  # timeout in seconds to avoid hanging
        )
        print(f"✅ Notification sent to {subscription.get('device', 'unknown')}")
    except WebPushException as e:
        print(f"❌ Failed to send notification to {subscription.get('device', 'unknown')}: {e}")
        
def unique_subscriptions(subscriptions):
    seen = set()
    unique = []
    for sub in subscriptions:
        # use endpoint as unique identifier
        endpoint = sub.get("endpoint")
        if endpoint and endpoint not in seen:
            seen.add(endpoint)
            unique.append(sub)
    return unique
# ---------- MAIN FUNCTION ----------
def main():
    """
    Main flow:
    1. Fetch user's notification IDs from the users table
    2. Fetch corresponding subscriptions from notifications table
    3. Send test notification to each device
    """
    notification_ids = unique_subscriptions(get_user_notification_ids())

    if not notification_ids:
        print("❌ No notification IDs found for this user")
        return

    print(f"Found {len(notification_ids)} device(s) for user {ROLL_NUMBER}")

    for sub in notification_ids:
        send_push(sub)


# ---------- RUN SCRIPT ----------
if __name__ == "__main__":
    main()

# def enrich_latest_instructors_with_previous_term():

#     import os, json

#     DATA_DIR = "course_data"

#     # ===== LOAD LATEST TERM =====
#     with open(os.path.join(DATA_DIR, "latest_term.json"), "r", encoding="utf-8") as f:
#         latest = json.load(f)

#     term_code = latest["term_code"]

#     latest_file = os.path.join(DATA_DIR, f"{term_code}_instructors.json")
#     prev_file = os.path.join(DATA_DIR, "2026SP_courses.json")

#     print(f"→ Updating: {latest_file}")
#     print(f"→ Using: {prev_file}")

#     # ===== LOAD DATA =====
#     with open(latest_file, "r", encoding="utf-8") as f:
#         instructor_list = json.load(f)

#     with open(prev_file, "r", encoding="utf-8") as f:
#         prev_courses = json.load(f)["courses"]

#     # ================= BUILD MAP =================
#     # KEY = name|dept BUT object stays unified per instructor+dept group
#     instructors = {}

#     for inst in instructor_list:
#         name = inst["name"].strip()

#         for dept in inst["departments"]:
#             dept_clean = dept.strip().upper()
#             key = f"{name}|{dept_clean}"

#             instructors[key] = {
#                 "name": name,
#                 "departments": set(inst["departments"]),
#                 "current_courses": inst.get("current_courses", [])[:],
#                 "all_courses": set(inst.get("all_courses", []))
#             }

#     # ================= PROCESS PREVIOUS TERM =================
#     for course in prev_courses:

#         instructor = (course.get("instructor") or "").strip()
#         if not instructor:
#             continue

#         course_code = course["course_code"].strip()
#         dept = course_code.split()[0].strip().upper()

#         key = f"{instructor}|{dept}"

#         # CREATE IF NOT EXISTS
#         if key not in instructors:
#             instructors[key] = {
#                 "name": instructor,
#                 "departments": {dept},
#                 "current_courses": [],
#                 "all_courses": set()
#             }

#         inst = instructors[key]

#         # ADD COURSE TO HISTORY ONLY (previous term)
#         inst["all_courses"].add(course_code)

#     # ================= CONVERT BACK =================
#     final = []

#     for inst in instructors.values():

#         final.append({
#             "name": inst["name"],
#             "departments": sorted(list(inst["departments"])),
#             "current_courses": inst["current_courses"],  # untouched (latest term)
#             "all_courses": sorted(list(inst["all_courses"]))
#         })

#     # ================= SAVE =================
#     with open(latest_file, "w", encoding="utf-8") as f:
#         json.dump(final, f, indent=2, ensure_ascii=False)

#     print("✓ Done — properly merged previous term into all_courses")


# enrich_latest_instructors_with_previous_term()