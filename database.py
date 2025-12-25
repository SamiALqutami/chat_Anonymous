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
        """جلب البيانات والـ SHA من جيت هاب"""
        try:
            response = requests.get(self.url, headers=self.headers, timeout=15)
            if response.status_code == 200:
                content = response.json()
                decoded_data = base64.b64decode(content['content']).decode('utf-8')
                return json.loads(decoded_data), content['sha']
            # إذا كان الملف غير موجود أو هناك خطأ، ننشئ هيكل افتراضي
            return {"users": {}, "stats": {"total_chats": 0, "daily_new_users": 0}}, None
        except Exception as e:
            logger.error(f"❌ خطأ في جلب البيانات: {e}")
            return {"users": {}, "stats": {"total_chats": 0}}, None

    def _save_data(self, data, sha, message="Database update"):
        """حفظ البيانات (Commit)"""
        try:
            updated_json = json.dumps(data, indent=4, ensure_ascii=False)
            encoded_content = base64.b64encode(updated_json.encode('utf-8')).decode('utf-8')
            payload = {"message": message, "content": encoded_content}
            if sha: payload["sha"] = sha
            
            res = requests.put(self.url, headers=self.headers, json=payload, timeout=15)
            return res.status_code in [200, 201]
        except Exception as e:
            logger.error(f"❌ فشل الحفظ في جيت هاب: {e}")
            return False

    # --- إدارة المستخدمين ---
    def get_user(self, user_id):
        data, _ = self._get_raw_data()
        return data.get("users", {}).get(str(user_id))

    def create_user(self, info):
        """تسجيل المستخدم بكافة الحقول المطلوبة للبوت"""
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
                "join_ts": int(time.time()),
                "vip_until": 0,
                "total_chats": 0,
                "referrals": 0
            }
            self._save_data(data, sha, f"New User: {uid}")
        return data["users"][uid]

    # --- نظام البحث والدردشة ---
    def find_available_partner(self, exclude_id):
        data, _ = self._get_raw_data()
        for uid, info in data["users"].items():
            if uid != str(exclude_id) and info.get("status") == "searching":
                return info
        return None

    def set_user_status(self, user_id, status, partner=None):
        data, sha = self._get_raw_data()
        uid = str(user_id)
        if uid in data["users"]:
            data["users"][uid]["status"] = status
            data["users"][uid]["partner"] = partner
            if status == "chatting":
                data["users"][uid]["total_chats"] = data["users"][uid].get("total_chats", 0) + 1
            self._save_data(data, sha, f"Update status: {uid} to {status}")

    # --- الإحصائيات (لحل مشكلة الـ 0) ---
    def get_stats(self):
        data, _ = self._get_raw_data()
        u = data.get("users", {})
        now = int(time.time())
        return {
            "total_users": len(u),
            "searching_users": sum(1 for v in u.values() if v.get("status") == "searching"),
            "active_chats": sum(1 for v in u.values() if v.get("status") == "chatting") // 2,
            "vip_users": sum(1 for v in u.values() if v.get("vip_until", 0) > now),
            "male_users": sum(1 for v in u.values() if v.get("gender") == "ذكر"),
            "female_users": sum(1 for v in u.values() if v.get("gender") == "أنثى"),
            "total_points": sum(v.get("points", 0) for v in u.values())
        }

    # --- دوال العمليات المالية والنقاط ---
    def add_points(self, user_id, points):
        data, sha = self._get_raw_data()
        uid = str(user_id)
        if uid in data["users"]:
            data["users"][uid]["points"] = data["users"][uid].get("points", 0) + points
            self._save_data(data, sha, f"Add points: {uid}")

    def add_stars(self, user_id, stars):
        data, sha = self._get_raw_data()
        uid = str(user_id)
        if uid in data["users"]:
            data["users"][uid]["stars_balance"] = data["users"][uid].get("stars_balance", 0) + stars
            self._save_data(data, sha, f"Add stars: {uid}")

    def get_top_users(self, limit=10):
        data, _ = self._get_raw_data()
        users_list = list(data.get("users", {}).values())
        return sorted(users_list, key=lambda x: x.get('points', 0), reverse=True)[:limit]

    def optimize_database(self):
        return True # لا نحتاجها في JSON ولكن نتركها لكي لا ينهار bot_main
