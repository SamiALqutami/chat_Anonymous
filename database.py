import os
import requests
import json
import base64
import time
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path=None):
        self.token = os.getenv('GH_TOKEN')
        self.repo = os.getenv('DATA_REPO')
        self.file_path = os.getenv('DB_FILE', 'db.json')
        self.url = f"https://api.github.com/repos/{self.repo}/contents/{self.file_path}"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }

    def _get_raw_data(self):
        """جلب البيانات مع التعامل مع الـ SHA"""
        try:
            response = requests.get(self.url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                content = response.json()
                decoded_data = base64.b64decode(content['content']).decode('utf-8')
                return json.loads(decoded_data), content['sha']
            return {"users": {}, "stats": {"total_chats": 0, "daily_new_users": 0}}, None
        except Exception as e:
            logger.error(f"Error: {e}")
            return {"users": {}, "stats": {"total_chats": 0, "daily_new_users": 0}}, None

    def _save_data(self, data, sha, message="Database Update"):
        """حفظ البيانات في GitHub"""
        try:
            updated_json = json.dumps(data, indent=4, ensure_ascii=False)
            encoded_content = base64.b64encode(updated_json.encode('utf-8')).decode('utf-8')
            payload = {"message": message, "content": encoded_content, "sha": sha}
            res = requests.put(self.url, headers=self.headers, json=payload, timeout=10)
            return res.status_code in [200, 201]
        except Exception as e:
            logger.error(f"Save Error: {e}")
            return False

    def get_user(self, user_id):
        data, _ = self._get_raw_data()
        return data.get("users", {}).get(str(user_id))

    def create_user(self, info):
        """إنشاء مستخدم جديد بكافة الحقول التي يطلبها bot_main.py"""
        data, sha = self._get_raw_data()
        uid = str(info.get("user_id"))
        if uid not in data["users"]:
            data["users"][uid] = {
                "user_id": int(uid),
                "username": info.get("username", ""),
                "first_name": info.get("first_name", ""),
                "points": 50,
                "stars_balance": 0,
                "status": "idle",
                "partner": None,
                "gender": "غير محدد",
                "gender_changed": 0,
                "vip_until": 0,
                "vip_days": 0,
                "total_chats": 0,
                "join_ts": int(time.time()),
                "last_activity": int(time.time())
            }
            # تحديث إحصائيات اليوم للمستخدمين الجدد
            data["stats"]["daily_new_users"] = data["stats"].get("daily_new_users", 0) + 1
            self._save_data(data, sha, f"New User: {uid}")
        return data["users"][uid]

    def find_available_partner(self, exclude_user_id):
        """تفعيل زر البحث العشوائي"""
        data, _ = self._get_raw_data()
        for uid, info in data["users"].items():
            if uid != str(exclude_user_id) and info.get("status") == "searching":
                return info
        return None

    def set_user_status(self, user_id, status, partner=None):
        data, sha = self._get_raw_data()
        uid = str(user_id)
        if uid in data["users"]:
            data["users"][uid]["status"] = status
            data["users"][uid]["partner"] = partner
            data["users"][uid]["last_activity"] = int(time.time())
            if status == "chatting":
                data["users"][uid]["total_chats"] += 1
                data["stats"]["total_chats"] += 1
            self._save_data(data, sha, f"Status Update: {uid}")

    def get_stats(self):
        """تغذية لوحة الإحصائيات (حل مشكلة الأصفار)"""
        data, _ = self._get_raw_data()
        users = data.get("users", {})
        now = int(time.time())
        return {
            "total_users": len(users),
            "active_users": sum(1 for u in users.values() if u.get("status") == "chatting"),
            "searching_users": sum(1 for u in users.values() if u.get("status") == "searching"),
            "vip_users": sum(1 for u in users.values() if u.get("vip_until", 0) > now),
            "male_users": sum(1 for u in users.values() if u.get("gender") == "ذكر"),
            "female_users": sum(1 for u in users.values() if u.get("gender") == "أنثى"),
            "daily_new_users": data["stats"].get("daily_new_users", 0),
            "total_chats": data["stats"].get("total_chats", 0)
        }

    def get_top_users(self, limit=10):
        """لوحة المتصدرين"""
        data, _ = self._get_raw_data()
        users_list = list(data.get("users", {}).values())
        return sorted(users_list, key=lambda x: x.get('points', 0), reverse=True)[:limit]

    def add_points(self, user_id, points):
        data, sha = self._get_raw_data()
        uid = str(user_id)
        if uid in data["users"]:
            data["users"][uid]["points"] += points
            self._save_data(data, sha, f"Points Add: {uid}")

    def optimize_database(self): return True
 
