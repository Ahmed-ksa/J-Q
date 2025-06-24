from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import datetime
import pyrebase
import os
from dotenv import load_dotenv
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
# تم تغيير TAP_SECRET_KEY إلى MOYASAR_SECRET_KEY
MOYASAR_SECRET_KEY = os.getenv("MOYASAR_SECRET_KEY")
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

@bot.message_handler(func=lambda message: message.text.strip().startswith("تغيير السعر") and str(message.chat.id) == ADMIN_ID)
def change_price(message):
    """
    يسمح للمشرف بتغيير سعر الاشتراك.
    """
    try:
        parts = message.text.strip().split()
        if len(parts) < 3:
            raise ValueError("Missing price")
        new_price = float(parts[2])
        db.child("config").child("price").set(new_price)
        bot.reply_to(message, f"✅ تم تحديث السعر إلى {new_price} ريال.")
    except Exception as e:
        bot.reply_to(message, f"⚠️ الصيغة الصحيحة: تغيير السعر 500. حدث خطأ: {e}")

# معالج عام لأوامر التعيين الخاصة بالمشرف
@bot.message_handler(func=lambda message: str(message.chat.id) == ADMIN_ID and message.text.strip().startswith("تعيين"))
def set_config_value(message):
    """
    يسمح للمشرف بتعيين قيم إعدادات البوت المختلفة.
    الصيغة: تعيين [اسم_الإعداد] [القيمة]
    """
    try:
        parts = message.text.strip().split(' ', 2) # تقسيم الرسالة إلى 3 أجزاء كحد أقصى
        if len(parts) < 3:
            bot.reply_to(message, "⚠️ الصيغة الصحيحة: `تعيين [اسم_الإعداد] [القيمة]`")
            return

        setting_key_raw = parts[1] # الجزء الثاني هو اسم الإعداد (مثل "خدمة العملاء")
        value = parts[2] # الجزء الثالث هو القيمة

        if setting_key_raw == "خدمة العملاء":
            db.child("config").child("settings").child("customer_service_username").set(value)
            bot.reply_to(message, f"✅ تم تعيين اسم مستخدم خدمة العملاء إلى: @{value}")
        elif setting_key_raw == "رابط البرنامج":
            db.child("config").child("settings").child("program_download_link").set(value)
            bot.reply_to(message, f"✅ تم تعيين رابط تحميل البرنامج إلى: {value}")
        elif setting_key_raw == "متطلبات البرنامج":
            db.child("config").child("settings").child("program_requirements_text").set(value)
            bot.reply_to(message, f"✅ تم تعيين متطلبات البرنامج بنجاح.")
        elif setting_key_raw == "دليل المستخدم رابط":
            # تحديث نوع وقيمة دليل المستخدم إلى رابط
            db.child("config").child("settings").child("user_guide_content").update({"type": "link", "value": value})
            bot.reply_to(message, f"✅ تم تعيين رابط دليل المستخدم إلى: {value}")
        elif setting_key_raw == "دليل المستخدم ملف":
            # تحديث نوع وقيمة دليل المستخدم إلى معرف ملف
            db.child("config").child("settings").child("user_guide_content").update({"type": "file_id", "value": value})
            bot.reply_to(message, f"✅ تم تعيين معرف ملف دليل المستخدم إلى: {value}")
        elif setting_key_raw == "دليل المستخدم عنوان":
            # تحديث عنوان (caption) دليل المستخدم
            db.child("config").child("settings").child("user_guide_content").update({"caption": value})
            bot.reply_to(message, f"✅ تم تعيين عنوان دليل المستخدم إلى: {value}")
        else:
            bot.reply_to(message, "❌ إعداد غير معروف. الإعدادات المتاحة للتعيين هي:\n"
                                  "`خدمة العملاء`\n"
                                  "`رابط البرنامج`\n"
                                  "`متطلبات البرنامج`\n"
                                  "`دليل المستخدم رابط`\n"
                                  "`دليل المستخدم ملف`\n"
                                  "`دليل المستخدم عنوان`")
    except Exception as e:
        bot.reply_to(message, f"⚠️ حدث خطأ أثناء تعيين الإعداد: {e}\n"
                              "تأكد من استخدام الصيغة الصحيحة: `تعيين [اسم_الإعداد] [القيمة]`")

@bot.message_handler(func=lambda message: str(message.chat.id) == ADMIN_ID, content_types=['document'])
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

def create_checkout_link(internal_id):
    """
    ينشئ رابط دفع جديد باستخدام Moyasar API.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {MOYASAR_SECRET_KEY}:" # Moyasar uses Basic Auth with secret key
    }
    # المبلغ بالهللة (cent) لذلك نضرب السعر في 100
    amount_in_halalas = int(get_current_price() * 100)

    payload = {
        "amount": amount_in_halalas,
        "currency": "SAR",
        "description": "اشتراك خدمة التليجرام بوت",
        "callback_url": "https://yourdomain.com/moyasar_webhook", # هذا هو رابط الويب هوك الجديد
        "metadata": {
            "telegram_chat_id": internal_id # استخدام internal_id لتتبع المستخدم
        },
        "source": {
            "type": "invoice", # يمكن أن يكون "creditcard", "stcpay", "applepay", "mada", "sadad" إلخ
                              # اختر "invoice" إذا كنت تريد Moyasar لتوليد صفحة دفع
            "invoice": {
                "redirect_url": "https://yourdomain.com/success" # رابط النجاح بعد الدفع
            }
        }
    }
    # طباعة الحمولة للتحقق
    print(f"Moyasar Payload: {payload}")
    
    response = requests.post("https://api.moyasar.com/v1/payments", headers=headers, json=payload)
    response.raise_for_status() # إظهار خطأ إذا كانت الحالة غير 2xx

    response_data = response.json()
    # طباعة استجابة Moyasar للتحقق
    print(f"Moyasar Response: {response_data}")

    # Moyasar ترجع رابط التحويل في source.transaction_url
    if response_data.get("status") == "initiated" and response_data.get("source", {}).get("transaction_url"):
        return response_data["source"]["transaction_url"]
    else:
        raise Exception(f"Failed to create Moyasar payment: {response_data.get('message', 'Unknown error')}")

# بدء تشغيل البوت
bot.polling()
