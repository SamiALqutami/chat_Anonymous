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
            return {"users": {}, "stats": {"total_chats": 0}}, None
        except: return {"users": {}, "stats": {}}, None

    def _save(self, data, sha, msg="Sync"):
        try:
            content = base64.b64encode(json.dumps(data, indent=4, ensure_ascii=False).encode('utf-8')).decode('utf-8')
            res = requests.put(self.url, headers=self.headers, json={"message": msg, "content": content, "sha": sha}, timeout=15)
            return res.status_code in [200, 201]
        except: return False

    # --- إدارة المستخدمين (تطابق كامل مع SQL) ---
    def create_user(self, info):
        data, sha = self._get_raw_data()
        uid = str(info.get("user_id"))
        if uid not in data["users"]:
            ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            data["users"][uid] = {
                "user_id": int(uid), "username": info.get("username", ""),
                "first_name": info.get("first_name", ""), "last_name": info.get("last_name", ""),
                "points": 50, "stars_balance": 0, "status": "idle", "gender": "غير محدد",
                "age": "غير محدد", "country": "غير محدد", "bio": "", "vip_until": 0,
                "vip_level": 0, "vip_title": "", "total_chats": 0, "join_ts": int(time.time()),
                "referral_code": ref_code, "last_reward_ts": 0, "partner": None,
                "rating_sum": 0, "total_ratings": 0
            }
            self._save(data, sha, f"New User {uid}")
        return data["users"][uid]

    def get_user(self, user_id):
        data, _ = self._get_raw_data()
        return data["users"].get(str(user_id))

    def list_all_users(self):
        data, _ = self._get_raw_data()
        return list(data["users"].values())

    def update_user_profile(self, user_id, updates):
        data, sha = self._get_raw_data()
        uid = str(user_id)
        if uid in data["users"]:
            data["users"][uid].update(updates)
            self._save(data, sha)

    # --- المحادثات والبحث (إصلاح خطأ list_active_conversations) ---
    def set_user_status(self, user_id, status, partner=None):
        data, sha = self._get_raw_data()
        uid = str(user_id)
        if uid in data["users"]:
            data["users"][uid]["status"] = status
            data["users"][uid]["partner"] = partner
            if status == "chatting":
                data["users"][uid]["total_chats"] += 1
            self._save(data, sha)

    def list_active_conversations(self):
        data, _ = self._get_raw_data()
        active = []
        for uid, u in data["users"].items():
            if u.get("status") == "chatting" and u.get("partner"):
                # لتجنب التكرار (الشريكين)
                if int(uid) < int(u["partner"]):
                    active.append({"user_a": int(uid), "user_b": u["partner"]})
        return active

    def find_available_partner(self, exclude_id):
        data, _ = self._get_raw_data()
        pool = [u for k, u in data["users"].items() if k != str(exclude_id) and u.get("status") == "searching"]
        return random.choice(pool) if pool else None

    # --- الإحصائيات والمتصدرين ---
    def get_stats(self):
        data, _ = self._get_raw_data()
        u = data.get("users", {})
        return {
            "total_users": len(u),
            "active_users": sum(1 for v in u.values() if v.get("status") == "chatting"),
            "searching_users": sum(1 for v in u.values() if v.get("status") == "searching"),
            "vip_users": sum(1 for v in u.values() if v.get("vip_until", 0) > time.time()),
            "total_points": sum(v.get("points", 0) for v in u.values()),
            "male_users": sum(1 for v in u.values() if v.get("gender") == "ذكر"),
            "female_users": sum(1 for v in u.values() if v.get("gender") == "أنثى")
        }

    def get_leaderboard(self, limit=10):
        data, _ = self._get_raw_data()
        users = list(data.get("users", {}).values())
        return sorted(users, key=lambda x: x.get('points', 0), reverse=True)[:limit]

    # --- وظائف VIP والجوائز ---
    def get_vip_status(self, user_id):
        user = self.get_user(user_id)
        if not user: return {"is_vip": False}
        is_vip = user.get("vip_until", 0) > time.time()
        return {"is_vip": is_vip, "days_left": (user["vip_until"] - time.time()) // 86400 if is_vip else 0}

    def add_points(self, user_id, points):
        data, sha = self._get_raw_data()
        uid = str(user_id)
        if uid in data["users"]:
            data["users"][uid]["points"] += points
            self._save(data, sha)

    def consume_points(self, user_id, points):
        data, sha = self._get_raw_data()
        uid = str(user_id)
        if uid in data["users"] and data["users"][uid]["points"] >= points:
            data["users"][uid]["points"] -= points
            self._save(data, sha)
            return True
        return False

    def optimize_database(self): return True
 
