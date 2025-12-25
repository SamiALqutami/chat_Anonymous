import os, requests, json, base64, time, logging, random, string

logger = logging.getLogger(__name__)

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
            return {"users": {}, "logs": [], "stats": {"total_chats": 0}}, None
        except: return {"users": {}, "logs": [], "stats": {}}, None

    def _save(self, data, sha, msg="Admin Action"):
        try:
            content = base64.b64encode(json.dumps(data, indent=4, ensure_ascii=False).encode('utf-8')).decode('utf-8')
            res = requests.put(self.url, headers=self.headers, json={"message": msg, "content": content, "sha": sha}, timeout=15)
            return res.status_code in [200, 201]
        except: return False

    # --- البحث عبر اسم المستخدم (للوحة التحكم) ---
    def get_user_by_username(self, username):
        data, _ = self._get_raw_data()
        username = username.replace("@", "").strip()
        for u in data["users"].values():
            if u.get("username") == username:
                return u
        return None

    # --- نظام الحظر والـ VIP ---
    def ban_user(self, identifier, until_ts):
        data, sha = self._get_raw_data()
        user = self.get_user_by_username(identifier) if isinstance(identifier, str) else data["users"].get(str(identifier))
        if user:
            uid = str(user["user_id"])
            data["users"][uid]["banned_until"] = until_ts
            self._save(data, sha, f"Ban User {uid}")
            return True
        return False

    def set_vip_all(self, days):
        data, sha = self._get_raw_data()
        until = int(time.time()) + (days * 86400)
        for uid in data["users"]:
            data["users"][uid]["vip_until"] = until
        self._save(data, sha, "VIP for ALL")

    def add_points_all(self, points):
        data, sha = self._get_raw_data()
        for uid in data["users"]:
            data["users"][uid]["points"] += points
        self._save(data, sha, f"Points {points} for ALL")

    # --- نظام البحث المتطور وإظهار البيانات ---
    def get_user(self, user_id):
        data, _ = self._get_raw_data()
        u = data["users"].get(str(user_id))
        if u: # حساب التقييم تلقائياً
            u['avg_rating'] = round(u.get('rating_sum', 0) / max(u.get('total_ratings', 1), 1), 1)
            u['is_vip'] = u.get('vip_until', 0) > time.time()
        return u

    def list_active_conversations(self):
        data, _ = self._get_raw_data()
        return [{"user_a": int(k), "user_b": v["partner"]} for k, v in data["users"].items() if v.get("status") == "chatting" and v.get("partner")]

    def list_all_users(self):
        data, _ = self._get_raw_data()
        return list(data["users"].values())

    def get_leaderboard(self, limit=10):
        data, _ = self._get_raw_data()
        users = list(data["users"].values())
        return sorted(users, key=lambda x: x.get('points', 0), reverse=True)[:limit]

    # --- السجلات (Monitoring) ---
    def add_log(self, action):
        data, sha = self._get_raw_data()
        log_entry = f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {action}"
        if "logs" not in data: data["logs"] = []
        data["logs"].insert(0, log_entry)
        data["logs"] = data["logs"][:100] # حفظ آخر 100 سجل فقط
        self._save(data, sha)

    # دالة إنشاء المستخدم مع التأكد من وجود كل الحقول
    def create_user(self, info):
        data, sha = self._get_raw_data()
        uid = str(info.get("user_id"))
        if uid not in data["users"]:
            data["users"][uid] = {
                "user_id": int(uid), "username": info.get("username", ""),
                "first_name": info.get("first_name", ""), "points": 50,
                "status": "idle", "gender": "غير محدد", "age": "غير محدد",
                "country": "غير محدد", "vip_until": 0, "rating_sum": 0, "total_ratings": 0,
                "partner": None, "join_ts": int(time.time())
            }
            self._save(data, sha)
        return data["users"][uid]

    def set_user_status(self, user_id, status, partner=None):
        data, sha = self._get_raw_data()
        if str(user_id) in data["users"]:
            data["users"][str(user_id)]["status"] = status
            data["users"][str(user_id)]["partner"] = partner
            self._save(data, sha)
            
    def consume_points(self, user_id, points):
        data, sha = self._get_raw_data()
        uid = str(user_id)
        if uid in data["users"] and data["users"][uid]["points"] >= points:
            data["users"][uid]["points"] -= points
            self._save(data, sha)
            return True
        return False
        
    def find_available_partner(self, exclude_id):
        data, _ = self._get_raw_data()
        pool = [u for k, u in data["users"].items() if k != str(exclude_id) and u.get("status") == "searching"]
        return random.choice(pool) if pool else None
 
