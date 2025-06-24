from flask import Flask, request, jsonify
from threading import Thread
import datetime
import pyrebase
import os
from dotenv import load_dotenv

load_dotenv()

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

app = Flask('')

@app.route('/')
def home():
    return "✅ Bot is alive!"

# تم تغيير المسار إلى /moyasar_webhook ليتناسب مع Moyasar
@app.route('/moyasar_webhook', methods=['POST'])
def moyasar_webhook():
    data = request.json
    print(f"Received Moyasar Webhook: {data}") # لطباعة بيانات الويب هوك للمراجعة

    # Moyasar ترسل حالة الدفع في حقل 'status'
    status = data.get("status")
    # معرف المستخدم لدينا يتم إرساله في 'metadata'
    internal_id = data.get("metadata", {}).get("telegram_chat_id")

    if status == "paid" and internal_id: # Moyasar ترسل 'paid' عندما يكون الدفع ناجحًا
        # تحديث بيانات المستخدم في Firebase
        db.child("users").child(internal_id).update({
            "active": True,
            "paid_at": str(datetime.datetime.now().date()),
            "expiry": str(datetime.date.today() + datetime.timedelta(days=30)) # مثال: تفعيل لمدة 30 يومًا
            # يمكنك إضافة كلمة مرور هنا أو في مكان آخر إذا لم تكن موجودة
            # "password": "new_generated_password"
        })
        print(f"User {internal_id} status updated to PAID.")
    elif status == "failed":
        print(f"Payment for {internal_id} failed.")
        # يمكنك هنا إضافة منطق للتعامل مع الدفعات الفاشلة، مثل إرسال إشعار للمستخدم

    response = jsonify({"message": "OK"})
    response.status_code = 200
    response.headers["Content-Type"] = "application/json"
    return response

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
