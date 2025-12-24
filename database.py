import os
import ssl
import certifi
from pymongo import MongoClient

class Database:
    def __init__(self, db_path=None):
        self.uri = os.getenv('MONGO_URI')
        
        if not self.uri:
            print("❌ MONGO_URI missing")
            return

        try:
            # إعداد سياق SSL مخصص لتجاوز تعارض الإصدارات
            context = ssl.create_default_context(cafile=certifi.where())
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE # هذا السطر سيحل مشكلة الـ Alert Internal Error

            self.client = MongoClient(
                self.uri,
                tls=True,
                tlsContext=context,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=10000
            )
            
            # فحص الاتصال
            self.client.admin.command('ping')
            self.db = self.client['DBchat']
            self.users = self.db['users']
            print("✅ تم اختراق حاجز SSL والاتصال بنجاح!")
            
        except Exception as e:
            print(f"❌ فشل الاتصال النهائي: {e}")
            raise e
