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
        """جلب كل البيانات من مستودع SQL_Chat"""
        try:
            response = requests.get(self.url, headers=self.headers, timeout=15)
            if response.status_code == 200:
                content = response.json()
                decoded_data = base64.b64decode(content['content']).decode('utf-8')
                return json.loads(decoded_data), content['sha']
            return {"users": {}, "stats": {"total_chats": 0}}, None
        except Exception as e:
            logger.error(f"خطأ في جلب البيانات: {e}")
            return {"users": {}, "stats": {"total_chats": 0}}, None

    def _save_data(self, data, sha, message="Bot Update"):
        """حفظ التعديلات في المستودع"""
        try:
            updated_json = json.dumps(data, indent=4, ensure_ascii=False)
            encoded_content = base64.b64encode(updated_json.encode('utf-8')).decode('utf-8')
            payload = {"message": message, "content": encoded_content, "sha": sha}
            res = requests.put(self.url, headers=self.headers, json=payload, timeout=15)
            return res.status_code in [200, 201]
        except Exception as e:
            logger.error(f"خطأ في الحفظ: {e}")
            return False

    # --- إدارة المستخدمين ---
    def create_user(self, info):
        data, sha = self._get_raw_data()
        user_id = str(info.get("user_id"))
        if user_id not in data["users"]:
            data["users"][user_id] = {
                "user_id": int(user_id),
                "username": info.get("username", ""),
                "first_name": info.get("first_name", ""),
                "points": 50,
                "stars_balance": 0,
                "status": "idle",
                "partner": None,
                "gender": "غير محدد",
                "join_ts": int(time.time()),
                "total_chats": 0,
                "vip_until": 0
            }
            self._save_data(data, sha, f"Register User: {user_id}")
        return data["users"][user_id]

    def get_user(self, user_id):
        data, _ = self._get_raw_data()
        return data.get("users", {}).get(str(user_id))

    # --- نظام البحث العشوائي (المحرك الأساسي) ---
    def find_available_partner(self, exclude_user_id):
        """البحث عن شخص حالته 'searching'"""
        data, _ = self._get_raw_data()
        for uid, info in data["users"].items():
            if uid != str(exclude_user_id) and info.get("status") == "searching":
                return info
        return None

    def set_user_status(self, user_id, status, partner=None):
        """تحديث الحالة (idle, searching, chatting)"""
        data, sha = self._get_raw_data()
        uid = str(user_id)
        if uid in data["users"]:
            data["users"][uid]["status"] = status
            data["users"][uid]["partner"] = partner
            if status == "chatting":
                data["users"][uid]["total_chats"] = data["users"][uid].get("total_chats", 0) + 1
            self._save_data(data, sha, f"Update Status: {uid} to {status}")

    # --- الإحصائيات ولوحة التحكم ---
    def get_stats(self):
        data, _ = self._get_raw_data()
        users = data.get("users", {})
        now = int(time.time())
        return {
            "total_users": len(users),
            "searching_users": sum(1 for u in users.values() if u.get("status") == "searching"),
            "active_chats": sum(1 for u in users.values() if u.get("status") == "chatting") // 2,
            "vip_users": sum(1 for u in users.values() if u.get("vip_until", 0) > now),
            "total_points": sum(u.get("points", 0) for u in users.values()),
            "male_users": sum(1 for u in users.values() if u.get("gender") == "ذكر"),
            "female_users": sum(1 for u in users.values() if u.get("gender") == "أنثى")
        }

    # --- دوال إضافية لمنع أخطاء البوت القديم ---
    def add_points(self, user_id, points):
        data, sha = self._get_raw_data()
        uid = str(user_id)
        if uid in data["users"]:
            data["users"][uid]["points"] = data["users"][uid].get("points", 0) + points
            self._save_data(data, sha, f"Add points to {uid}")

    def optimize_database(self): return True
    def get_leaderboard(self, limit=10):
        data, _ = self._get_raw_data()
        users = list(data.get("users", {}).values())
        return sorted(users, key=lambda x: x.get('points', 0), reverse=True)[:limit]
 
