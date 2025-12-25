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
        """جلب البيانات والـ SHA (الرقم التسلسلي للملف)"""
        response = requests.get(self.url, headers=self.headers)
        if response.status_code == 200:
            content = response.json()
            decoded_data = base64.b64decode(content['content']).decode('utf-8')
            return json.loads(decoded_data), content['sha']
        return {"users": {}}, None

    def get_user(self, user_id):
        """جلب بيانات مستخدم"""
        data, _ = self._get_raw_data()
        return data.get("users", {}).get(str(user_id))

    def update_user_points(self, user_id, new_points):
        """مثال لتحديث النقاط فقط"""
        all_data, sha = self._get_raw_data()
        if str(user_id) in all_data["users"]:
            all_data["users"][str(user_id)]["points"] = new_points
            
            # تحويل البيانات إلى نص ثم تشفيرها للحفظ
            updated_json = json.dumps(all_data, indent=4, ensure_ascii=False)
            encoded_content = base64.b64encode(updated_json.encode('utf-8')).decode('utf-8')
            
            payload = {
                "message": f"تحديث نقاط المستخدم {user_id}",
                "content": encoded_content,
                "sha": sha
            }
            res = requests.put(self.url, headers=self.headers, json=payload)
            return res.status_code in [200, 201]
        return False
