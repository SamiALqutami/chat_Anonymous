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
        """جلب البيانات من GitHub"""
        try:
            response = requests.get(self.url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                content = response.json()
                decoded_data = base64.b64decode(content['content']).decode('utf-8')
                return json.loads(decoded_data), content['sha']
            return {"users": {}, "stats": {"total_chats": 0, "total_messages": 0}}, None
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            return {"users": {}, "stats": {"total_chats": 0, "total_messages": 0}}, None

    def _save_data(self, data, sha, message="Database Update"):
        """حفظ البيانات (Commit)"""
        try:
            updated_json = json.dumps(data, indent=4, ensure_ascii=False)
            encoded_content = base64.b64encode(updated_json.encode('utf-8')).decode('utf-8')
            payload = {"message": message, "content": encoded_content, "sha": sha}
            res = requests.put(self.url, headers=self.headers, json=payload, timeout=10)
            return res.status_code in [200, 201]
        except Exception as e:
            logger.error(f"Error saving data: {e}")
            return False

    # --- إدارة المستخدمين (تحديث ليتناسب مع SQLite القديم) ---
    def create_user(self, info):
        data, sha = self._get_raw_data()
        user_id = str(info.get("user_id"))
        if user_id not in data["users"]:
            data["users"][user_id] = {
                "user_id": int(user_id),
                "username": info.get("username", ""),
                "first_name": info.get("first_name", ""),
                "points": 0,
                "stars_balance": 0,
                "status": "idle",
                "join_ts": int(time.time()),
                "gender": "غير محدد",
                "vip_until": 0,
                "total_chats": 0
            }
            self._save_data(data, sha, f"New User: {user_id}")
        return data["users"][user_id]

    def get_user(self, user_id):
        data, _ = self._get_raw_data()
        return data.get("users", {}).get(str(user_id))

    def add_points(self, user_id, points):
        data, sha = self._get_raw_data()
        uid = str(user_id)
        if uid in data["users"]:
            data["users"][uid]["points"] = data["users"][uid].get("points", 0) + points
            self._save_data(data, sha, f"Points added to {uid}")

    def add_stars(self, user_id, stars):
        data, sha = self._get_raw_data()
        uid = str(user_id)
        if uid in data["users"]:
            data["users"][uid]["stars_balance"] = data["users"][uid].get("stars_balance", 0) + stars
            self._save_data(data, sha, f"Stars added to {uid}")

    # --- الإحصائيات (التي طلبها المشرف) ---
    def get_stats(self):
        data, _ = self._get_raw_data()
        users = data.get("users", {})
        return {
            "total_users": len(users),
            "active_chats": sum(1 for u in users.values() if u.get("status") == "chatting"),
            "total_points": sum(u.get("points", 0) for u in users.values()),
            "total_stars": sum(u.get("stars_balance", 0) for u in users.values())
        }

    # --- حل مشكلة optimize_database ---
    def optimize_database(self):
        """هذه الدالة الآن صامتة لأن جيت هاب لا يحتاج VACUUM مثل SQLite"""
        print("✅ جاري تحسين قاعدة البيانات السحابية...")
        return True

    def set_user_status(self, user_id, status):
        data, sha = self._get_raw_data()
        uid = str(user_id)
        if uid in data["users"]:
            data["users"][uid]["status"] = status
            self._save_data(data, sha, f"Status Update: {uid}")
