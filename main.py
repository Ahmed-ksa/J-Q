from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import datetime
import pyrebase
import os
from dotenv import load_dotenv
import base64
import re

# افتراض وجود ملف keep_alive.py منفصل لتشغيل التطبيق باستمرار
from keep_alive import keep_alive

# تحميل متغيرات البيئة من ملف .env
load_dotenv()
keep_alive() # تشغيل وظيفة keep_alive للحفاظ على البوت نشطًا

# إعدادات Firebase من متغيرات البيئة
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

# متغيرات البوت من متغيرات البيئة
BOT_TOKEN = os.getenv("BOT_TOKEN")
MOYASAR_SECRET_KEY = os.getenv("MOYASAR_SECRET_KEY") # مفتاح Moyasar السري
ADMIN_ID = os.getenv("ADMIN_ID") # معرف المشرف

# تهيئة البوت
bot = TeleBot(BOT_TOKEN, parse_mode="HTML")

# دالة مساعدة لجلب الإعدادات من Firebase
def get_setting(key, default=None):
    """
    تجلب إعدادًا معينًا من مسار config/settings في Firebase.
    إذا لم يكن الإعداد موجودًا، تقوم بتعيين قيمة افتراضية له ثم إعادته.
    """
    setting = db.child("config").child("settings").child(key).get().val()
    if setting is None:
        # تعيين القيم الافتراضية إذا لم تكن موجودة في قاعدة البيانات
        if key == "customer_service_username":
            default = "hassan_jumaie"
        elif key == "program_download_link":
            default = "https://example.com/program.exe"
        elif key == "program_requirements_text":
            default = "يتطلب نظام ويندوز ويفضل إيقاف برنامج مكافحة الفيروسات كي يعمل البرنامج بشكل سليم."
        elif key == "user_guide_content":
            default = {"type": "link", "value": "https://example.com/user_guide.pdf", "caption": "دليل المستخدم الخاص بك"}

        if default is not None:
            db.child("config").child("settings").child(key).set(default)
            return default
    return setting if setting is not None else default

