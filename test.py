import os
import json
from supabase import create_client
from pywebpush import webpush , WebPushException

# ---------- CONFIG ----------
SUPABASE_URL = ""
SUPABASE_KEY = ""
VAPID_PRIVATE_KEY = ""

ROLL_NUMBER = 281134833  # Replace with the student's roll number you want to test

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