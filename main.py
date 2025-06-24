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
ADMIN_ID           = os.getenv("ADMIN_ID")

bot = TeleBot(BOT_TOKEN, parse_mode="HTML")

# ---------------------------------------------------------------------------

def get_setting(key, default=None):
    setting = db.child("config").child("settings").child(key).get().val()
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
            db.child("config").child("settings").child(key).set(default)
            return default
    return setting if setting is not None else default

# ---------------------------------------------------------------------------

@bot.message_handler(commands=['start', 'help'])
def handle_start(message):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🟢 اشتراك",          callback_data="subscribe"),
        InlineKeyboardButton("🔄 تجديد",           callback_data="renew"),
        InlineKeyboardButton("📊 حالة الاشتراك",    callback_data="status"),
        InlineKeyboardButton("🔐 بيانات الدخول",    callback_data="credentials"),
        InlineKeyboardButton("📞 خدمة العملاء",      callback_data="customer_service"),
        InlineKeyboardButton("⬇️ تثبيت البرنامج",    callback_data="install_program"),
        InlineKeyboardButton("📚 دليل المستخدم",    callback_data="user_guide")
    )
    bot.send_message(
        message.chat.id,
        "👋 مرحبًا! اختر أحد الخيارات أدناه:",
        reply_markup=markup
    )

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
# عمليات الاشتراك

def handle_subscribe_action(chat_id):
    try:
        url = create_checkout_link(chat_id)
        bot.send_message(
            chat_id,
            f"""🔗 <b>رابط الدفع الخاص بك:</b>
<a href="{url}">اضغط هنا لإتمام عملية الدفع</a>

📩 بعد الدفع سيتم إرسال اسم المستخدم وكلمة المرور الخاصة بك تلقائيًا."""
        )
    except Exception as e:
        bot.send_message(chat_id, f"❌ حدث خطأ أثناء إنشاء رابط الدفع: {e}")
        print(f"Error creating checkout link for {chat_id}: {e}")

# ---------------------------------------------------------------------------
# حالة الاشتراك وبيانات الدخول

def check_status_action(chat_id):
    user = db.child("users").child(chat_id).get().val()
    if not user:
        bot.send_message(chat_id, "❌ لا يوجد اشتراك مرتبط بهذا الحساب.")
        return

    expiry_str = user.get("expiry")
    if not expiry_str:
        bot.send_message(chat_id, "❌ لا يوجد تاريخ انتهاء صلاحية مسجل لاشتراكك.")
        return

    try:
        expiry_date = datetime.datetime.strptime(expiry_str, "%Y-%m-%d").date()
        today       = datetime.date.today()

        if today > expiry_date:
            bot.send_message(chat_id, f"📛 انتهى اشتراكك بتاريخ {expiry_str}.")
        else:
            days_left = (expiry_date - today).days
            bot.send_message(
                chat_id,
                f"✅ اشتراكك نشط وينتهي بتاريخ {expiry_str}.\n🕓 متبقٍ: {days_left} يوم."
            )
    except ValueError:
        bot.send_message(chat_id, "❌ هناك مشكلة في تنسيق تاريخ الانتهاء. تواصل مع الدعم.")

def get_credentials_action(chat_id):
    user = db.child("users").child(chat_id).get().val()
    if not user:
        bot.send_message(chat_id, "❌ لا يوجد اشتراك مرتبط بهذا الحساب.")
        return

    expiry_str = user.get("expiry")
    if not expiry_str:
        bot.send_message(chat_id, "❌ لا يوجد تاريخ انتهاء صلاحية مسجل لاشتراكك.")
        return

    try:
        expiry_date = datetime.datetime.strptime(expiry_str, "%Y-%m-%d").date()
        if datetime.date.today() > expiry_date:
            bot.send_message(chat_id, f"📛 انتهى اشتراكك بتاريخ {expiry_str}.")
        else:
            password = user.get("password", "غير متوفر")
            bot.send_message(
                chat_id,
                f"""🔐 <b>بيانات حسابك:</b>

👤 <b>اسم المستخدم:</b> <code>{chat_id}</code>
🔒 <b>كلمة المرور:</b> <code>{password}</code>
📅 <b>تاريخ الانتهاء:</b> <code>{expiry_str}</code>

⚠️ يُمنع مشاركة الحساب."""
            )
    except ValueError:
        bot.send_message(chat_id, "❌ تنسيق تاريخ غير صالح. تواصل مع الدعم.")

# ---------------------------------------------------------------------------
# معلومات إضافية

def send_customer_service_info(chat_id):
    username = get_setting("customer_service_username")
    bot.send_message(chat_id, f"للتواصل مع خدمة العملاء: @{username}")

def send_program_info(chat_id):
    link         = get_setting("program_download_link")
    requirements = get_setting("program_requirements_text")
    bot.send_message(
        chat_id,
        f"""⬇️ <b>تثبيت البرنامج:</b>

🔗 <b>رابط التحميل:</b> <a href="{link}">اضغط هنا</a>

📝 <b>المتطلبات:</b>
{requirements}"""
    )

