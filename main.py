import os
import sys
import re
import json
import html
import time
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import feedparser

# ---------------- تنظیمات ----------------
TOKEN = os.environ.get("RUBIKA_TOKEN", "")
OWNER = os.environ.get("OWNER_CHAT_ID", "")      # چت‌آیدی پیوی شما با ربات
CHANNEL = os.environ.get("CHANNEL_ID", "")       # چت‌آیدی (guid) کانال
FOOTER = "@akbarvateknologi"

BASE = f"https://botapi.rubika.ir/v3/{TOKEN}/"
TZ = ZoneInfo("Asia/Tehran")
STATE_FILE = "state.json"

DIGEST_HOUR = 6          # از این ساعت به بعد، لیست روزانه برای تایید فرستاده می‌شود
DAILY_TOPICS = 50
POST_START_HOUR = 7      # بازه ارسال پست در کانال: ۷ صبح تا ۱۲ شب
POST_END_HOUR = 23
POLL_EVERY_DAYS = 3

# فیدهای فارسی (اگر آدرسی کار نکرد، عوض یا حذفش کن)
FEEDS = [
    ("tech", "https://www.zoomit.ir/feed/"),
    ("tech", "https://digiato.com/feed"),
    ("tech", "https://www.itna.ir/feed/"),
    ("game", "https://www.gamefa.com/feed/"),
    ("game", "https://www.gameland.ir/feed/"),
    ("game", "https://farsroid.com/feed/"),
]

POLLS = [
    ("بیشتر از چه پلتفرمی بازی می‌کنی؟", ["کامپیوتر", "پلی‌استیشن", "ایکس‌باکس", "موبایل"]),
    ("گوشی فعلیت چه برندیه؟", ["سامسونگ", "شیائومی", "اپل", "بقیه"]),
    ("کدام ژانر بازی رو بیشتر دوست داری؟", ["اکشن", "نقش‌آفرینی (RPG)", "استراتژی", "ورزشی"]),
    ("از چه سیستم‌عاملی استفاده می‌کنی؟", ["ویندوز", "لینوکس", "مک", "اندروید/iOS"]),
    ("محتوای کانال رو چطور می‌بینی؟", ["عالی", "خوب", "معمولی", "باید بهتر بشه"]),
    ("بیشتر چه خبری رو دوست داری ببینی؟", ["اخبار گیم", "اخبار موبایل", "هوش مصنوعی", "سخت‌افزار"]),
]

# ---------------- ابزارها ----------------
def api(method, data):
    try:
        r = requests.post(BASE + method, json=data, timeout=30)
        res = r.json()
    except Exception as e:
        print(f"[{method}] error: {e}")
        return None
    if res.get("status") != "OK":
        print(f"[{method}] bad response: {res}")
        return None
    return res.get("data", {})


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            st = json.load(f)
    else:
        st = {}
    st.setdefault("offset_id", "")
    st.setdefault("candidates", {})
    st.setdefault("queue", [])
    st.setdefault("seen", [])
    st.setdefault("digest_date", "")
    st.setdefault("morning_date", "")
    st.setdefault("night_date", "")
    st.setdefault("last_poll", "")
    st.setdefault("poll_index", 0)
    return st


def save_state(st):
    st["seen"] = st["seen"][-3000:]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj and obj[key]:
            return obj[key]
        for v in obj.values():
            r = find_key(v, key)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_key(v, key)
            if r:
                return r
    return None


def clean_text(s, limit=450):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = re.sub(r"https?://\S+|www\.\S+", "", s)           # حذف لینک سایت‌ها
    s = re.sub(r"(ادامه (مطلب|خبر).*|appeared first on.*|The post .*)", "", s, flags=re.S)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0] + "…"
    return s


def build_post(c):
    icon = "🎮" if c["cat"] == "game" else "💻"
    parts = [f"{icon} {c['title']}"]
    if c.get("summary"):
        parts.append(c["summary"])
    parts.append(FOOTER)
    return "\n\n".join(parts)


# ---------------- ارسال‌ها ----------------
def send(chat, text, keypad=None):
    data = {"chat_id": chat, "text": text}
    if keypad:
        data["inline_keypad"] = keypad
    return api("sendMessage", data)


def review_keypad(cid):
    return {"rows": [{"buttons": [
        {"id": f"ok:{cid}", "type": "Simple", "button_text": "✅ تایید"},
        {"id": f"no:{cid}", "type": "Simple", "button_text": "❌ رد"},
    ]}]}


