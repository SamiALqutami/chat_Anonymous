import os
import requests
import json
import base64

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
        try:
            response = requests.get(self.url, headers=self.headers)
            if response.status_code == 200:
                content = response.json()
                decoded_data = base64.b64decode(content['content']).decode('utf-8')
                return json.loads(decoded_data), content['sha']
            return {"users": {}, "stats": {"total_chats": 0}}, None
        except:
            return {"users": {}, "stats": {"total_chats": 0}}, None

    def _save_data(self, data, sha, message="Update"):
        updated_json = json.dumps(data, indent=4, ensure_ascii=False)
        encoded_content = base64.b64encode(updated_json.encode('utf-8')).decode('utf-8')
        payload = {"message": message, "content": encoded_content, "sha": sha}
        res = requests.put(self.url, headers=self.headers, json=payload)
        return res.status_code in [200, 201]

    def get_user(self, user_id):
        data, _ = self._get_raw_data()
        user = data.get("users", {}).get(str(user_id))
        return user

    def create_user(self, user_id, username, first_name):
        data, sha = self._get_raw_data()
        if str(user_id) not in data["users"]:
            data["users"][str(user_id)] = {
                "id": int(user_id),
                "username": username,
                "first_name": first_name,
                "points": 50,
                "status": "idle",
                "partner": None
            }
            self._save_data(data, sha, f"New user: {user_id}")
        return data["users"][str(user_id)]

    def get_idle_user(self, exclude_user_id):
        """البحث عن شخص آخر يبحث عن دردشة"""
        data, _ = self._get_raw_data()
        for uid, info in data.get("users", {}).items():
            if uid != str(exclude_user_id) and info.get("status") == "searching":
                return info
        return None

    def set_user_status(self, user_id, status, partner=None):
        data, sha = self._get_raw_data()
        uid_str = str(user_id)
        if uid_str in data["users"]:
            data["users"][uid_str]["status"] = status
            data["users"][uid_str]["partner"] = partner
            self._save_data(data, sha, f"Status: {uid_str} -> {status}")

    def get_stats(self):
        data, _ = self._get_raw_data()
        return {"total_users": len(data.get("users", {})), "active_chats": 0}

    def get_top_users(self, limit=10):
        data, _ = self._get_raw_data()
        users = list(data.get("users", {}).values())
        return sorted(users, key=lambda x: x.get('points', 0), reverse=True)[:limit]