@bot.message_handler(commands=['start', 'help'])
def handle_start(message):
    """
    يعالج الأمرين /start و /help ويرسل رسالة ترحيب مع الأزرار المضمنة.
    """
    # إنشاء لوحة مفاتيح مضمنة
    markup = InlineKeyboardMarkup()
    markup.row_width = 2 # عدد الأزرار في كل صف

    # إضافة الأزرار للخيارات المتاحة
    markup.add(
        InlineKeyboardButton("🟢 اشتراك", callback_data="subscribe"),
        InlineKeyboardButton("🔄 تجديد", callback_data="renew"),
        InlineKeyboardButton("📊 حالة الاشتراك", callback_data="status"),
        InlineKeyboardButton("🔐 بيانات الدخول", callback_data="credentials"),
        InlineKeyboardButton("📞 خدمة العملاء", callback_data="customer_service"),
        InlineKeyboardButton("⬇️ تثبيت البرنامج", callback_data="install_program"),
        InlineKeyboardButton("📚 دليل المستخدم", callback_data="user_guide")
    )
    
    # إرسال الرسالة مع لوحة المفاتيح المضمنة
    bot.send_message(
        message.chat.id,
        "👋 مرحبًا! اختر أحد الخيارات أدناه:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    """
    يعالج جميع استدعاءات الأزرار المضمنة (callback queries).
    """
    chat_id = str(call.message.chat.id)
    bot.answer_callback_query(call.id) # لإخفاء "جاري التحميل" على الزر

    # توجيه الطلب بناءً على بيانات الزر (callback_data)
    if call.data == "subscribe":
        handle_subscribe_action(chat_id)
    elif call.data == "renew":
        handle_subscribe_action(chat_id) # التجديد يستخدم نفس منطق الاشتراك في الوقت الحالي
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

# دوال مساعدة لمهام الاشتراك والتحقق من الحالة وبيانات الاعتماد
# هذه الدوال يمكن استدعاؤها من أوامر الرسائل المباشرة أو من استدعاءات الأزرار المضمنة

def handle_subscribe_action(chat_id):
    """
    يقوم بإنشاء رابط دفع وإرساله للمستخدم.
    """
    try:
        url = create_checkout_link(chat_id)
        bot.send_message(chat_id, f"""🔗 <b>رابط الدفع الخاص بك:</b>
<a href="{url}">اضغط هنا لإتمام عملية الدفع</a>

📩 بعد الدفع سيتم إرسال اسم المستخدم وكلمة المرور الخاصة بك تلقائيًا.""")
    except Exception as e:
        bot.send_message(chat_id, f"❌ حدث خطأ أثناء إنشاء رابط الدفع. يرجى المحاولة لاحقًا. الخطأ: {e}")
        print(f"Error creating checkout link for {chat_id}: {e}")


def check_status_action(chat_id):
    """
    يتحقق من حالة اشتراك المستخدم ويعرض تاريخ الانتهاء والأيام المتبقية.
    """
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
        today = datetime.date.today()

        if today > expiry_date:
            bot.send_message(chat_id, f"📛 انتهى اشتراكك بتاريخ {expiry_str}.")
        else:
            days_left = (expiry_date - today).days
            bot.send_message(chat_id, f"✅ اشتراكك نشط. ينتهي بتاريخ {expiry_str}.\n🕓 متبقي: {days_left} يوم.")
    except ValueError:
        bot.send_message(chat_id, "❌ هناك مشكلة في تنسيق تاريخ انتهاء الصلاحية. يرجى التواصل مع الدعم.")


def get_credentials_action(chat_id):
    """
    يعرض اسم المستخدم وكلمة المرور وتاريخ انتهاء الاشتراك للمستخدم إذا كان نشطًا.
    """
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
        today = datetime.date.today()

        if today > expiry_date:
            bot.send_message(chat_id, f"📛 انتهى اشتراكك بتاريخ {expiry_str}. لا يمكن عرض البيانات.")
        else:
            password = user.get("password", "غير متوفر")
            bot.send_message(chat_id, f"""🔐 <b>بيانات حسابك:</b>

👤 <b>اسم المستخدم:</b> <code>{chat_id}</code>
🔒 <b>كلمة المرور:</b> <code>{password}</code>
📅 <b>تاريخ الانتهاء:</b> <code>{expiry_str}</code>

⚠️ يُمنع مشاركة الحساب مع الآخرين.""")
    except ValueError:
        bot.send_message(chat_id, "❌ هناك مشكلة في تنسيق تاريخ انتهاء الصلاحية. يرجى التواصل مع الدعم.")

# معالجات الأوامر الأصلية (تبقى لتمكين الاستخدام المباشر للأوامر النصية)
@bot.message_handler(commands=['subscribe', 'renew'])
def handle_subscribe_command(message):
    handle_subscribe_action(str(message.chat.id))

@bot.message_handler(commands=['status'])
def check_status_command(message):
    check_status_action(str(message.chat.id))

@bot.message_handler(commands=['credentials'])
def get_credentials_command(message):
    get_credentials_action(str(message.chat.id))

# دوال الميزات الجديدة

def send_customer_service_info(chat_id):
    """
    يرسل معلومات الاتصال بخدمة العملاء.
    """
    username = get_setting("customer_service_username")
    bot.send_message(chat_id, f"للتواصل المباشر مع خدمة العملاء: @{username}")

def send_program_info(chat_id):
    """
    يرسل رابط تحميل البرنامج مع متطلبات التشغيل.
    """
    link = get_setting("program_download_link")
    requirements = get_setting("program_requirements_text")
    bot.send_message(chat_id, f"""⬇️ <b>تثبيت البرنامج:</b>

🔗 <b>رابط التحميل:</b> <a href="{link}">اضغط هنا للتحميل</a>

📝 <b>المتطلبات:</b>
{requirements}""")

def send_user_guide(chat_id):
    """
    يرسل دليل المستخدم، إما كرابط أو كملف بناءً على الإعدادات.
    """
    user_guide_data = get_setting("user_guide_content")
    guide_type = user_guide_data.get("type", "link")
    guide_value = user_guide_data.get("value")
    guide_caption = user_guide_data.get("caption", "دليل المستخدم الخاص بك:")

    if guide_value:
        if guide_type == "link":
            # إرسال دليل المستخدم كرابط
            bot.send_message(chat_id, f"📚 <b>{guide_caption}</b>\n\n<a href='{guide_value}'>اضغط هنا لعرض الدليل</a>")
        elif guide_type == "file_id":
            # إرسال دليل المستخدم كملف باستخدام File ID
            try:
                bot.send_document(chat_id, guide_value, caption=guide_caption)
            except Exception as e:
                bot.send_message(chat_id, f"❌ حدث خطأ عند إرسال دليل المستخدم. يرجى التأكد من صحة معرف الملف.")
                print(f"Error sending document: {e}") # لطباعة الخطأ في الكونسول للمراجعة
        else:
            bot.send_message(chat_id, "⚠️ لا يمكن العثور على دليل المستخدم. يرجى إبلاغ الإدارة.")
    else:
        bot.send_message(chat_id, "⚠️ لا يتوفر دليل المستخدم حاليًا. يرجى إبلاغ الإدارة.")

# <<<<<<< تم حذف دالة change_price القديمة هنا، حيث تم دمج وظيفتها في set_config_value الجديدة >>>>>>>>

# معالج عام لأوامر التعيين الخاصة بالمشرف - الحل الأقوى
@bot.message_handler(func=lambda m: str(m.chat.id) == str(ADMIN_ID) and m.text.strip().startswith("تعيين"))
def set_config_value(message):
    try:
        # استخدام التعبير المنتظم لتحليل الرسالة
        m = re.match(r'^تعيين\s+(.+?)\s+(.+)$', message.text.strip())
        if not m:
            bot.reply_to(message, "⚠️ الصيغة: `تعيين [اسم الإعداد] [القيمة]`")
            return

        # إزالة المسافات من مفتاح الإعداد (مثل "خدمة العملاء" تصبح "خدمةالعملاء") للمطابقة في القاموس
        raw_key = m.group(1).strip().replace(" ", "")
        value   = m.group(2).strip()

        # قاموس يربط أسماء الإعدادات العربية (بدون مسافات) بمساراتها وقيمها في Firebase
        settings_map = {
            "خدمةالعملاء": ("customer_service_username", value),
            "رابطالبرنامج": ("program_download_link", value),
            "متطلباتالبرنامج": ("program_requirements_text", value),
            "دليلالمستخدمرابط": ("user_guide_content", {"type": "link", "value": value}),
            "دليلالمستخدمملف": ("user_guide_content", {"type": "file_id", "value": value}),
            "دليلالمستخدمعنوان": ("user_guide_content", {"caption": value}),
            "سعرالاشتراك": ("price", float(value)) # معالجة السعر كـ float
        }

        if raw_key not in settings_map:
            bot.reply_to(message,
                "❌ إعداد غير معروف. الإعدادات المتاحة للتعيين هي:\n"
                "• `خدمة العملاء`\n• `رابط البرنامج`\n• `متطلبات البرنامج`\n"
                "• `دليل المستخدم رابط`\n• `دليل المستخدم ملف`\n• `دليل المستخدم عنوان`\n"
                "• `سعر الاشتراك`")
            return

        # جلب مسار Firebase والقيمة المراد تعيينها من القاموس
        path, setting_value = settings_map[raw_key]

        # تحديث Firebase بناءً على المسار
        if path == "user_guide_content":
            # تحديث جزء معين من كائن دليل المستخدم
            db.child("config").child("settings").child(path).update(setting_value)
        elif path == "price":
            # تعيين السعر مباشرة تحت config
            db.child("config").child(path).set(setting_value)
        else:
            # تعيين باقي الإعدادات تحت config/settings
            db.child("config").child("settings").child(path).set(setting_value)

        bot.reply_to(message, f"✅ تم تعيين {m.group(1)} بنجاح.")
    except ValueError: # لمعالجة خطأ التحويل إلى float إذا كانت قيمة السعر غير صحيحة
        bot.reply_to(message, "⚠️ قيمة السعر يجب أن تكون رقماً صحيحاً أو عشرياً.")
    except Exception as e:
        bot.reply_to(message, f"⚠️ حدث خطأ أثناء تعيين الإعداد: {e}\n"
                              "تأكد من استخدام الصيغة الصحيحة: `تعيين [اسم الإعداد] [القيمة]`")

@bot.message_handler(func=lambda message: str(message.chat.id) == str(ADMIN_ID), content_types=['document'])
def get_admin_file_id(message):
    """
    يسمح للمشرف بإرسال أي ملف للحصول على معرف الملف (File ID) الخاص به.
    هذا مفيد لتعيين دليل المستخدم كملف.
    """
    if message.document:
        file_id = message.document.file_id
        bot.reply_to(message, f"✅ تم استلام الملف بنجاح.\n"
                              f"<b>معرف الملف (File ID):</b> <code>{file_id}</code>\n\n"
                              f"يمكنك استخدام هذا المعرف لتعيين دليل المستخدم بالصيغة التالية:\n"
                              f"`تعيين دليل المستخدم ملف {file_id}`")
    else:
        bot.reply_to(message, "❌ هذا ليس ملفًا.")

def get_current_price():
    """
    يجلب السعر الحالي من Firebase.
    """
    price = db.child("config").child("price").get().val()
    return float(price) if price else 350.0

def create_checkout_link(chat_id: str) -> str:
    """
    ينشئ رابط صفحة دفع جاهزة باستخدام Moyasar Invoices API.
    """
    # التأكد أنّ المتغيِّر مضبوط فى البيئة
    if not MOYASAR_SECRET_KEY:
        raise RuntimeError("MOYASAR_SECRET_KEY غير مضبوط فى البيئة")

    # Basic-Auth (اسم المستخدم = المفتاح، كلمة المرور فارغة)
    auth_header = base64.b64encode(f"{MOYASAR_SECRET_KEY}:".encode()).decode()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {auth_header}"
    }

    amount = int(get_current_price() * 100)          # بالهللة
    payload = {
        "amount": amount,
        "currency": "SAR",
        "description": "اشتراك SIGMATOR BOT", # تم تغيير الوصف ليتناسب مع اقتراحك
        "callback_url": "https://yourdomain.com/moyasar_webhook", # رابط الويب هوك الخاص بك
        "success_url": "https://yourdomain.com/success", # رابط النجاح بعد الدفع
        "metadata": {"telegram_chat_id": chat_id} # معرف المستخدم لدينا
    }

    print(f"Moyasar Invoice Payload: {payload}") # طباعة الحمولة للتحقق

    r = requests.post("https://api.moyasar.com/v1/invoices", headers=headers, json=payload)
    r.raise_for_status() # إظهار خطأ إذا كانت الحالة غير 2xx

    response_data = r.json()
    print(f"Moyasar Invoice Response: {response_data}") # طباعة الاستجابة للتحقق

    return response_data["url"] # فلد «url» يحوى رابط صفحة الدفع

# بدء تشغيل البوت
bot.polling()
