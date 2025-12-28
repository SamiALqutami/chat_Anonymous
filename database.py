import os
import json
import time
import base64
import requests
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import threading
from collections import defaultdict

logger = logging.getLogger(__name__)

def now_ts():
    return int(time.time())

class GitHubDatabase:
    """نظام قاعدة بيانات يستخدم GitHub كمستودع للبيانات"""
    
    def __init__(self, token: str, repo: str, db_file: str = "bot_data.json"):
        self.token = token
        self.repo = repo
        self.db_file = db_file
        self.base_url = f"https://api.github.com/repos/{repo}/contents"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.cache = None
        self.cache_sha = None
        self.last_sync = 0
        self.cache_duration = 300  # 5 دقائق بين كل مزامنة
        self.lock = threading.Lock()
        
        # تهيئة الهيكل الأساسي للبيانات
        self.default_structure = {
            "users": {},
            "reports": [],
            "referrals": [],
            "conversations": [],
            "messages": [],
            "friends": [],
            "games": [],
            "gifts": [],
            "vip_purchases": [],
            "game_requests": [],
            "stars_transactions": [],
            "vip_stars_purchases": [],
            "logs": [],
            "system": {
                "last_backup": 0,
                "total_users": 0,
                "total_messages": 0,
                "total_games": 0
            }
        }
        
        # محاولة تحميل البيانات الحالية
        self._load_data()
    
    def _load_data(self) -> Dict:
        """تحميل البيانات من مستودع GitHub"""
        with self.lock:
            current_time = now_ts()
            
            # استخدام الكاش إذا كان حديثاً
            if self.cache and (current_time - self.last_sync) < self.cache_duration:
                return self.cache
            
            try:
                # الحصول على معلومات الملف
                file_url = f"{self.base_url}/{self.db_file}"
                response = requests.get(file_url, headers=self.headers, timeout=30)
                
                if response.status_code == 200:
                    content = response.json()
                    data_json = base64.b64decode(content['content']).decode('utf-8')
                    self.cache = json.loads(data_json)
                    self.cache_sha = content['sha']
                else:
                    # إذا لم يوجد الملف، إنشاء هيكل جديد
                    self.cache = self.default_structure.copy()
                    self.cache_sha = None
                    
                    # محاولة حفظ الهيكل الجديد
                    self._save_data("Initializing database structure")
                
            except Exception as e:
                logger.error(f"Error loading data from GitHub: {e}")
                # استخدام بيانات افتراضية في حالة الخطأ
                if not self.cache:
                    self.cache = self.default_structure.copy()
                    self.cache_sha = None
            
            self.last_sync = current_time
            return self.cache
    
    def _save_data(self, commit_message: str = "Auto-save") -> bool:
        """حفظ البيانات إلى مستودع GitHub"""
        with self.lock:
            try:
                # تحويل البيانات إلى JSON
                data_json = json.dumps(self.cache, indent=2, ensure_ascii=False)
                data_bytes = data_json.encode('utf-8')
                encoded_content = base64.b64encode(data_bytes).decode('utf-8')
                
                # إعداد بيانات الرفع
                file_url = f"{self.base_url}/{self.db_file}"
                payload = {
                    "message": f"🤖 {commit_message}",
                    "content": encoded_content
                }
                
                # إضافة SHA إذا كان موجوداً لتحديث الملف
                if self.cache_sha:
                    payload["sha"] = self.cache_sha
                
                # رفع/تحديث الملف
                response = requests.put(file_url, headers=self.headers, json=payload, timeout=30)
                
                if response.status_code in [200, 201]:
                    result = response.json()
                    self.cache_sha = result.get('sha')
                    logger.info(f"Successfully saved data to GitHub: {commit_message}")
                    
                    # إنشاء سجل
                    self._add_log(f"SAVE: {commit_message}")
                    return True
                else:
                    logger.error(f"Failed to save data: {response.status_code} - {response.text}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error saving data to GitHub: {e}")
                return False
    
    def _add_log(self, action: str):
        """إضافة سجل للنظام"""
        log_entry = {
            "timestamp": now_ts(),
            "action": action
        }
        self.cache.get("logs", []).insert(0, log_entry)
        # حفظ آخر 1000 سجل فقط
        if len(self.cache.get("logs", [])) > 1000:
            self.cache["logs"] = self.cache["logs"][:1000]
    
    # --- المستخدمين ---
    def create_user(self, info: Dict[str, Any]) -> Dict:
        """إنشاء مستخدم جديد"""
        data = self._load_data()
        user_id = info.get("user_id")
        
        if str(user_id) not in data["users"]:
            import random
            import string
            
            # إنشاء كود إحالة فريد
            referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            
            user_data = {
                "user_id": user_id,
                "username": info.get("username", ""),
                "first_name": info.get("first_name", ""),
                "last_name": info.get("last_name", ""),
                "join_ts": info.get("join_ts", now_ts()),
                "country": "غير محدد",
                "gender": "غير محدد",
                "age": None,
                "bio": "",
                "language": "عربي",
                "points": 50,  # نقاط بداية
                "vip_until": 0,
                "vip_days": 0,
                "vip_purchases": 0,
                "chats_count": 0,
                "status": "idle",
                "last_hourly_ts": 0,
                "banned_until": 0,
                "referrals": 0,
                "invited_by": None,
                "level": 1,
                "total_chats": 0,
                "gender_changed": 0,
                "total_ratings": 0,
                "rating_sum": 0,
                "stars_balance": 0,
                "stars_purchases": 0,
                "premium_until": 0,
                "vip_level": 0,
                "vip_title": "",
                "last_reward_ts": 0,
                "referral_code": referral_code,
                "total_stars_earned": 0,
                "total_stars_spent": 0,
                "active_conversation": None,
                "searching_since": 0
            }
            
            data["users"][str(user_id)] = user_data
            self.cache = data
            self._save_data(f"Create user: {user_id}")
            
            # تحديث إحصائيات النظام
            data["system"]["total_users"] = len(data["users"])
            
            return user_data
        
        return data["users"][str(user_id)]
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """الحصول على بيانات مستخدم"""
        data = self._load_data()
        return data["users"].get(str(user_id))
    
    def update_user_profile(self, user_id: int, updates: Dict[str, Any]):
        """تحديث بيانات المستخدم"""
        data = self._load_data()
        user_key = str(user_id)
        
        if user_key in data["users"]:
            for key, value in updates.items():
                data["users"][user_key][key] = value
            
            self.cache = data
            self._save_data(f"Update user profile: {user_id}")
    
    def set_user_status(self, user_id: int, status: str):
        """تحديث حالة المستخدم"""
        data = self._load_data()
        user_key = str(user_id)
        
        if user_key in data["users"]:
            data["users"][user_key]["status"] = status
            if status == "searching":
                data["users"][user_key]["searching_since"] = now_ts()
            elif status == "idle":
                data["users"][user_key]["searching_since"] = 0
            
            self.cache = data
            self._save_data(f"User {user_id} status changed to {status}")
    
    def list_all_users(self, limit: int = 1000) -> List[Dict]:
        """قائمة بجميع المستخدمين"""
        data = self._load_data()
        users = list(data["users"].values())
        return sorted(users, key=lambda x: x.get('join_ts', 0), reverse=True)[:limit]
    
    # --- النقاط ---
    def add_points(self, user_id: int, points: int):
        """إضافة نقاط للمستخدم"""
        data = self._load_data()
        user_key = str(user_id)
        
        if user_key in data["users"]:
            data["users"][user_key]["points"] = data["users"][user_key].get("points", 0) + points
            
            # تحديث المستوى
            current_points = data["users"][user_key]["points"]
            new_level = (current_points // 100) + 1
            data["users"][user_key]["level"] = new_level
            
            self.cache = data
            self._save_data(f"Add {points} points to user {user_id}")
    
    def consume_points(self, user_id: int, points: int) -> bool:
        """خصم نقاط من المستخدم"""
        data = self._load_data()
        user_key = str(user_id)
        
        if user_key in data["users"]:
            current_points = data["users"][user_key].get("points", 0)
            if current_points >= points:
                data["users"][user_key]["points"] = current_points - points
                self.cache = data
                self._save_data(f"Consume {points} points from user {user_id}")
                return True
        return False
    
    # --- النجوم ---
    def add_stars(self, user_id: int, stars: int):
        """إضافة نجوم للمستخدم"""
        data = self._load_data()
        user_key = str(user_id)
        
        if user_key in data["users"]:
            data["users"][user_key]["stars_balance"] = data["users"][user_key].get("stars_balance", 0) + stars
            data["users"][user_key]["total_stars_earned"] = data["users"][user_key].get("total_stars_earned", 0) + stars
            self.cache = data
            self._save_data(f"Add {stars} stars to user {user_id}")
    
    def consume_stars(self, user_id: int, stars: int) -> bool:
        """خصم نجوم من المستخدم"""
        data = self._load_data()
        user_key = str(user_id)
        
        if user_key in data["users"]:
            current_stars = data["users"][user_key].get("stars_balance", 0)
            if current_stars >= stars:
                data["users"][user_key]["stars_balance"] = current_stars - stars
                data["users"][user_key]["total_stars_spent"] = data["users"][user_key].get("total_stars_spent", 0) + stars
                self.cache = data
                self._save_data(f"Consume {stars} stars from user {user_id}")
                return True
        return False
    
    def get_stars_balance(self, user_id: int) -> int:
        """الحصول على رصيد النجوم"""
        user = self.get_user(user_id)
        return user.get("stars_balance", 0) if user else 0
    
    def add_stars_transaction(self, user_id: int, transaction_type: str, stars_amount: int, description: str):
        """إضافة معاملة نجوم"""
        data = self._load_data()
        
        transaction = {
            "id": len(data["stars_transactions"]) + 1,
            "user_id": user_id,
            "transaction_type": transaction_type,
            "stars_amount": stars_amount,
            "description": description,
            "status": "completed",
            "created_at": now_ts()
        }
        
        data["stars_transactions"].append(transaction)
        self.cache = data
        self._save_data(f"Add stars transaction for user {user_id}")
    
    # --- التقارير ---
    def add_report(self, reporter_id: int, target_id: int, reason: str):
        """إضافة تقرير"""
        data = self._load_data()
        
        report = {
            "id": len(data["reports"]) + 1,
            "reporter_id": reporter_id,
            "target_id": target_id,
            "reason": reason,
            "ts": now_ts(),
            "handled": 0
        }
        
        data["reports"].append(report)
        self.cache = data
        self._save_data(f"Add report from {reporter_id} against {target_id}")
    
    def get_reports(self, limit: int = 100) -> List[Dict]:
        """الحصول على التقارير"""
        data = self._load_data()
        reports = data["reports"]
        return sorted(reports, key=lambda x: x.get('ts', 0), reverse=True)[:limit]
    
    # --- الإحالات ---
    def add_referral(self, referrer_id: int, new_user_id: int):
        """إضافة إحالة"""
        data = self._load_data()
        
        referral = {
            "id": len(data["referrals"]) + 1,
            "referrer_id": referrer_id,
            "new_user_id": new_user_id,
            "ts": now_ts()
        }
        
        data["referrals"].append(referral)
        
        # تحديث إحصائيات المستخدم
        referrer_key = str(referrer_id)
        if referrer_key in data["users"]:
            data["users"][referrer_key]["referrals"] = data["users"][referrer_key].get("referrals", 0) + 1
        
        new_user_key = str(new_user_id)
        if new_user_key in data["users"]:
            data["users"][new_user_key]["invited_by"] = referrer_id
        
        self.cache = data
        self._save_data(f"Add referral: {referrer_id} -> {new_user_id}")
    
    # --- المحادثات والرسائل ---
    def create_conversation(self, user_a: int, user_b: int) -> int:
        """إنشاء محادثة جديدة"""
        data = self._load_data()
        
        conversation = {
            "id": len(data["conversations"]) + 1,
            "user_a": user_a,
            "user_b": user_b,
            "start_ts": now_ts(),
            "last_ts": now_ts(),
            "active": 1,
            "rating_a": 0,
            "rating_b": 0,
            "messages_count": 0
        }
        
        data["conversations"].append(conversation)
        
        # تحديث إحصائيات المستخدمين
        for user_id in [user_a, user_b]:
            user_key = str(user_id)
            if user_key in data["users"]:
                data["users"][user_key]["chats_count"] = data["users"][user_key].get("chats_count", 0) + 1
                data["users"][user_key]["total_chats"] = data["users"][user_key].get("total_chats", 0) + 1
                data["users"][user_key]["active_conversation"] = conversation["id"]
        
        self.cache = data
        self._save_data(f"Create conversation between {user_a} and {user_b}")
        
        return conversation["id"]
    
    def close_conversation(self, conv_id: int):
        """إغلاق محادثة"""
        data = self._load_data()
        
        for conv in data["conversations"]:
            if conv["id"] == conv_id and conv["active"] == 1:
                conv["active"] = 0
                conv["last_ts"] = now_ts()
                
                # إزالة المحادثة النشطة من المستخدمين
                for user_id in [conv["user_a"], conv["user_b"]]:
                    user_key = str(user_id)
                    if user_key in data["users"]:
                        data["users"][user_key]["active_conversation"] = None
                        data["users"][user_key]["status"] = "idle"
                
                self.cache = data
                self._save_data(f"Close conversation {conv_id}")
                break
    
    def add_message(self, conv_id: int, sender_id: int, text: str, message_type: str = "text"):
        """إضافة رسالة"""
        data = self._load_data()
        
        message = {
            "id": len(data["messages"]) + 1,
            "conv_id": conv_id,
            "sender_id": sender_id,
            "text": text,
            "ts": now_ts(),
            "message_type": message_type
        }
        
        data["messages"].append(message)
        
        # تحديث عدد الرسائل في المحادثة
        for conv in data["conversations"]:
            if conv["id"] == conv_id:
                conv["messages_count"] = conv.get("messages_count", 0) + 1
                conv["last_ts"] = now_ts()
                break
        
        # تحديث إحصائيات النظام
        data["system"]["total_messages"] = len(data["messages"])
        
        self.cache = data
        self._save_data(f"Add message to conversation {conv_id}")
    
    def get_messages(self, conv_id: int, limit: int = 50) -> List[Dict]:
        """الحصول على رسائل المحادثة"""
        data = self._load_data()
        messages = [msg for msg in data["messages"] if msg["conv_id"] == conv_id]
        return sorted(messages, key=lambda x: x.get('ts', 0), reverse=True)[:limit][::-1]
    
    def list_active_conversations(self) -> List[Dict]:
        """قائمة بالمحادثات النشطة"""
        data = self._load_data()
        return [conv for conv in data["conversations"] if conv.get("active") == 1]
    
    def get_conversation(self, conv_id: int) -> Optional[Dict]:
        """الحصول على محادثة"""
        data = self._load_data()
        for conv in data["conversations"]:
            if conv["id"] == conv_id:
                return conv
        return None
    
    # --- المطابقة المحسنة ---
    def find_available_partner(self, exclude_user_id: int) -> Optional[Dict]:
        """البحث عن شريك متاح"""
        data = self._load_data()
        current_time = now_ts()
        
        # فلترة المستخدمين المتاحين
        available_users = []
        for user_id, user in data["users"].items():
            uid = int(user_id)
            if (uid != exclude_user_id and
                user.get("status") == "idle" and
                user.get("banned_until", 0) < current_time and
                not user.get("active_conversation") and
                (user.get("searching_since", 0) == 0 or 
                 (current_time - user.get("searching_since", 0)) < 300)):  # لا يبحث لأكثر من 5 دقائق
                available_users.append(user)
        
        if available_users:
            # ترتيب عشوائي للمستخدمين
            import random
            return random.choice(available_users)
        
        return None
    
    def find_available_partner_by_gender(self, exclude_user_id: int, gender_pref: str) -> Optional[Dict]:
        """البحث عن شريك حسب الجنس"""
        data = self._load_data()
        current_time = now_ts()
        
        # فلترة المستخدمين المتاحين بنفس الجنس
        available_users = []
        for user_id, user in data["users"].items():
            uid = int(user_id)
            if (uid != exclude_user_id and
                user.get("gender") == gender_pref and
                user.get("status") == "idle" and
                user.get("banned_until", 0) < current_time and
                not user.get("active_conversation")):
                available_users.append(user)
        
        if available_users:
            import random
            return random.choice(available_users)
        
        return None
    
    # --- لوحة المتصدرين ---
    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """لوحة متصدرين النقاط"""
        data = self._load_data()
        users = list(data["users"].values())
        return sorted(users, key=lambda x: x.get('points', 0), reverse=True)[:limit]
    
    def get_stars_leaderboard(self, limit: int = 10) -> List[Dict]:
        """لوحة متصدرين النجوم"""
        data = self._load_data()
        users = list(data["users"].values())
        return sorted(users, key=lambda x: x.get('stars_balance', 0), reverse=True)[:limit]
    
    def get_user_rank(self, user_id: int) -> int:
        """الحصول على ترتيب المستخدم في النقاط"""
        data = self._load_data()
        user_points = self.get_user(user_id).get("points", 0) if self.get_user(user_id) else 0
        
        users = list(data["users"].values())
        users.sort(key=lambda x: x.get('points', 0), reverse=True)
        
        for i, user in enumerate(users, 1):
            if user.get("user_id") == user_id:
                return i
        
        return len(users) + 1
    
    def get_user_stars_rank(self, user_id: int) -> int:
        """الحصول على ترتيب المستخدم في النجوم"""
        data = self._load_data()
        user_stars = self.get_user(user_id).get("stars_balance", 0) if self.get_user(user_id) else 0
        
        users = list(data["users"].values())
        users.sort(key=lambda x: x.get('stars_balance', 0), reverse=True)
        
        for i, user in enumerate(users, 1):
            if user.get("user_id") == user_id:
                return i
        
        return len(users) + 1
    
    # --- VIP ---
    def set_vip(self, user_id: int, days: int, use_stars: bool = False, stars_paid: int = 0):
        """تعيين VIP للمستخدم"""
        data = self._load_data()
        user_key = str(user_id)
        
        if user_key in data["users"]:
            until_ts = now_ts() + (days * 86400)
            
            # تحديث حالة VIP
            data["users"][user_key]["vip_until"] = until_ts
            data["users"][user_key]["vip_days"] = data["users"][user_key].get("vip_days", 0) + days
            data["users"][user_key]["vip_purchases"] = data["users"][user_key].get("vip_purchases", 0) + 1
            
            # تحديد مستوى VIP
            vip_level = 1
            if days >= 30:
                vip_level = 3
            elif days >= 7:
                vip_level = 2
            
            data["users"][user_key]["vip_level"] = vip_level
            data["users"][user_key]["vip_title"] = f'VIP {vip_level}'
            
            # تسجيل عملية الشراء
            purchase = {
                "id": len(data["vip_purchases"]) + 1,
                "user_id": user_id,
                "days": days,
                "points_paid": 0 if use_stars else (days * 20),  # سعر افتراضي
                "stars_paid": stars_paid,
                "ts": now_ts(),
                "purchase_type": "stars" if use_stars else "points"
            }
            
            data["vip_purchases"].append(purchase)
            
            # إذا كانت بالنجوم، تسجيل في جدول النجوم
            if use_stars:
                stars_purchase = {
                    "id": len(data["vip_stars_purchases"]) + 1,
                    "user_id": user_id,
                    "vip_days": days,
                    "stars_paid": stars_paid,
                    "purchase_date": now_ts(),
                    "expiration_date": until_ts
                }
                data["vip_stars_purchases"].append(stars_purchase)
            
            self.cache = data
            self._save_data(f"Set VIP for user {user_id} for {days} days")
    
    def get_vip_status(self, user_id: int) -> Dict[str, Any]:
        """الحصول على حالة VIP للمستخدم"""
        user = self.get_user(user_id)
        if not user:
            return {"is_vip": False, "days_left": 0, "vip_level": 0, "vip_title": ""}
        
        vip_until = user.get('vip_until', 0)
        now = now_ts()
        
        if vip_until > now:
            days_left = (vip_until - now) // 86400
            return {
                "is_vip": True,
                "days_left": days_left,
                "until_ts": vip_until,
                "vip_level": user.get('vip_level', 1),
                "vip_title": user.get('vip_title', 'VIP 1')
            }
        else:
            return {
                "is_vip": False,
                "days_left": 0,
                "vip_level": 0,
                "vip_title": ""
            }
    
    def purchase_vip_with_stars(self, user_id: int, days: int, stars_cost: int) -> bool:
        """شراء VIP بالنجوم"""
        if self.consume_stars(user_id, stars_cost):
            self.set_vip(user_id, days, use_stars=True, stars_paid=stars_cost)
            return True
        return False
    
    # --- المشرفين ---
    def ban_user(self, user_id: int, until_ts: int):
        """حظر مستخدم"""
        data = self._load_data()
        user_key = str(user_id)
        
        if user_key in data["users"]:
            data["users"][user_key]["banned_until"] = until_ts
            
            # إذا كان في محادثة، إغلاقها
            active_conv = data["users"][user_key].get("active_conversation")
            if active_conv:
                self.close_conversation(active_conv)
            
            self.cache = data
            self._save_data(f"Ban user {user_id} until {until_ts}")
    
    def unban_user(self, user_id: int):
        """إلغاء حظر مستخدم"""
        data = self._load_data()
        user_key = str(user_id)
        
        if user_key in data["users"]:
            data["users"][user_key]["banned_until"] = 0
            self.cache = data
            self._save_data(f"Unban user {user_id}")
    
    # --- الإحصائيات المحسنة ---
    def get_stats(self) -> Dict[str, Any]:
        """الحصول على إحصائيات النظام"""
        data = self._load_data()
        current_time = now_ts()
        today_ts = current_time - 86400
        
        # إجمالي المستخدمين
        total_users = len(data["users"])
        
        # المستخدمين النشطين
        active_users = 0
        searching_users = 0
        
        for user in data["users"].values():
            if user.get("status") == "chatting":
                active_users += 1
            elif user.get("status") == "searching":
                searching_users += 1
        
        # المحادثات النشطة
        active_chats = len([conv for conv in data["conversations"] if conv.get("active") == 1])
        
        # إجمالي النقاط والنجوم
        total_points = sum(user.get("points", 0) for user in data["users"].values())
        total_stars = sum(user.get("stars_balance", 0) for user in data["users"].values())
        
        # التوزيع حسب الجنس
        male_users = len([user for user in data["users"].values() if user.get("gender") == "ذكر"])
        female_users = len([user for user in data["users"].values() if user.get("gender") == "أنثى"])
        
        # المحادثات اليوم
        today_chats = len([conv for conv in data["conversations"] if conv.get("start_ts", 0) > today_ts])
        
        # المستخدمين الجدد اليوم
        new_users_today = len([user for user in data["users"].values() if user.get("join_ts", 0) > today_ts])
        
        # عدد مستخدمين VIP
        vip_users = len([user for user in data["users"].values() if user.get("vip_until", 0) > current_time])
        
        # الألعاب اليوم
        today_games = len([game for game in data["games"] if game.get("ts", 0) > today_ts])
        
        # إجمالي الرسائل
        total_messages = len(data["messages"])
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "searching_users": searching_users,
            "active_chats": active_chats,
            "total_points": total_points,
            "total_stars": total_stars,
            "male_users": male_users,
            "female_users": female_users,
            "today_chats": today_chats,
            "new_users_today": new_users_today,
            "vip_users": vip_users,
            "today_games": today_games,
            "total_messages": total_messages
        }
    
    # --- النسخ الاحتياطي ---
    def backup_database(self) -> bool:
        """إنشاء نسخة احتياطية"""
        try:
            # إنشاء اسم الملف بنسخة احتياطية
            backup_file = f"backup_{int(time.time())}.json"
            backup_url = f"{self.base_url}/{backup_file}"
            
            # تحميل البيانات الحالية
            data = self._load_data()
            data_json = json.dumps(data, indent=2, ensure_ascii=False)
            data_bytes = data_json.encode('utf-8')
            encoded_content = base64.b64encode(data_bytes).decode('utf-8')
            
            # رفع النسخة الاحتياطية
            payload = {
                "message": "🤖 نسخة احتياطية تلقائية",
                "content": encoded_content
            }
            
            response = requests.put(backup_url, headers=self.headers, json=payload, timeout=30)
            
            if response.status_code in [200, 201]:
                logger.info(f"Created backup: {backup_file}")
                
                # تحديث وقت آخر نسخة احتياطية
                data["system"]["last_backup"] = now_ts()
                self.cache = data
                self._save_data("Update last backup timestamp")
                
                # الحفاظ على آخر 5 نسخ احتياطية فقط
                self._cleanup_old_backups(keep=5)
                
                return True
            else:
                logger.error(f"Failed to create backup: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return False
    
    def _cleanup_old_backups(self, keep: int = 5):
        """تنظيف النسخ الاحتياطية القديمة"""
        try:
            # الحصول على قائمة الملفات في المستودع
            response = requests.get(self.base_url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                files = response.json()
                backup_files = [f for f in files if f["name"].startswith("backup_") and f["name"].endswith(".json")]
                
                # ترتيب حسب التاريخ (الأقدم أولاً)
                backup_files.sort(key=lambda x: x["name"])
                
                # حذف الملفات القديمة
                for backup in backup_files[:-keep]:
                    delete_url = f"{self.base_url}/{backup['name']}"
                    delete_payload = {
                        "message": "🤖 تنظيف النسخ الاحتياطية القديمة",
                        "sha": backup["sha"]
                    }
                    
                    requests.delete(delete_url, headers=self.headers, json=delete_payload, timeout=30)
                    
        except Exception as e:
            logger.error(f"Error cleaning up old backups: {e}")
    
    # --- التحسين ---
    def optimize_database(self) -> bool:
        """تحسين قاعدة البيانات"""
        try:
            # حذف المستخدمين غير النشطين (أكثر من 30 يوم)
            data = self._load_data()
            current_time = now_ts()
            thirty_days_ago = current_time - (30 * 86400)
            
            users_to_remove = []
            for user_id, user in data["users"].items():
                last_activity = max(
                    user.get("last_activity", 0),
                    user.get("join_ts", 0)
                )
                
                if last_activity < thirty_days_ago and user.get("points", 0) < 10:
                    users_to_remove.append(user_id)
            
            for user_id in users_to_remove:
                del data["users"][user_id]
            
            # حذف المحادثات القديمة (أكثر من 7 أيام)
            data["conversations"] = [conv for conv in data["conversations"] 
                                   if conv.get("last_ts", 0) > (current_time - (7 * 86400))]
            
            # حذف الرسائل القديمة (أكثر من 7 أيام)
            data["messages"] = [msg for msg in data["messages"] 
                              if msg.get("ts", 0) > (current_time - (7 * 86400))]
            
            self.cache = data
            self._save_data("Optimize database")
            
            logger.info(f"Optimized database - Removed {len(users_to_remove)} inactive users")
            return True
            
        except Exception as e:
            logger.error(f"Error optimizing database: {e}")
            return False
    
    def auto_save(self):
        """حفظ تلقائي للبيانات"""
        try:
            if self.cache:
                self._save_data("Auto-save")
                logger.debug("Auto-save completed")
        except Exception as e:
            logger.error(f"Error in auto-save: {e}")
    
    # --- إدارة الأخطاء ---
    def handle_error(self, error: Exception, context: str = ""):
        """معالجة الأخطاء وتسجيلها"""
        error_msg = f"ERROR in {context}: {str(error)}"
        logger.error(error_msg)
        
        # إضافة السجل
        self._add_log(f"ERROR: {context} - {str(error)}")
        
        # محاولة حفظ البيانات
        try:
            if self.cache:
                self._save_data("Emergency save after error")
        except:
            pass


class DatabaseManager:
    """مدير قواعد البيانات مع دعم التبديل بين الأنظمة"""
    
    def __init__(self, use_github: bool = True, config: Optional[Dict] = None):
        self.use_github = use_github
        self.config = config or {}
        
        if use_github:
            # استخدام GitHub كمستودع
            token = os.getenv('GH_TOKEN')
            repo = os.getenv('DATA_REPO')
            db_file = os.getenv('DB_FILE', 'bot_data.json')
            
            if not token or not repo:
                raise ValueError("GitHub token and repository must be configured")
            
            self.db = GitHubDatabase(token, repo, db_file)
            logger.info("Using GitHub as database repository")
        else:
            # استخدام قاعدة البيانات المحلية (SQLite)
            from database import Database
            self.db = Database()
            logger.info("Using local SQLite database")
        
        # تهيئة الحفظ التلقائي
        self._init_auto_save()
    
    def _init_auto_save(self):
        """تهيئة الحفظ التلقائي"""
        def auto_save_worker():
            while True:
                time.sleep(300)  # كل 5 دقائق
                if self.use_github:
                    try:
                        self.db.auto_save()
                    except:
                        pass
        
        import threading
        thread = threading.Thread(target=auto_save_worker, daemon=True)
        thread.start()
    
    def __getattr__(self, name):
        """توجيه جميع الاستدعاءات إلى قاعدة البيانات النشطة"""
        return getattr(self.db, name)
    
    def switch_to_github(self, token: str, repo: str, db_file: str = "bot_data.json"):
        """التبديل إلى استخدام GitHub"""
        try:
            self.db = GitHubDatabase(token, repo, db_file)
            self.use_github = True
            logger.info("Switched to GitHub database")
            return True
        except Exception as e:
            logger.error(f"Failed to switch to GitHub: {e}")
            return False
    
    def switch_to_local(self, db_path: str = "bot_data.sqlite"):
        """التبديل إلى قاعدة البيانات المحلية"""
        try:
            from database import Database
            self.db = Database(db_path)
            self.use_github = False
            logger.info("Switched to local database")
            return True
        except Exception as e:
            logger.error(f"Failed to switch to local database: {e}")
            return False
    
    def backup(self) -> bool:
        """إنشاء نسخة احتياطية"""
        try:
            return self.db.backup_database()
        except AttributeError:
            logger.warning("Backup not supported for current database type")
            return False


# استخدام الفئة في المشروع
def get_database():
    """الحصول على مثيل قاعدة البيانات"""
    use_github = os.getenv('USE_GITHUB_DB', 'true').lower() == 'true'
    
    config = {
        'token': os.getenv('GH_TOKEN'),
        'repo': os.getenv('DATA_REPO'),
        'db_file': os.getenv('DB_FILE', 'bot_data.json')
    }
    
    return DatabaseManager(use_github=use_github, config=config)


# نموذج تهيئة المتغيرات البيئية
"""
# في ملف .env أو إعدادات الخادم
USE_GITHUB_DB=true
GH_TOKEN=your_github_token_here
DATA_REPO=your_username/your_repo_name
DB_FILE=bot_data.json
""" 
