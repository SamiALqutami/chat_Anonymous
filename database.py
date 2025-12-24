import os
from pymongo import MongoClient

class Database:
    def __init__(self, db_path=None):
        # جلب الرابط من جيت هاب
        self.uri = os.getenv('MONGO_URI')
        
        if not self.uri:
            raise ValueError("❌ خطأ: متغير MONGO_URI غير موجود في Secrets!")

        # الاتصال وتجاوز مشاكل الحماية
        self.client = MongoClient(
            self.uri, 
            tlsAllowInvalidCertificates=True,
            serverSelectionTimeoutMS=5000
        )
        
        try:
            # فحص الاتصال
            self.client.admin.command('ping')
            self.db = self.client['DBchat']
            self.users = self.db['users']
            print("✅ تم الاتصال بـ MongoDB بنجاح!")
        except Exception as e:
            print(f"❌ فشل المصادقة: تأكد من كلمة المرور في جيت هاب. الخطأ: {e}")
            raise e

    def get_user(self, user_id):
        return self.users.find_one({"user_id": user_id})

    def set_user_status(self, user_id, status):
        self.users.update_one({"user_id": user_id}, {"$set": {"status": status}}, upsert=True)