def send_user_guide(chat_id):
    data        = get_setting("user_guide_content")
    guide_type  = data.get("type", "link")
    guide_value = data.get("value")
    caption     = data.get("caption", "دليل المستخدم:")

    if not guide_value:
        bot.send_message(chat_id, "⚠️ لا يتوفر دليل المستخدم حاليًا.")
        return

    if guide_type == "link":
        bot.send_message(chat_id, f"📚 <b>{caption}</b>\n\n<a href='{guide_value}'>اضغط هنا</a>")
    elif guide_type == "file_id":
        try:
            bot.send_document(chat_id, guide_value, caption=caption)
        except Exception:
            bot.send_message(chat_id, "❌ خطأ في إرسال ملف الدليل. تحقق من File ID.")
    else:
        bot.send_message(chat_id, "⚠️ نوع دليل غير مدعوم.")

# ---------------------------------------------------------------------------
# تغيير السعر (يمكن تركه أو حذفه إذا ستستخدم «تعيين سعر الاشتراك» فقط)

@bot.message_handler(func=lambda m: m.text and
                     m.text.strip().startswith("تغيير السعر") and
                     str(m.chat.id) == ADMIN_ID)
def change_price(message):
    try:
        new_price = float(message.text.strip().split()[2])
        db.child("config").child("price").set(new_price)
        bot.reply_to(message, f"✅ تم تحديث السعر إلى {new_price} ريال.")
    except Exception as e:
        bot.reply_to(message, f"⚠️ الصيغة الصحيحة: تغيير السعر 500  ➜  {e}")

# ---------------------------------------------------------------------------
# أوامر التعيين للمشرف

@bot.message_handler(func=lambda m: str(m.chat.id) == ADMIN_ID and
                     m.text and m.text.strip().startswith("تعيين"))
def set_config_value(message):
    try:
        m = re.match(r'^تعيين\s+(.+?)\s+(.+)$', message.text.strip())
        if not m:
            bot.reply_to(message, "⚠️ الصيغة: تعيين [اسم الإعداد] [القيمة]")
            return

        key   = m.group(1).strip()
        value = m.group(2).strip()

        if key == "خدمة العملاء":
            db.child("config/settings/customer_service_username").set(value)
            bot.reply_to(message, f"✅ تم تحديث خدمة العملاء إلى @{value}")
        elif key == "رابط البرنامج":
            db.child("config/settings/program_download_link").set(value)
            bot.reply_to(message, "✅ تم تحديث رابط البرنامج.")
        elif key == "متطلبات البرنامج":
            db.child("config/settings/program_requirements_text").set(value)
            bot.reply_to(message, "✅ تم تحديث متطلبات البرنامج.")
        elif key == "دليل المستخدم رابط":
            db.child("config/settings/user_guide_content").update({"type": "link", "value": value})
            bot.reply_to(message, "✅ تم تحديث رابط دليل المستخدم.")
        elif key == "دليل المستخدم ملف":
            db.child("config/settings/user_guide_content").update({"type": "file_id", "value": value})
            bot.reply_to(message, "✅ تم تحديث ملف دليل المستخدم.")
        elif key == "دليل المستخدم عنوان":
            db.child("config/settings/user_guide_content").update({"caption": value})
            bot.reply_to(message, "✅ تم تحديث عنوان الدليل.")
        elif key == "سعر الاشتراك":
            db.child("config").child("price").set(float(value))
            bot.reply_to(message, f"✅ تم تحديث سعر الاشتراك إلى {value} ريال.")
        else:
            bot.reply_to(message,
                "❌ إعداد غير معروف. المتاح:\n"
                "• خدمة العملاء\n• رابط البرنامج\n• متطلبات البرنامج\n"
                "• دليل المستخدم رابط\n• دليل المستخدم ملف\n• دليل المستخدم عنوان\n"
                "• سعر الاشتراك")
    except Exception as e:
        bot.reply_to(message, f"⚠️ خطأ أثناء التعيين: {e}")

# ---------------------------------------------------------------------------
# الحصول على File ID للملفات

@bot.message_handler(func=lambda m: str(m.chat.id) == ADMIN_ID, content_types=['document'])
def get_admin_file_id(message):
    if message.document:
        fid = message.document.file_id
        bot.reply_to(message,
            f"✅ تم استلام الملف.\n"
            f"<b>File ID:</b> <code>{fid}</code>\n\n"
            f"استخدمه هكذا:\n"
            f"`تعيين دليل المستخدم ملف {fid}`")
    else:
        bot.reply_to(message, "❌ هذا ليس ملفًا.")

# ---------------------------------------------------------------------------
# السعر الحالى

def get_current_price():
    price = db.child("config").child("price").get().val()
    return float(price) if price else 350.0

# ---------------------------------------------------------------------------
# إنشاء فاتورة Moyasar

def create_checkout_link(chat_id: str) -> str:
    if not MOYASAR_SECRET_KEY:
        raise RuntimeError("MOYASAR_SECRET_KEY غير مضبوط")

    auth_header = base64.b64encode(f"{MOYASAR_SECRET_KEY}:".encode()).decode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {auth_header}"
    }

    payload = {
        "amount":    int(get_current_price() * 100),
        "currency":  "SAR",
        "description": "اشتراك SIGMATOR BOT",
        "callback_url": "https://yourdomain.com/moyasar_webhook",
        "success_url":  "https://yourdomain.com/success",
        "metadata":  {"telegram_chat_id": chat_id}
    }

    r = requests.post("https://api.moyasar.com/v1/invoices", headers=headers, json=payload)
    r.raise_for_status()
    return r.json()["url"]

# ---------------------------------------------------------------------------

bot.polling()
