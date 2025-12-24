import os
import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path=None): # تركنا db_path للتوافق فقط
        # 1. جلب رابط الاتصال من متغيرات البيئة في جيت هاب
        self.uri = os.getenv('MONGO_URI')
        
        if not self.uri:
            print("❌ خطأ: لم يتم العثور على متغير MONGO_URI في Secrets!")
            return

        try:
            # 2. إنشاء الاتصال مع إعدادات تجاوز أخطاء الشهادات (مهم جداً لجيت هاب)
            self.client = MongoClient(
                self.uri,
                tlsAllowInvalidCertificates=True, # تجاوز مشكلة SSL
                serverSelectionTimeoutMS=5000     # الانتظار لمدة 5 ثوانٍ فقط عند الفشل
            )
            
            # 3. أمر فحص الاتصال (Ping)
            self.client.admin.command('ping')
            
            # 4. تحديد قاعدة البيانات (سيتم إنشاؤها تلقائياً إذا لم توجد)
            self.db = self.client['DBchat']
            self.users = self.db['users']
            
            print("✅ تم الاتصال بنجاح بـ MongoDB Atlas!")
            
        except Exception as e:
            print(f"❌ فشل الاتصال بالقاعدة. السبب: {e}")
            # لإعطائك تفاصيل أكثر في سجلات جيت هاب
            raise e

    # دالة تسجيل مستخدم (كمثال للتأكد من العمل)
    def register_user(self, user_id, username, first_name):
        user_data = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "points": 50,
            "status": "idle",
            "last_activity": __import__('datetime').datetime.now()
        }
        return self.users.update_one(
            {"user_id": user_id},
            {"$set": user_data},
            upsert=True
        )

    def get_user(self, user_id):
        return self.users.find_one({"user_id": user_id})
