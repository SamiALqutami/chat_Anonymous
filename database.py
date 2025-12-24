import os
import certifi
from pymongo import MongoClient

class Database:
    def __init__(self, db_path=None):
        self.uri = os.getenv('MONGO_URI')
        
        # استخدام certifi لتأمين شهادات SSL
        ca = certifi.where()
        
        self.client = MongoClient(
            self.uri,
            tlsCAFile=ca,            # استخدام شهادات certifi
            tlsAllowInvalidCertificates=True, # السماح لتجاوز أخطاء SSL الداخلية
            serverSelectionTimeoutMS=5000
        )
        
        try:
            self.client.admin.command('ping')
            self.db = self.client['DBchat']
            self.users = self.db['users']
            print("✅ تم حل مشكلة SSL والاتصال بنجاح!")
        except Exception as e:
            print(f"❌ لا تزال هناك مشكلة في الاتصال: {e}")
            raise e
