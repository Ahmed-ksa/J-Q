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

@app.route('/paylink_webhook', methods=['POST'])
def paylink_webhook():
    data = request.json
    status = data.get("status")
    internal_id = data.get("orderNumber")

    if status == "PAID" and internal_id:
        db.child("users").child(internal_id).update({
            "active": True,
            "paid_at": str(datetime.datetime.now().date())
        })

    response = jsonify({"message": "OK"})
    response.status_code = 200
    response.headers["Content-Type"] = "application/json"
    return response

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
