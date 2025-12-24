import os
import sys
import time
import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# إعداد السجلات لمراقبة الاتصال
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        # 1. جلب رابط MONGO_URI من Secrets جيت هاب
        self.uri = os.getenv('MONGO_URI')
        
        # 2. التوقف الإجباري إذا لم يتم العثور على الرابط
        if not self.uri:
            print("❌ خطأ قاتل: لم يتم العثور على MONGO_URI في إعدادات Secrets!")
            sys.exit(1) 

        try:
            # 3. الاتصال بـ MongoDB مع إعدادات الأمان المتقدمة لـ GitHub Actions
            # أضفنا tlsAllowInvalidCertificates لتجاوز خطأ SSL handshake
            self.client = MongoClient(
                self.uri,
                serverSelectionTimeoutMS=5000,
                tlsAllowInvalidCertificates=True,
                retryWrites=True,
                w='majority'
            )
            
            # 4. اختبار الاتصال الفعلي (Ping)
            self.client.admin.command('ping')
            
            # 5. تحديد قاعدة البيانات والمجموعات (Collections)
            self.db = self.client['DBchat'] # سيظهر بهذا الاسم في MongoDB Atlas
            self.users = self.db['users']
            
            # 6. إنشاء فهرس فريد لضمان عدم تكرار المستخدمين وسرعة البحث
            self.users.create_index("user_id", unique=True)
            
            print("✅ تم الاتصال بـ MongoDB بنجاح. جميع البيانات مرتبطة بالسحاب الآن.")
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            print(f"❌ فشل الاتصال بالقاعدة الخارجية: {e}")
            print("⚠️ يتم إيقاف البوت الآن لمنع ضياع بيانات المستخدمين.")
            sys.exit(1) # توقف البوت إذا لم ينجح الاتصال (طلبك الأساسي)

    def get_user(self, user_id):
        """جلب بيانات المستخدم من السحاب"""
        return self.users.find_one({"user_id": user_id})

    def register_user(self, user_id, username, first_name):
        """تسجيل مستخدم جديد أو تحديث بياناته دون تصفير النقاط"""
        existing_user = self.get_user(user_id)
        if not existing_user:
            user_data = {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "points": 10, # نقاط ترحيبية
                "joined_at": int(time.time()),
                "is_banned": False
            }
            self.users.insert_one(user_data)
        else:
            # تحديث الاسم واليوزرنيم فقط إذا تغيروا
            self.users.update_one(
                {"user_id": user_id},
                {"$set": {"username": username, "first_name": first_name}}
            )

    def update_points(self, user_id, amount):
        """إضافة أو سحب نقاط من المستخدم في السحاب مباشرة"""
        self.users.update_one(
            {"user_id": user_id},
            {"$inc": {"points": amount}}
        )
