import os, requests, json, base64, time, logging

class Database:
    def __init__(self, db_path=None):
        self.token = os.getenv('GH_TOKEN')
        self.repo = os.getenv('DATA_REPO')
        self.file_path = os.getenv('DB_FILE', 'db.json')
        self.url = f"https://api.github.com/repos/{self.repo}/contents/{self.file_path}"
        self.headers = {"Authorization": f"token {self.token}", "Accept": "application/vnd.github.v3+json"}

    def _get_raw_data(self):
        try:
            res = requests.get(self.url, headers=self.headers, timeout=15)
            if res.status_code == 200:
                content = res.json()
                return json.loads(base64.b64decode(content['content']).decode('utf-8')), content['sha']
            return {"users": {}, "stats": {"total_chats": 0}}, None
        except: return {"users": {}, "stats": {"total_chats": 0}}, None

    def _save(self, data, sha):
        content = base64.b64encode(json.dumps(data, indent=4, ensure_ascii=False).encode('utf-8')).decode('utf-8')
        payload = {"message": "Fixing Logs Errors", "content": content, "sha": sha}
        requests.put(self.url, headers=self.headers, json=payload, timeout=15)

    def create_user(self, info):
        data, sha = self._get_raw_data()
        uid = str(info.get("user_id"))
        if uid not in data["users"]:
            data["users"][uid] = {
                "user_id": int(uid), "username": info.get("username", ""),
                "first_name": info.get("first_name", ""), "points": 50,
                "stars_balance": 0, "status": "idle", "gender": "غير محدد",
                "vip_until": 0, "join_ts": int(time.time()), "total_chats": 0
            }
            self._save(data, sha)
        return data["users"][uid]

    def get_user(self, user_id):
        data, _ = self._get_raw_data()
        user = data.get("users", {}).get(str(user_id))
        # حل مشكلة NoneType: إذا لم يجد المستخدم، يقوم بإنشائه فوراً
        if not user:
            return {"user_id": int(user_id), "status": "idle", "points": 0}
        return user

    def get_stats(self):
        data, _ = self._get_raw_data()
        u = data.get("users", {})
        now = int(time.time())
        return {
            "total_users": len(u),
            "active_users": sum(1 for v in u.values() if v.get("status") == "chatting"),
            "searching_users": sum(1 for v in u.values() if v.get("status") == "searching"),
            "vip_users": sum(1 for v in u.values() if v.get("vip_until", 0) > now),
            "male_users": sum(1 for v in u.values() if v.get("gender") == "ذكر"),
            "female_users": sum(1 for v in u.values() if v.get("gender") == "أنثى")
        }

    # حل خطأ السجلات: إضافة get_leaderboard
    def get_leaderboard(self, limit=10):
        data, _ = self._get_raw_data()
        users = list(data.get("users", {}).values())
        return sorted(users, key=lambda x: x.get('points', 0), reverse=True)[:limit]

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
            self._save(data, sha)

    def optimize_database(self): return True
