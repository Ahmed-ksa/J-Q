from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import datetime
import pyrebase
import os
from dotenv import load_dotenv
import base64
import re
from keep_alive import keep_alive

# ---------------------------------------------------------------------------
# التهيئة العامة
# ---------------------------------------------------------------------------

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

BOT_TOKEN          = os.getenv("BOT_TOKEN")
MOYASAR_SECRET_KEY = os.getenv("MOYASAR_SECRET_KEY")
ADMIN_ID           = os.getenv("ADMIN_ID")  # نخزنه كسلسلة للمقارنة المباشرة

bot = TeleBot(BOT_TOKEN, parse_mode="HTML")

# ---------------------------------------------------------------------------
# أدوات مساعدة
# ---------------------------------------------------------------------------

def get_setting(key, default=None):
    """يجلب قيمة إعداد من Firebase ويضبط قيمة افتراضية عند اللزوم"""
    setting = db.child("config/settings").child(key).get().val()
    if setting is None:
        if key == "customer_service_username":
            default = "hassan_jumaie"
        elif key == "program_download_link":
            default = "https://example.com/program.exe"
        elif key == "program_requirements_text":
            default = "يتطلب نظام ويندوز ويفضل إيقاف برنامج مكافحة الفيروسات كي يعمل البرنامج بشكل سليم."
        elif key == "user_guide_content":
            default = {
                "type": "link",
                "value": "https://example.com/user_guide.pdf",
                "caption": "دليل المستخدم الخاص بك"
            }
        if default is not None:
            db.child("config/settings").child(key).set(default)
            return default
    return setting if setting is not None else default

# ---------------------------------------------------------------------------
# أوامر البداية
# ---------------------------------------------------------------------------

@bot.message_handler(commands=["start", "help"])
def handle_start(message):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🟢 اشتراك", callback_data="subscribe"),
        InlineKeyboardButton("🔄 تجديد", callback_data="renew"),
        InlineKeyboardButton("📊 حالة الاشتراك", callback_data="status"),
        InlineKeyboardButton("🔐 بيانات الدخول", callback_data="credentials"),
        InlineKeyboardButton("📞 خدمة العملاء", callback_data="customer_service"),
        InlineKeyboardButton("⬇️ تثبيت البرنامج", callback_data="install_program"),
        InlineKeyboardButton("📚 دليل المستخدم", callback_data="user_guide")
    )
    bot.send_message(message.chat.id, "👋 مرحبًا! اختر أحد الخيارات أدناه:", reply_markup=markup)

# ---------------------------------------------------------------------------
# معالجات الأزرار المضمنة
# ---------------------------------------------------------------------------

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = str(call.message.chat.id)
    bot.answer_callback_query(call.id)

    if call.data in ("subscribe", "renew"):
        handle_subscribe_action(chat_id)
    elif call.data == "status":
        check_status_action(chat_id)
    elif call.data == "credentials":
        get_credentials_action(chat_id)
    elif call.data == "customer_service":
        send_customer_service_info(chat_id)
    elif call.data == "install_program":
        send_program_info(chat_id)
    elif call.data == "user_guide":
        send_user_guide(chat_id)

# ---------------------------------------------------------------------------
# الاشتراك والدفع
# ---------------------------------------------------------------------------

def get_current_price() -> float:
    price = db.child("config/price").get().val()
    return float(price) if price else 350.0


def create_checkout_link(chat_id: str) -> str:
    if not MOYASAR_SECRET_KEY:
        raise RuntimeError("MOYASAR_SECRET_KEY غير مضبوط")

    auth_header = base64.b64encode(f"{MOYASAR_SECRET_KEY}:".encode()).decode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {auth_header}"
    }

    payload = {
        "amount": int(get_current_price() * 100),
        "currency": "SAR",
        "description": "اشتراك SIGMATOR BOT",
        "callback_url": "https://yourdomain.com/moyasar_webhook",
        "success_url": "https://yourdomain.com/success",
        "metadata": {"telegram_chat_id": chat_id}
    }

    r = requests.post("https://api.moyasar.com/v1/invoices", headers=headers, json=payload)
    r.raise_for_status()
    return r.json()["url"]


def handle_subscribe_action(chat_id: str):
    try:
        url = create_checkout_link(chat_id)
        bot.send_message(
            chat_id,
            f"""🔗 <b>رابط الدفع الخاص بك:</b>\n<a href=\"{url}\">اضغط هنا لإتمام عملية الدفع</a>\n\n📩 بعد الدفع سيتم إرسال اسم المستخدم وكلمة المرور تلقائيًا."""
        )
    except Exception as e:
        bot.send_message(chat_id, f"❌ حدث خطأ أثناء إنشاء رابط الدفع: {e}")

# ---------------------------------------------------------------------------
# حالة الاشتراك وبيانات الدخول
# ---------------------------------------------------------------------------

