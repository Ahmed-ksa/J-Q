from telebot import TeleBot
import requests
import datetime
import pyrebase
from keep_alive import keep_alive
import os
from dotenv import load_dotenv

load_dotenv()
keep_alive()

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

BOT_TOKEN = os.getenv("BOT_TOKEN")
TAP_SECRET_KEY = os.getenv("TAP_SECRET_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

bot = TeleBot(BOT_TOKEN, parse_mode="HTML")

@bot.message_handler(commands=['start', 'help'])
def handle_start(message):
    bot.reply_to(message, "👋 مرحبًا! الأوامر المتاحة:\n\n"
                          "🟢 /subscribe - الاشتراك بالخدمة\n"
                          "🔄 /renew - تجديد الاشتراك\n"
                          "📊 /status - حالة الاشتراك\n"
                          "🔐 /credentials - اسم المستخدم وكلمة المرور")

@bot.message_handler(commands=['subscribe', 'renew'])
def handle_subscribe(message):
    chat_id = str(message.chat.id)
    url = create_checkout_link(chat_id)
    bot.send_message(chat_id, f"""🔗 <b>رابط الدفع الخاص بك:</b>
<a href="{url}">اضغط هنا لإتمام عملية الدفع</a>

📩 بعد الدفع سيتم إرسال اسم المستخدم وكلمة المرور الخاصة بك تلقائيًا.""")

@bot.message_handler(commands=['status'])
def check_status(message):
    chat_id = str(message.chat.id)
    user = db.child("users").child(chat_id).get().val()
    if not user:
        bot.reply_to(message, "❌ لا يوجد اشتراك مرتبط بهذا الحساب.")
        return

    expiry_str = user.get("expiry")
    expiry_date = datetime.datetime.strptime(expiry_str, "%Y-%m-%d").date()
    today = datetime.date.today()

    if today > expiry_date:
        bot.reply_to(message, f"📛 انتهى اشتراكك بتاريخ {expiry_str}.")
    else:
        days_left = (expiry_date - today).days
        bot.reply_to(message, f"✅ اشتراكك نشط. ينتهي بتاريخ {expiry_str}.\n🕓 متبقي: {days_left} يوم.")

@bot.message_handler(commands=['credentials'])
def get_credentials(message):
    chat_id = str(message.chat.id)
    user = db.child("users").child(chat_id).get().val()
    if not user:
        bot.reply_to(message, "❌ لا يوجد اشتراك مرتبط بهذا الحساب.")
        return

    expiry_str = user.get("expiry")
    expiry_date = datetime.datetime.strptime(expiry_str, "%Y-%m-%d").date()
    today = datetime.date.today()

    if today > expiry_date:
        bot.reply_to(message, f"📛 انتهى اشتراكك بتاريخ {expiry_str}. لا يمكن عرض البيانات.")
    else:
        password = user.get("password", "غير متوفر")
        bot.send_message(chat_id, f"""🔐 <b>بيانات حسابك:</b>

👤 <b>اسم المستخدم:</b> <code>{chat_id}</code>
🔒 <b>كلمة المرور:</b> <code>{password}</code>
📅 <b>تاريخ الانتهاء:</b> <code>{expiry_str}</code>

⚠️ يُمنع مشاركة الحساب مع الآخرين.""")

@bot.message_handler(func=lambda message: message.text.strip().startswith("تغيير السعر"))
def change_price(message):
    if str(message.chat.id) != ADMIN_ID:
        return bot.reply_to(message, "❌ ليس لديك صلاحية تعديل السعر.")
    try:
        parts = message.text.strip().split()
        if len(parts) < 3:
            raise ValueError("Missing price")
        new_price = float(parts[2])
        db.child("config").child("price").set(new_price)
        bot.reply_to(message, f"✅ تم تحديث السعر إلى {new_price} ريال.")
    except:
        bot.reply_to(message, "⚠️ الصيغة الصحيحة:\nتغيير السعر 500")

def get_current_price():
    price = db.child("config").child("price").get().val()
    return float(price) if price else 350.0

def create_checkout_link(internal_id):
    headers = {
        "Authorization": "Bearer " + TAP_SECRET_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "amount": get_current_price(),
        "currency": "SAR",
        "customer": {
            "first_name": "TelegramUser",
            "email": f"{internal_id}@example.com"
        },
        "source": {"id": "src_all"},
        "redirect": {
            "url": "https://yourdomain.com/success"
        },
        "post": {
            "url": "https://yourdomain.com/tap_webhook"
        },
        "metadata": {
            "internal_id": internal_id
        }
    }
    response = requests.post("https://api.tap.company/v2/charges", headers=headers, json=payload)
    return response.json()["transaction"]["url"]

bot.polling()