# ---------------- منطق اصلی ----------------
def process_updates(st):
    data = api("getUpdates", {"offset_id": st["offset_id"], "limit": 100} if st["offset_id"] else {"limit": 100})
    if not data:
        return
    ok = no = 0
    for u in data.get("updates", []):
        chat = find_key(u, "chat_id")
        bid = find_key(u, "button_id")
        if not bid or str(chat) != str(OWNER):
            continue
        action, _, cid = str(bid).partition(":")
        c = st["candidates"].get(cid)
        if not c or c["status"] != "pending":
            continue
        if action == "ok":
            c["status"] = "approved"
            st["queue"].append(cid)
            ok += 1
        elif action == "no":
            c["status"] = "rejected"
            no += 1
    nxt = data.get("next_offset_id")
    if nxt:
        st["offset_id"] = nxt
    if ok or no:
        send(OWNER, f"✅ {ok} پست تایید شد، ❌ {no} رد شد. در صف: {len(st['queue'])}")


def fetch_candidates(st):
    per_feed = []
    for cat, url in FEEDS:
        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
        except Exception as e:
            print("feed error", url, e)
            continue
        items = []
        for e in feed.entries[:30]:
            link = e.get("link", "")
            cid = hashlib.md5(link.encode()).hexdigest()[:10]
            if not link or cid in st["seen"] or cid in st["candidates"]:
                continue
            title = clean_text(e.get("title", ""), 200)
            if not title:
                continue
            summary = clean_text(e.get("summary", "") or e.get("description", ""))
            items.append((cid, {"cat": cat, "title": title, "summary": summary,
                                "link": link, "status": "pending", "ts": time.time()}))
        per_feed.append(items)
        print(f"{url}: {len(items)} new")
    # ترکیب نوبتی از همه منابع
    picked = []
    i = 0
    while len(picked) < DAILY_TOPICS and any(per_feed):
        for items in per_feed:
            if i < len(items) and len(picked) < DAILY_TOPICS:
                picked.append(items[i])
        i += 1
        if i > 60:
            break
    return picked


def send_digest(st, today):
    # پاک‌سازی موضوع‌های قدیمی که در صف نیستند
    limit = time.time() - 3 * 86400
    for cid in list(st["candidates"]):
        c = st["candidates"][cid]
        if c["ts"] < limit and cid not in st["queue"]:
            del st["candidates"][cid]
    picked = fetch_candidates(st)
    if not picked:
        print("no new topics")
        return
    send(OWNER, f"📋 {len(picked)} موضوع امروز برای تایید:")
    for cid, c in picked:
        text = f"{'🎮' if c['cat'] == 'game' else '💻'} {c['title']}\n\n{c['summary']}\n\n🔗 {c['link']}"
        if send(OWNER, text, review_keypad(cid)) is not None:
            st["candidates"][cid] = c
            st["seen"].append(cid)
        time.sleep(0.6)
    st["digest_date"] = today


def post_next(st):
    while st["queue"]:
        cid = st["queue"][0]
        c = st["candidates"].get(cid)
        if not c:
            st["queue"].pop(0)
            continue
        if send(CHANNEL, build_post(c)) is not None:
            st["queue"].pop(0)
            c["status"] = "posted"
            print("posted", cid)
        return


def send_poll(st, now):
    q, opts = POLLS[st["poll_index"] % len(POLLS)]
    if api("sendPoll", {"chat_id": CHANNEL, "question": q, "options": opts}) is not None:
        st["poll_index"] += 1
        st["last_poll"] = now.strftime("%Y-%m-%d")


def run():
    st = load_state()
    now = datetime.now(TZ)
    today = now.strftime("%Y-%m-%d")
    h = now.hour

    process_updates(st)

    if h >= DIGEST_HOUR and st["digest_date"] != today:
        send_digest(st, today)

    if 7 <= h < 12 and st["morning_date"] != today:
        if send(CHANNEL, f"☀️ صبح بخیر دوستان\nروز خوبی داشته باشید 🌹\n\n{FOOTER}") is not None:
            st["morning_date"] = today

    if h in (0, 1) and st["night_date"] != today:
        if send(CHANNEL, f"🌙 شب بخیر دوستان\nشبتون پر از آرامش 😴\n\n{FOOTER}") is not None:
            st["night_date"] = today

    if POST_START_HOUR <= h <= POST_END_HOUR:
        if 12 <= h <= 21:
            last = st["last_poll"]
            if not last or (now.date() - datetime.strptime(last, "%Y-%m-%d").date()).days >= POLL_EVERY_DAYS:
                send_poll(st, now)
        post_next(st)

    save_state(st)


def show_ids():
    data = api("getUpdates", {"limit": 100})
    seen = set()
    for u in (data or {}).get("updates", []):
        chat = find_key(u, "chat_id")
        if chat and chat not in seen:
            seen.add(chat)
            print("chat_id:", chat)
    if not seen:
        print("هیچ آپدیتی نیست. به ربات پیام بده (یا توی کانال پست بذار) و دوباره اجرا کن.")


if __name__ == "__main__":
    if not TOKEN:
        sys.exit("RUBIKA_TOKEN تنظیم نشده")
    if len(sys.argv) > 1 and sys.argv[1] == "ids":
        show_ids()
    else:
        run()
