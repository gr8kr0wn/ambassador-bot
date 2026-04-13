import requests
import time
import uuid
import threading
from datetime import datetime

# ===== YOUR CONFIGURATION =====
TELEGRAM_TOKEN = "8664130966:AAGwmssIWvUzriVHuSML-NIayeqv588Lqf8"
SUPABASE_URL = "https://vminufdeufycbvlmnkvq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZtaW51ZmRldWZ5Y2J2bG1ua3ZxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU4ODc2ODksImV4cCI6MjA5MTQ2MzY4OX0.AYH9ih3BzAeiC5KK-AVel9l3CCKNYC3JozY4RvY_Ug8"
GROUP_ID = -1003777573948
TALLY_FORM_ID = "yPEDzx"

# ===== SUPABASE FUNCTIONS =====
def supabase_query(table, filters=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    if filters:
        url += f"?{filters}"
    response = requests.get(url, headers=headers)
    return response.json() if response.status_code == 200 else []

def supabase_insert(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    response = requests.post(url, headers=headers, json=data)
    return response.status_code == 201

def supabase_update(table, data, filters):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{filters}"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    response = requests.patch(url, headers=headers, json=data)
    return response.status_code == 200

# ===== TELEGRAM FUNCTIONS =====
def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

def is_user_in_group(user_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChatMember"
    params = {"chat_id": GROUP_ID, "user_id": user_id}
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.ok:
            status = response.json().get("result", {}).get("status")
            return status in ["member", "administrator", "creator"]
    except:
        return False
    return False

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"timeout": 20}
    if offset:
        params["offset"] = offset
    response = requests.get(url, params=params)
    return response.json()

# ===== PROCESSOR FUNCTION =====
def process_wl_responses():
    responses = supabase_query("wl_responses", "processed=is.null")
    for response in responses:
        ambassador_code = response.get("referrer_code")
        telegram_user_id = response.get("telegram_user_id")
        
        if ambassador_code and telegram_user_id:
            joined = is_user_in_group(telegram_user_id)
            
            if joined:
                # Award point
                ambassador = supabase_query("ambassadors", f"referrer_code=eq.{ambassador_code}")
                if ambassador:
                    current = ambassador[0].get("referral_count", 0)
                    supabase_update("ambassadors", {"referral_count": current + 1}, f"referrer_code=eq.{ambassador_code}")
                    send_message(int(ambassador[0]["telegram_id"]), f"🎉 New referral! Total: {current + 1}")
                    print(f"Point awarded to {ambassador_code}")
        
        supabase_update("wl_responses", {"processed": True}, f"id=eq.{response['id']}")

# ===== BOT COMMAND HANDLER =====
def handle_command(chat_id, user_id, username, text):
    if text == "/start":
        send_message(chat_id, "🎉 Welcome! Send /getlink to get your invite link")
    
    elif text == "/getlink":
        code = str(uuid.uuid4())[:8]
        existing = supabase_query("ambassadors", f"telegram_id=eq.{user_id}")
        if not existing:
            supabase_insert("ambassadors", {
                "telegram_id": str(user_id),
                "username": username,
                "referrer_code": code,
                "referral_count": 0
            })
        else:
            code = existing[0]["referrer_code"]
        
        link = f"https://tally.so/r/{TALLY_FORM_ID}?referrer_id={code}"
        send_message(chat_id, f"🔗 Your invite link:\n{link}")
    
    elif text == "/stats":
        result = supabase_query("ambassadors", f"telegram_id=eq.{user_id}")
        if result:
            send_message(chat_id, f"📊 You've referred {result[0]['referral_count']} people!")
        else:
            send_message(chat_id, "Type /getlink first")

# ===== MAIN FUNCTION (Runs Both) =====
def main():
    print("🤖 Bot and Processor running together!")
    last_id = 0
    last_process_time = time.time()
    
    while True:
        # Handle Telegram commands
        try:
            updates = get_updates(last_id + 1)
            if updates.get("ok"):
                for update in updates.get("result", []):
                    last_id = update["update_id"]
                    msg = update.get("message", {})
                    chat_id = msg.get("chat", {}).get("id")
                    user_id = msg.get("from", {}).get("id")
                    username = msg.get("from", {}).get("username") or msg.get("from", {}).get("first_name", "")
                    text = msg.get("text", "")
                    
                    if text and text.startswith("/"):
                        handle_command(chat_id, str(user_id), username, text)
        except Exception as e:
            print(f"Bot error: {e}")
        
        # Run processor every 30 seconds
        if time.time() - last_process_time >= 30:
            try:
                process_wl_responses()
            except Exception as e:
                print(f"Processor error: {e}")
            last_process_time = time.time()
        
        time.sleep(0.5)

if __name__ == "__main__":
    main()