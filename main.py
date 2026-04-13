import requests
import uuid
import time
import json
from datetime import datetime

# ===== YOUR CONFIGURATION =====
TELEGRAM_TOKEN = "8664130966:AAGwmssIWvUzriVHuSML-NIayeqv588Lqf8"
SUPABASE_URL = "https://vminufdeufycbvlmnkvq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZtaW51ZmRldWZ5Y2J2bG1ua3ZxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU4ODc2ODksImV4cCI6MjA5MTQ2MzY4OX0.AYH9ih3BzAeiC5KK-AVel9l3CCKNYC3JozY4RvY_Ug8"
GROUP_ID = -1003777573948
GROUP_INVITE_LINK = "https://t.me/AIAccessCommunity"
TALLY_FORM_ID = "yPEDzx"

# ===== SUPABASE FUNCTIONS =====
def supabase_query(table, filters=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    if filters:
        url += f"?{filters}"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return response.json() if response.status_code == 200 else []
    except:
        return []

def supabase_insert(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        return response.status_code == 201
    except:
        return False

def supabase_update(table, data, filters):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{filters}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.patch(url, headers=headers, json=data, timeout=10)
        return response.status_code == 200
    except:
        return False

# ===== TELEGRAM FUNCTIONS =====
def send_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    if reply_markup:
        data["reply_markup"] = reply_markup
    try:
        requests.post(url, json=data, timeout=10)
    except:
        pass

def is_user_in_group(user_id):
    """Check if user is a member of the Telegram group"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChatMember"
    params = {"chat_id": GROUP_ID, "user_id": user_id}
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.ok:
            status = response.json().get("result", {}).get("status")
            return status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Group check error: {e}")
    return False

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"timeout": 20}
    if offset:
        params["offset"] = offset
    try:
        response = requests.get(url, params=params, timeout=30)
        return response.json()
    except:
        return {"ok": False, "result": []}

def answer_callback(callback_id):
    """Answer callback query to remove loading state on button"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
    try:
        requests.post(url, json={"callback_query_id": callback_id}, timeout=10)
    except:
        pass

# ===== REFERRAL TRACKING =====
def track_referral_attempt(telegram_user_id, ambassador_code, signed_waitlist=False, joined_group=False):
    existing = supabase_query("referral_attempts", f"telegram_user_id=eq.{telegram_user_id},ambassador_code=eq.{ambassador_code}")
    
    if existing:
        updates = {}
        if signed_waitlist:
            updates["signed_waitlist"] = True
        if joined_group:
            updates["joined_group"] = True
        
        if updates:
            supabase_update("referral_attempts", updates, f"telegram_user_id=eq.{telegram_user_id},ambassador_code=eq.{ambassador_code}")
        return existing[0]
    else:
        supabase_insert("referral_attempts", {
            "telegram_user_id": telegram_user_id,
            "ambassador_code": ambassador_code,
            "signed_waitlist": signed_waitlist,
            "joined_group": joined_group
        })
        return {"signed_waitlist": signed_waitlist, "joined_group": joined_group}

def award_point(ambassador_code, telegram_user_id):
    ambassador = supabase_query("ambassadors", f"referrer_code=eq.{ambassador_code}")
    if ambassador:
        current_count = ambassador[0].get("referral_count", 0)
        supabase_update("ambassadors", {"referral_count": current_count + 1}, f"referrer_code=eq.{ambassador_code}")
        supabase_update("referral_attempts", {"completed_at": datetime.now().isoformat()}, 
                       f"telegram_user_id=eq.{telegram_user_id},ambassador_code=eq.{ambassador_code}")
        
        ambassador_telegram_id = ambassador[0].get("telegram_id")
        if ambassador_telegram_id:
            send_message(int(ambassador_telegram_id), 
                        f"🎉 **New Referral!** 🎉\n\n"
                        f"Someone completed both steps using your link!\n"
                        f"Total points: **{current_count + 1}**")
        return True
    return False

# ===== PROCESS WL_RESPONSES =====
def process_wl_responses():
    responses = supabase_query("wl_responses", "processed=is.null")
    
    for response in responses:
        response_id = response.get("id")
        ambassador_code = response.get("referrer_code")
        telegram_user_id = response.get("telegram_user_id")
        
        if ambassador_code and telegram_user_id:
            joined = is_user_in_group(telegram_user_id)
            
            if joined:
                award_point(ambassador_code, telegram_user_id)
                print(f"✅ Point awarded to {ambassador_code} for user {telegram_user_id}")
            else:
                print(f"⚠️ User {telegram_user_id} submitted form but not in group yet")
        
        supabase_update("wl_responses", {"processed": True}, f"id=eq.{response_id}")
    
    return len(responses)

# ===== BOT COMMAND HANDLERS =====
def handle_command(chat_id, user_id, username, text):
    user_id_str = str(user_id)
    
    # First, check if user is in the group (for commands that require it)
    if text in ["/getlink", "/stats", "/top"]:
        if not is_user_in_group(user_id):
            # User not in group - show join button
            keyboard = {
                "inline_keyboard": [[
                    {"text": "🔗 Join AI Access Group", "url": GROUP_INVITE_LINK},
                    {"text": "✅ I've Joined", "callback_data": "check_join"}
                ]]
            }
            send_message(chat_id, 
                "⚠️ **You need to join our Telegram group first!**\n\n"
                "Click the button below to join, then click 'I've Joined' to continue.\n\n"
                "This is required to participate in the Ambassador Program.",
                reply_markup=keyboard)
            return
    
    # User is in group - process commands normally
    if text == "/start":
        send_message(chat_id, 
            "🎉 Welcome to AI Access Ambassador Program!\n\n"
            "📌 Commands:\n"
            "/getlink - Get your invite link\n"
            "/stats - Your referral points\n"
            "/top - Leaderboard\n\n"
            "How it works:\n"
            "1. Share your invite link\n"
            "2. Friends join Telegram group AND sign waitlist\n"
            "3. You get 1 point when they complete BOTH")
    
    elif text == "/getlink":
        code = str(uuid.uuid4())[:8]
        existing = supabase_query("ambassadors", f"telegram_id=eq.{user_id_str}")
        
        if not existing:
            supabase_insert("ambassadors", {
                "telegram_id": user_id_str,
                "username": username,
                "referrer_code": code,
                "referral_count": 0
            })
        else:
            code = existing[0]["referrer_code"]
        
        link = f"https://tally.so/r/{TALLY_FORM_ID}?referrer_id={code}"
        send_message(chat_id, f"🔗 YOUR INVITE LINK:\n\n{link}\n\nShare this link with friends!")
    
    elif text == "/stats":
        result = supabase_query("ambassadors", f"telegram_id=eq.{user_id_str}")
        if result:
            count = result[0].get("referral_count", 0)
            send_message(chat_id, f"📊 You've referred {count} people who completed both steps!")
        else:
            send_message(chat_id, "Type /getlink first to register as an ambassador!")
    
    elif text == "/top":
        result = supabase_query("ambassadors", "order=referral_count.desc&limit=10")
        if result:
            msg = "🏆 TOP 10 AMBASSADORS 🏆\n\n"
            for i, p in enumerate(result, 1):
                name = p.get("username", "Anonymous")[:15]
                count = p.get("referral_count", 0)
                msg += f"{i}. {name} — {count} point{'s' if count != 1 else ''}\n"
            send_message(chat_id, msg)
        else:
            send_message(chat_id, "No ambassadors yet! Be the first!")
    
    elif text == "/help":
        send_message(chat_id, "Commands: /start, /getlink, /stats, /top")

# ===== CALLBACK QUERY HANDLER (for "I've Joined" button) =====
def handle_callback_query(callback_query):
    chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
    user_id = callback_query.get("from", {}).get("id")
    data = callback_query.get("data", "")
    
    if data == "check_join":
        if is_user_in_group(user_id):
            send_message(chat_id, "✅ **Verified!** You're now a member of the group.\n\nYou can now use /getlink to start your ambassador journey! 🚀")
        else:
            send_message(chat_id, "❌ You haven't joined the group yet.\n\nPlease click the link below to join first, then click 'I've Joined' again.")
    
    # Answer the callback to remove loading state
    answer_callback(callback_query.get("id"))

# ===== MAIN LOOP =====
def main():
    print("🤖 AI Access Bot is running!")
    print(f"📌 Group ID: {GROUP_ID}")
    print(f"🔗 Group Invite Link: {GROUP_INVITE_LINK}")
    print("🔄 Waiting for messages...")
    
    last_id = 0
    last_process_time = time.time()
    
    while True:
        try:
            updates = get_updates(last_id + 1)
            
            if updates.get("ok"):
                for update in updates.get("result", []):
                    last_id = update["update_id"]
                    
                    # Handle callback queries (button clicks)
                    if "callback_query" in update:
                        handle_callback_query(update["callback_query"])
                    
                    # Handle regular messages
                    message = update.get("message", {})
                    if message:
                        chat_id = message.get("chat", {}).get("id")
                        user_id = message.get("from", {}).get("id")
                        username = message.get("from", {}).get("username") or message.get("from", {}).get("first_name", "")
                        text = message.get("text", "")
                        
                        if text and text.startswith("/"):
                            handle_command(chat_id, user_id, username, text)
            
            # Process wl_responses every 30 seconds
            if time.time() - last_process_time >= 30:
                count = process_wl_responses()
                if count > 0:
                    print(f"✅ Processed {count} new responses")
                last_process_time = time.time()
            
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(0.5)

if __name__ == "__main__":
    main()
