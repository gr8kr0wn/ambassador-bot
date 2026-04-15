import requests
import uuid
import time
from datetime import datetime

# ===== YOUR CONFIGURATION =====
TELEGRAM_TOKEN = "8664130966:AAGwmssIWvUzriVHuSML-NIayeqv588Lqf8"
SUPABASE_URL = "https://vminufdeufycbvlmnkvq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZtaW51ZmRldWZ5Y2J2bG1ua3ZxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU4ODc2ODksImV4cCI6MjA5MTQ2MzY4OX0.AYH9ih3BzAeiC5KK-AVel9l3CCKNYC3JozY4RvY_Ug8"
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
        if response.status_code == 200:
            return response.json()
    except:
        pass
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
def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
    except:
        pass

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

# ===== PROCESS WL_RESPONSES =====
def process_wl_responses():
    responses = supabase_query("wl_responses", "processed=eq.false")
    
    count = 0
    for response in responses:
        response_id = response.get("id")
        ambassador_code = response.get("referrer_code")
        telegram_user_id = response.get("telegram_user_id")
        
        if ambassador_code and telegram_user_id:
            ambassador = supabase_query("ambassadors", f"referrer_code=eq.{ambassador_code}")
            if ambassador:
                current_count = ambassador[0].get("referral_count", 0)
                supabase_update("ambassadors", {"referral_count": current_count + 1}, f"referrer_code=eq.{ambassador_code}")
                
                ambassador_telegram_id = ambassador[0].get("telegram_id")
                if ambassador_telegram_id:
                    send_message(int(ambassador_telegram_id), f"🎉 New Referral! Total points: {current_count + 1}")
                count += 1
        
        supabase_update("wl_responses", {"processed": True}, f"id=eq.{response_id}")
    
    return count

# ===== BOT COMMAND HANDLERS =====
def handle_command(chat_id, user_id, username, text):
    user_id_str = str(user_id)
    
    if text == "/start":
        send_message(chat_id, "🎉 Welcome to AI Access Ambassador Program!\n\n/getlink - Get your invite link\n/stats - Your points\n/top - Leaderboard")
    
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
        send_message(chat_id, f"🔗 Your invite link:\n{link}")
    
    elif text == "/stats":
        result = supabase_query("ambassadors", f"telegram_id=eq.{user_id_str}")
        if result:
            count = result[0].get("referral_count", 0)
            send_message(chat_id, f"📊 You've referred {count} people!")
        else:
            send_message(chat_id, "Type /getlink first to register!")
    
    elif text == "/top":
        result = supabase_query("ambassadors", "order=referral_count.desc&limit=10")
        if result:
            msg = "🏆 TOP 10 AMBASSADORS 🏆\n\n"
            for i, p in enumerate(result, 1):
                msg += f"{i}. {p.get('username', 'Anonymous')} — {p.get('referral_count', 0)} points\n"
            send_message(chat_id, msg)
        else:
            send_message(chat_id, "No ambassadors yet!")
    
    elif text == "/process":
        count = process_wl_responses()
        send_message(chat_id, f"✅ Processed {count} pending referrals")

# ===== MAIN LOOP =====
def main():
    print("🤖 AI Access Bot is running!")
    last_id = 0
    last_process_time = time.time()
    
    while True:
        try:
            updates = get_updates(last_id + 1)
            
            if updates.get("ok"):
                for update in updates.get("result", []):
                    last_id = update["update_id"]
                    message = update.get("message", {})
                    if message:
                        chat_id = message.get("chat", {}).get("id")
                        user_id = message.get("from", {}).get("id")
                        username = message.get("from", {}).get("username") or message.get("from", {}).get("first_name", "")
                        text = message.get("text", "")
                        
                        if text and text.startswith("/"):
                            handle_command(chat_id, user_id, username, text)
            
            if time.time() - last_process_time >= 30:
                process_wl_responses()
                last_process_time = time.time()
            
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(0.5)

if __name__ == "__main__":
    main()
