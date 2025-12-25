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
            return {"users": {}, "conversations": [], "games": [], "reports": [], "gifts": [], "stats": {"total_chats": 0}}, None
        except: 
            return {"users": {}, "conversations": [], "stats": {}}, None

    def _save(self, data, sha, msg="Sync Data"):
        try:
            content = base64.b64encode(json.dumps(data, indent=4, ensure_ascii=False).encode('utf-8')).decode('utf-8')
            res = requests.put(self.url, headers=self.headers, json={"message": msg, "content": content, "sha": sha}, timeout=15)
            return res.status_code in [200, 201]
        except: return False

    # --- إدارة المستخدمين ---
    def create_user(self, info):
        data, sha = self._get_raw_data()
        uid = str(info.get("user_id"))
        if uid not in data["users"]:
            ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            data["users"][uid] = {
                "user_id": int(uid), "username": info.get("username", ""),
                "first_name": info.get("first_name", ""), "points": 50,
                "stars_balance": 0, "status": "idle", "gender": "غير محدد",
                "vip_until": 0, "vip_level": 0, "vip_title": "", "total_chats": 0,
                "join_ts": int(time.time()), "referral_code": ref_code, "last_reward_ts": 0, "partner": None
            }
            self._save(data, sha, f"New User {uid}")
        return data["users"][uid]

    def get_user(self, user_id):
        data, _ = self._get_raw_data()
        return data["users"].get(str(user_id))

    def update_user_profile(self, user_id, updates):
        data, sha = self._get_raw_data()
        uid = str(user_id)
        if uid in data["users"]:
            data["users"][uid].update(updates)
            self._save(data, sha)

    def set_user_status(self, user_id, status, partner=None):
        data, sha = self._get_raw_data()
        uid = str(user_id)
        if uid in data["users"]:
            data["users"][uid]["status"] = status
            data["users"][uid]["partner"] = partner
            if status == "chatting":
                data["users"][uid]["total_chats"] += 1
                data["stats"]["total_chats"] += 1
            self._save(data, sha)

    # --- المحادثات ---
    def list_active_conversations(self):
        data, _ = self._get_raw_data()
        # نعتبر أي مستخدم حالته chatting هو في محادثة نشطة
        active = []
        for uid, info in data["users"].items():
            if info.get("status") == "chatting" and info.get("partner"):
                active.append({"user_a": int(uid), "user_b": info["partner"]})
        return active

    # --- الإحصائيات (حل مشكلة خطأ تحميل الإحصائيات) ---
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
            "female_users": sum(1 for v in u.values() if v.get("gender") == "أنثى"),
            "total_points": sum(v.get("points", 0) for v in u.values()),
            "total_chats": data["stats"].get("total_chats", 0)
        }

    # --- المتصدرين ---
    def get_leaderboard(self, limit=10):
        data, _ = self._get_raw_data()
        users = list(data.get("users", {}).values())
        return sorted(users, key=lambda x: x.get('points', 0), reverse=True)[:limit]

    # --- البحث عن شريك ---
    def find_available_partner(self, exclude_id):
        data, _ = self._get_raw_data()
        for uid, info in data["users"].items():
            if uid != str(exclude_id) and info.get("status") == "searching":
                return info
        return None

    def find_available_partner_by_gender(self, exclude_id, gender_pref):
        data, _ = self._get_raw_data()
        for uid, info in data["users"].items():
            if uid != str(exclude_id) and info.get("status") == "searching" and info.get("gender") == gender_pref:
                return info
        return None

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
 
