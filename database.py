import os
import time
import logging
from pymongo import MongoClient, UpdateOne, ASCENDING, DESCENDING
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

def now_ts():
    return int(time.time())

class Database:
    def __init__(self, connection_string=None):
        # جلب رابط الاتصال من متغيرات البيئة (GitHub Secrets)
        self.uri = connection_string or os.getenv('MONGO_URI')
        if not self.uri:
            raise ValueError("❌ MONGO_URI is missing! Please add it to GitHub Secrets.")
        
        # الاتصال بالسيرفر
        self.client = MongoClient(self.uri)
        # اسم قاعدة البيانات
        self.db = self.client['DBchat']
        
        # المجموعات (Collections)
        self.users = self.db['users']
        self.vip_purchases = self.db['vip_purchases']
        self.reports = self.db['reports']
        
        # إنشاء الفهارس لتسريع عمليات البحث
        self._ensure_indexes()
        logger.info("✅ Connected to MongoDB cloud successfully!")

    def _ensure_indexes(self):
        """إنشاء فهارس لتحسين أداء الاستعلامات"""
        self.users.create_index("user_id", unique=True)
        self.users.create_index("status")
        self.users.create_index([("points", DESCENDING)])

    # --- إدارة المستخدمين ---

    def register_user(self, user_id, username, first_name):
        """تسجيل مستخدم جديد أو تحديث بياناته الأساسية"""
        user_data = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "points": 10,  # هدية تسجيل
            "gender": None,
            "status": "idle",
            "partner_id": None,
            "vip_until": 0,
            "last_reward": 0,
            "joined_at": now_ts(),
            "is_banned": False,
            "gender_changed": 0,
            "total_chats": 0,
            "stars_balance": 0,
            "bio": ""
        }
        # استخدم update_one مع upsert لضمان عدم التكرار
        self.users.update_one(
            {"user_id": user_id},
            {"$setOnInsert": user_data},
            upsert=True
        )

    def get_user(self, user_id) -> Optional[Dict]:
        """جلب بيانات مستخدم معين"""
        return self.users.find_one({"user_id": user_id})

    def update_user(self, user_id, update_data: Dict):
        """تحديث بيانات المستخدم بمرونة"""
        self.users.update_one({"user_id": user_id}, {"$set": update_data})

    def add_points(self, user_id, points):
        """إضافة أو خصم نقاط (استخدم قيمة سالبة للخصم)"""
        self.users.update_one({"user_id": user_id}, {"$inc": {"points": points}})

    def set_user_status(self, user_id, status, partner_id=None):
        """تحديث حالة المستخدم (بحث، دردشة، خامل)"""
        self.users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "status": status, 
                    "partner_id": partner_id, 
                    "last_activity": now_ts()
                }
            }
        )

    # --- نظام الدردشة العشوائية ---

    def get_waiting_user(self, gender_filter=None, exclude_id=None):
        """البحث عن شريك متاح للدردشة"""
        query = {
            "status": "searching", 
            "user_id": {"$ne": exclude_id},
            "is_banned": False
        }
        if gender_filter:
            query["gender"] = gender_filter
        
        return self.users.find_one(query)

    # --- نظام VIP والدفع ---

    def add_vip_time(self, user_id, days):
        """إضافة وقت VIP للمستخدم"""
        current_user = self.get_user(user_id)
        now = now_ts()
        
        # إذا كان لديه VIP حالياً، نبدأ الإضافة من تاريخ الانتهاء، وإلا نبدأ من الآن
        start_from = max(current_user.get('vip_until', 0), now)
        new_expiry = start_from + (days * 86400)
        
        self.users.update_one(
            {"user_id": user_id},
            {"$set": {"vip_until": new_expiry}}
        )
        return new_expiry

    def log_purchase(self, user_id, amount, currency, days):
        """تسجيل عملية شراء VIP"""
        self.vip_purchases.insert_one({
            "user_id": user_id,
            "amount": amount,
            "currency": currency, # 'stars' or 'points'
            "days": days,
            "timestamp": now_ts()
        })

    # --- نظام البلاغات ---

    def add_report(self, reporter_id, reported_id, reason):
        """تسجيل بلاغ ضد مستخدم"""
        self.reports.insert_one({
            "reporter_id": reporter_id,
            "reported_id": reported_id,
            "reason": reason,
            "timestamp": now_ts(),
            "status": "pending"
        })

    # --- الإحصائيات (Stats) ---

    def get_stats(self) -> Dict:
        """جلب إحصائيات عامة للبوت"""
        return {
            "total_users": self.users.count_documents({}),
            "active_chats": self.users.count_documents({"status": "chatting"}),
            "searching": self.users.count_documents({"status": "searching"}),
            "banned": self.users.count_documents({"is_banned": True}),
            "total_vip": self.users.count_documents({"vip_until": {"$gt": now_ts()}})
        }

    def get_top_users(self, limit=10):
        """قائمة المتصدرين بالنقاط"""
        return list(self.users.find().sort("points", DESCENDING).limit(limit))

    # --- التنظيف (Maintenance) ---

    def optimize_database(self):
        """في MongoDB لا نحتاج لـ VACUUM مثل SQLite"""
        logger.info("MongoDB maintenance: Indexes are up to date.")
        return True
