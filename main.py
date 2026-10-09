import os
import requests

def send_message(text):
    # این توکن از تنظیمات امنیتی گیتهاب (Secrets) خونده می‌شه
    token = os.environ.get("RUBIKA_TOKEN")
    chat_id = "@akbarvateknologi"
    
    # آدرس ای‌پی‌آی روبیکا
    url = f"https://messenger.rubika.ir/api/v1?token={token}"
    
    payload = {
        "text": text + "\n\n@akbarvateknologi",
        "chat_id": chat_id
    }
    
    try:
        response = requests.post(url, json=payload)
        print(f"Status Code: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")
print("Bot is starting...")
# بقیه کدها...