def check_status_action(chat_id: str):
    user = db.child("users").child(chat_id).get().val()
    if not user:
        bot.send_message(chat_id, "❌ لا يوجد اشتراك مرتبط بهذا الحساب.")
        return

    expiry_str = user.get("expiry")
    if not expiry_str:
        bot.send_message(chat_id, "❌ لا يوجد تاريخ انتهاء صلاحية مسجل.")
        return

    try:
        expiry_date = datetime.datetime.strptime(expiry_str, "%Y-%m-%d").date()
        today = datetime.date.today()
        if today > expiry_date:
            bot.send_message(chat_id, f"📛 انتهى اشتراكك بتاريخ {expiry_str}.")
        else:
            days_left = (expiry_date - today).days
            bot.send_message(chat_id, f"✅ اشتراكك نشط حتى {expiry_str}.\n🕓 متبقٍ: {days_left} يوم.")
    except ValueError:
        bot.send_message(chat_id, "❌ تنسيق تاريخ غير صالح. تواصل مع الدعم.")


def get_credentials_action(chat_id: str):
    user = db.child("users").child(chat_id).get().val()
    if not user:
        bot.send_message(chat_id, "❌ لا يوجد اشتراك مرتبط بهذا الحساب.")
        return

    expiry_str = user.get("expiry")
    if not expiry_str:
        bot.send_message(chat_id, "❌ لا يوجد تاريخ انتهاء مسجل.")
        return

    try:
        expiry_date = datetime.datetime.strptime(expiry_str, "%Y-%m-%d").date()
        if datetime.date.today() > expiry_date:
            bot.send_message(chat_id, f"📛 انتهى اشتراكك بتاريخ {expiry_str}.")
        else:
            password = user.get("password", "غير متوفر")
            bot.send_message(
                chat_id,
                f"""🔐 <b>بيانات حسابك:</b>\n\n👤 <b>اسم المستخدم:</b> <code>{chat_id}</code>\n🔒 <b>كلمة المرور:</b> <code>{password}</code>\n📅 <b>تاريخ الانتهاء:</b> <code>{expiry_str}</code>\n\n⚠️ يُمنع مشاركة الحساب."""
            )
    except ValueError:
        bot.send_message(chat_id, "❌ تنسيق تاريخ غير صالح.")

# ---------------------------------------------------------------------------
# رسائل المعلومات
# ---------------------------------------------------------------------------

def send_customer_service_info(chat_id):
    bot.send_message(chat_id, f"للتواصل مع خدمة العملاء: @{get_setting('customer_service_username')}")


def send_program_info(chat_id):
    bot.send_message(
        chat_id,
        f"""⬇️ <b>تثبيت البرنامج:</b>\n\n🔗 <b>رابط:</b> <a href='{get_setting('program_download_link')}'>اضغط هنا</a>\n\n📝 <b>المتطلبات:</b>\n{get_setting('program_requirements_text')}"""
    )


def send_user_guide(chat_id):
    data = get_setting("user_guide_content")
    if not data or not data.get("value"):
        bot.send_message(chat_id, "⚠️ لا يتوفر دليل المستخدم حاليًا.")
        return

    if data.get("type") == "file_id":
        try:
            bot.send_document(chat_id, data["value"], caption=data.get("caption", "دليل المستخدم"))
        except Exception:
            bot.send_message(chat_id, "❌ خطأ في إرسال ملف الدليل.")
    else:
        bot.send_message(chat_id, f"📚 <b>{data.get('caption', 'دليل المستخدم')}</b>\n\n<a href='{data['value']}'>اضغط هنا</a>")

# ---------------------------------------------------------------------------
# تغيير السعر السريع
# ---------------------------------------------------------------------------

@bot.message_handler(func=lambda m: m.text and m.text.startswith("تغيير السعر") and str(m.chat.id) == ADMIN_ID)
def change_price(message):
    try:
        new_price = float(message.text.split()[2])
        db.child("config/price").set(new_price)
        bot.reply_to(message, f"✅ تم تحديث السعر إلى {new_price} ريال.")
    except Exception as e:
        bot.reply_to(message, f"⚠️ الصيغة الصحيحة: تغيير السعر 500 → {e}")

# ---------------------------------------------------------------------------
# أمر التعيين العام (الحل الأقوى والمرن)
# ---------------------------------------------------------------------------

SETTINGS_MAP = {
    "خدمةالعملاء": ("settings/customer_service_username", lambda v: v),
    "رابطالبرنامج": ("settings/program_download_link", lambda v: v),
    "متطلباتالبرنامج": ("settings/program_requirements_text", lambda v: v),
    "دليلالمستخدمرابط": ("settings/user_guide_content", lambda v: {"type": "link", "value": v}),
    "دليلالمستخدمملف": ("settings/user_guide_content", lambda v: {"type": "file_id", "value": v}),
    "دليلالمستخدمعنوان": ("settings/user_guide_content", lambda v: {"caption": v}),
    "سعرالاشتراك": ("price", lambda v: float(v))
}


@bot.message_handler(func=lambda m: str(m.chat.id) == ADMIN_ID and m.text and m.text.startswith("تعيين"))
def set_config_value(message):
    try:
        m = re.match(r"^تعيين\s+(.+?)\s+(.+)$", message.text.strip())
        if not m:
            bot.reply
