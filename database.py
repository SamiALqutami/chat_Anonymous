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
        except: 
            return {"users": {}, "stats": {}}, None

    def _save(self, data, sha, msg="Database Update"):
        try:
            content = base64.b64encode(json.dumps(data, indent=4, ensure_ascii=False).encode('utf-8')).decode('utf-8')
            res = requests.put(self.url, headers=self.headers, json={"message": msg, "content": content, "sha": sha}, timeout=15)
            return res.status_code in [200, 201]
        except: return False

    # --- إدارة المستخدمين الشاملة ---
    def create_user(self, info):
        data, sha = self._get_raw_data()
        uid = str(info.get("user_id"))
        if uid not in data["users"]:
            ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            # إضافة كافة الحقول من قاعدتك الأصلية
            data["users"][uid] = {
                "user_id": int(uid), "username": info.get("username", ""),
                "first_name": info.get("first_name", ""), "last_name": info.get("last_name", ""),
                "points": 50, "stars_balance": 0, "status": "idle", "gender": "غير محدد",
                "age": 0, "country": "غير محدد", "bio": "", "language": "عربي",
                "vip_until": 0, "vip_level": 0, "vip_title": "", "total_chats": 0,
                "join_ts": int(time.time()), "referral_code": ref_code, "last_reward_ts": 0,
                "partner": None, "rating_sum": 0, "total_ratings": 0, "level": 1
            }
            self._save(data, sha, f"Create User {uid}")
        return data["users"][uid]

    def get_user(self, user_id):
        data, _ = self._get_raw_data()
        user = data["users"].get(str(user_id))
        return user

    def update_user_profile(self, user_id, updates):
        data, sha = self._get_raw_data()
        uid = str(user_id)
        if uid in data["users"]:
            data["users"][uid].update(updates)
            self._save(data, sha, f"Update Profile {uid}")

    def set_user_status(self, user_id, status, partner=None):
        data, sha = self._get_raw_data()
        uid = str(user_id)
        if uid in data["users"]:
            data["users"][uid]["status"] = status
            data["users"][uid]["partner"] = partner
            if status == "chatting":
                data["users"][uid]["total_chats"] += 1
            self._save(data, sha)

    # --- نظام النقاط والنجوم ---
    def add_points(self, user_id, points):
        data, sha = self._get_raw_data()
        uid = str(user_id)
        if uid in data["users"]:
            data["users"][uid]["points"] += points
            # تحديث المستوى تلقائياً (كما في قاعدتك القديمة)
            data["users"][uid]["level"] = (data["users"][uid]["points"] // 100) + 1
            self._save(data, sha)

    def consume_points(self, user_id, points):
        data, sha = self._get_raw_data()
        uid = str(user_id)
        if uid in data["users"] and data["users"][uid]["points"] >= points:
            data["users"][uid]["points"] -= points
            self._save(data, sha)
            return True
        return False

    # --- المتصدرين (يدعم النقاط والنجوم) ---
    def get_leaderboard(self, limit=10):
        data, _ = self._get_raw_data()
        users = list(data.get("users", {}).values())
        return sorted(users, key=lambda x: x.get('points', 0), reverse=True)[:limit]

    def get_stars_leaderboard(self, limit=10):
        data, _ = self._get_raw_data()
        users = list(data.get("users", {}).values())
        return sorted(users, key=lambda x: x.get('stars_balance', 0), reverse=True)[:limit]

    # --- البحث عن شريك ---
    def find_available_partner(self, exclude_id):
        data, _ = self._get_raw_data()
        search_pool = [u for k, u in data["users"].items() if k != str(exclude_id) and u.get("status") == "searching"]
        return random.choice(search_pool) if search_pool else None

    def find_available_partner_by_gender(self, exclude_id, gender_pref):
        data, _ = self._get_raw_data()
        search_pool = [u for k, u in data["users"].items() if k != str(exclude_id) and u.get("status") == "searching" and u.get("gender") == gender_pref]
        return random.choice(search_pool) if search_pool else None

    # --- وظائف إضافية لتوافق البوت الرئيسي ---
    def list_active_conversations(self):
        data, _ = self._get_raw_data()
        return [{"user_a": int(k), "user_b": v["partner"]} for k, v in data["users"].items() if v.get("status") == "chatting" and v.get("partner")]

    def get_stats(self):
        data, _ = self._get_raw_data()
        u = data.get("users", {})
        return {
            "total_users": len(u),
            "active_users": sum(1 for v in u.values() if v.get("status") == "chatting"),
            "searching_users": sum(1 for v in u.values() if v.get("status") == "searching"),
            "total_points": sum(v.get("points", 0) for v in u.values()),
            "male_users": sum(1 for v in u.values() if v.get("gender") == "ذكر"),
            "female_users": sum(1 for v in u.values() if v.get("gender") == "أنثى")
        }

    def optimize_database(self): return True
 
