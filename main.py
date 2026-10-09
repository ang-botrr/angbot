import os
import requests

def send_message(text):
    # این توکن باید توی تنظیماتِ Secret گیتهاب تعریف شده باشه
    token = os.environ.get("CGECFE0LPXWGBDZFFSAIIIJMIHQDGLFULRYLUONIRBLRYEYMAXYJTMUIXTLQWEUQ")
    chat_id = "@akbarvateknologi"

    # نکته: مطمئن شو این URL دقیقاً همون چیزیه که مستنداتِ رباتت گفته
    url = "https://messenger.rubika.ir/api/v1/sendMessage" # این فقط یه نمونه‌ست!

    payload = {
        "text": text + "\n\n@akbarvateknologi",
        "chat_id": chat_id
    }
    
    # اضافه کردنِ هدر (احتمالاً برای احراز هویت لازمه)
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

print("Done")
