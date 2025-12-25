import os
import requests
import json
import base64
import logging

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
        """جلب البيانات من المستودع الخاص"""
        try:
            response = requests.get(self.url, headers=self.headers)
            if response.status_code == 200:
                content = response.json()
                decoded_data = base64.b64decode(content['content']).decode('utf-8')
                return json.loads(decoded_data), content['sha']
            return {"users": {}, "stats": {"total_chats": 0}}, None
        except:
            return {"users": {}, "stats": {"total_chats": 0}}, None

    def _save_data(self, data, sha, message="Update Database"):
        """حفظ البيانات في مستودع جيت هاب (Commit)"""
        updated_json = json.dumps(data, indent=4, ensure_ascii=False)
        encoded_content = base64.b64encode(updated_json.encode('utf-8')).decode('utf-8')
        payload = {"message": message, "content": encoded_content, "sha": sha}
        res = requests.put(self.url, headers=self.headers, json=payload)
        return res.status_code in [200, 201]

    def get_user(self, user_id):
        data, _ = self._get_raw_data()
        return data.get("users", {}).get(str(user_id))

    def create_user(self, user_id, username, first_name):
        """هذه الدالة التي كانت تنقصك وحلت مشكلة /start"""
        data, sha = self._get_raw_data()
        if str(user_id) not in data["users"]:
            data["users"][str(user_id)] = {
                "id": user_id,
                "username": username,
                "first_name": first_name,
                "points": 50,
                "status": "idle",
                "partner": None
            }
            self._save_data(data, sha, f"New user: {user_id}")
        return data["users"][str(user_id)]

    def get_top_users(self, limit=10):
        """عرض المتصدرين"""
        data, _ = self._get_raw_data()
        users = list(data.get("users", {}).values())
        # ترتيب حسب النقاط
        sorted_users = sorted(users, key=lambda x: x.get('points', 0), reverse=True)
        return sorted_users[:limit]

    def get_stats(self):
        """لوحة المشرف والإحصائيات"""
        data, _ = self._get_raw_data()
        total_users = len(data.get("users", {}))
        return {"total_users": total_users, "active_users": 0} # يمكنك تطويرها لاحقاً

    def set_user_status(self, user_id, status, partner=None):
        """تحديث حالة المستخدم (بحث، دردشة، الخ)"""
        data, sha = self._get_raw_data()
        if str(user_id) in data["users"]:
            data["users"][str(user_id)]["status"] = status
            data["users"][str(user_id)]["partner"] = partner
            self._save_data(data, sha, f"Status update: {user_id}")
