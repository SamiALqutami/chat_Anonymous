import os, requests, json, base64, time

class Database:
    def __init__(self, db_path=None):
        self.token = os.getenv('GH_TOKEN')
        self.repo = os.getenv('DATA_REPO')
        self.file_path = os.getenv('DB_FILE', 'db.json')
        self.url = f"https://api.github.com/repos/{self.repo}/contents/{self.file_path}"
        self.headers = {"Authorization": f"token {self.token}", "Accept": "application/vnd.github.v3+json"}

    def _get_raw_data(self):
        try:
            res = requests.get(self.url, headers=self.headers, timeout=10)
            if res.status_code == 200:
                content = res.json()
                return json.loads(base64.b64decode(content['content']).decode('utf-8')), content['sha']
            return {"users": {}, "stats": {"total_chats": 0}}, None
        except: return {"users": {}, "stats": {"total_chats": 0}}, None

    def _save(self, data, sha):
        updated_json = json.dumps(data, indent=4, ensure_ascii=False)
        encoded = base64.b64encode(updated_json.encode('utf-8')).decode('utf-8')
        payload = {"message": "Update DB", "content": encoded, "sha": sha}
        requests.put(self.url, headers=self.headers, json=payload, timeout=10)

    def create_user(self, info):
        data, sha = self._get_raw_data()
        uid = str(info.get("user_id"))
        if uid not in data["users"]:
            data["users"][uid] = {
                "user_id": int(uid), "points": 50, "stars_balance": 0,
                "vip_until": 0, "status": "idle", "join_ts": int(time.time()),
                "total_chats": 0, "gender": "غير محدد"
            }
            self._save(data, sha)
        return data["users"][uid]

    def get_stats(self):
        data, _ = self._get_raw_data()
        u = data.get("users", {})
        return {
            "total_users": len(u),
            "total_points": sum(v.get("points", 0) for v in u.values()),
            "vip_users": sum(1 for v in u.values() if v.get("vip_until", 0) > time.time())
        }

    def optimize_database(self): return True # دالة وهمية لمنع الخطأ البرمجي
 
