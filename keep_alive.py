from flask import Flask, request, jsonify
from threading import Thread
import datetime
import os
import pyrebase
from dotenv import load_dotenv
from telebot import TeleBot
import secrets

load_dotenv()

# === Firebase =========================================================
firebaseConfig = {
    "apiKey": os.getenv("FIREBASE_API_KEY"),
    "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
    "databaseURL": os.getenv("FIREBASE_DB_URL"),
    "projectId": os.getenv("FIREBASE_PROJECT_ID"),
    "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
    "messagingSenderId": os.getenv("FIREBASE_MSG_ID"),
    "appId": os.getenv("FIREBASE_APP_ID")
}
firebase = pyrebase.initialize_app(firebaseConfig)
db = firebase.database()

# === Telegram Bot =====================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = TeleBot(BOT_TOKEN, parse_mode="HTML")

# === Flask app ========================================================
app = Flask(__name__)


@app.route('/')
def home():
    return "✅ Bot is alive!"


# ----------------------------------------------------------------------
# Paylink webhook (حالي)
# ----------------------------------------------------------------------
@app.route('/paylink_webhook', methods=['POST'])
def paylink_webhook():
    data = request.json or {}
    if data.get("status") == "PAID":
        chat_id = str(data.get("orderNumber"))
        if chat_id:
            db.child("users").child(chat_id).update({
                "active": True,
                "paid_at": datetime.date.today().isoformat()
            })
            bot.send_message(chat_id, "✅ تم تفعيل اشتراكك بنجاح (Paylink).")
    return jsonify({"message": "OK"}), 200


# ----------------------------------------------------------------------
# Moyasar webhook (جديد)
# ----------------------------------------------------------------------
@app.route('/moyasar_webhook', methods=['POST'])
def moyasar_webhook():
    data = request.json or {}
    if data.get("status") != "paid":
        return jsonify({"message": "ignored"}), 200

    meta = data.get("metadata", {})
    chat_id = str(meta.get("telegram_chat_id", ""))

    if not chat_id.isdigit():
        return jsonify({"message": "no chat id"}), 400

    # إنشاء بيانات الاشتراك
    expiry = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    password = secrets.token_hex(4)

    db.child("users").child(chat_id).set({
        "active": True,
        "expiry": expiry,
        "password": password,
        "paid_at": datetime.date.today().isoformat()
    })

    bot.send_message(
        chat_id,
        f"""✅ <b>تم تفعيل اشتراكك بنجاح</b>

👤 <b>اسم المستخدم:</b> <code>{chat_id}</code>
🔒 <b>كلمة المرور:</b> <code>{password}</code>
📅 <b>تاريخ الانتهاء:</b> <code>{expiry}</code>

مرحباً بك في SIGMATOR!"""
    )

    return jsonify({"message": "done"}), 200


# === runner ===========================================================
def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    Thread(target=run, daemon=True).start()
