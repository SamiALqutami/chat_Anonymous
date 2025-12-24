import os
import ssl
import certifi
from pymongo import MongoClient

class Database:
    def __init__(self, db_path=None):
        # جلب الرابط من جيت هاب
        self.uri = os.getenv('MONGO_URI')
        
        if not self.uri:
            print("❌ MONGO_URI missing")
            return

        try:
            # استخدام مكتبة certifi لتوفير شهادات موثوقة
            # هذا يحل مشكلة الـ SSL في بيئة GitHub Actions
            self.client = MongoClient(
                self.uri,
                tls=True,
                tlsCAFile=certifi.where(),
                tlsAllowInvalidCertificates=True, # لتجاوز أي تعارض في البروتوكولات
                serverSelectionTimeoutMS=5000
            )
            
            # اختبار الاتصال
            self.client.admin.command('ping')
            
            # تحديد قاعدة البيانات والمجموعات
            self.db = self.client.get_database("DBchat")
            self.users = self.db.get_collection("users")
            
            print("✅ تم الاتصال بنجاح تام بالقاعدة السحابية!")
            
        except Exception as e:
            print(f"❌ خطأ في الاتصال: {e}")
            raise e

    def get_user(self, user_id):
        return self.users.find_one({"user_id": user_id})

    def set_user_status(self, user_id, status):
        self.users.update_one({"user_id": user_id}, {"$set": {"status": status}}, upsert=True)
