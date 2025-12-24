import os
import sys
from pymongo import MongoClient

class Database:
    def __init__(self):
        # سحب الرابط من Secrets جيت هاب
        self.uri = os.getenv('MONGO_URI')
        if not self.uri:
            print("❌ خطأ قاتل: MONGO_URI غير موجود!")
            sys.exit(1) 

        try:
            # مهلة فحص 5 ثوانٍ فقط لمنع التعليق
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            self.client.admin.command('ping') 
            self.db = self.client['DBchat']
            self.users = self.db['users']
            # فهرس فريد لمنع تكرار المستخدمين
            self.users.create_index("user_id", unique=True)
            print("✅ تم الاتصال بـ MongoDB بنجاح. جميع ملفات البوت مرتبطة الآن بالسحاب.")
        except Exception as e:
            print(f"❌ فشل الاتصال بالقاعدة الخارجية: {e}")
            sys.exit(1) # إغلاق البوت فوراً لمنع مسح البيانات محلياً
