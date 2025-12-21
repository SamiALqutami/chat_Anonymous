import sqlite3
import time
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import os
import logging

logger = logging.getLogger(__name__)

def now_ts():
    return int(time.time())

class Database:
    def __init__(self, path="bot_data.sqlite"):
        self.path = path
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        self._migrate_tables()

    def _migrate_tables(self):
        """إضافة الأعمدة المفقودة إذا كانت غير موجودة"""
        c = self.conn.cursor()
        
        # الحصول على أعمدة الجدول
        c.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in c.fetchall()]
        
        # إضافة الأعمدة المفقودة
        missing_columns = {
            'gender_changed': 'INTEGER DEFAULT 0',
            'vip_days': 'INTEGER DEFAULT 0',
            'vip_purchases': 'INTEGER DEFAULT 0',
            'total_chats': 'INTEGER DEFAULT 0',
            'bio': 'TEXT DEFAULT \'\'',
            'total_ratings': 'INTEGER DEFAULT 0',
            'rating_sum': 'INTEGER DEFAULT 0',
            'stars_balance': 'INTEGER DEFAULT 0',  # رصيد النجوم
            'stars_purchases': 'INTEGER DEFAULT 0',  # عدد شراءات النجوم
            'premium_until': 'INTEGER DEFAULT 0',  # تاريخ انتهاء البريميوم
            'vip_level': 'INTEGER DEFAULT 0',  # مستوى VIP
            'vip_title': 'TEXT DEFAULT \'\'',  # لقب VIP
            'last_reward_ts': 'INTEGER DEFAULT 0',  # آخر وقت حصل فيه على مكافأة
            'referral_code': 'TEXT',  # كود الإحالة الخاص
            'total_stars_earned': 'INTEGER DEFAULT 0',  # إجمالي النجوم المكتسبة
            'total_stars_spent': 'INTEGER DEFAULT 0'  # إجمالي النجوم المنفقة
        }
        
        for column, column_type in missing_columns.items():
            if column not in columns:
                try:
                    c.execute(f"ALTER TABLE users ADD COLUMN {column} {column_type}")
                    logger.info(f"تمت إضافة العمود: {column}")
                except sqlite3.Error as e:
                    logger.error(f"خطأ في إضافة العمود {column}: {e}")
        
        # جدول معاملات النجوم
        try:
            c.execute('''
                CREATE TABLE IF NOT EXISTS stars_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    transaction_type TEXT,
                    stars_amount INTEGER,
                    description TEXT,
                    status TEXT DEFAULT 'completed',
                    created_at INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
        except sqlite3.Error as e:
            logger.error(f"خطأ في إنشاء جدول النجوم: {e}")
        
        # جدول مشتريات VIP بالنجوم
        try:
            c.execute('''
                CREATE TABLE IF NOT EXISTS vip_stars_purchases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    vip_days INTEGER,
                    stars_paid INTEGER,
                    purchase_date INTEGER,
                    expiration_date INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
        except sqlite3.Error as e:
            logger.error(f"خطأ في إنشاء جدول مشتريات VIP: {e}")
        
        self.conn.commit()

    def _create_tables(self):
        c = self.conn.cursor()
        
        # المستخدمين
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            join_ts INTEGER,
            country TEXT DEFAULT 'غير محدد',
            gender TEXT,
            age INTEGER,
            bio TEXT DEFAULT '',
            language TEXT DEFAULT 'عربي',
            points INTEGER DEFAULT 0,
            vip_until INTEGER DEFAULT 0,
            vip_days INTEGER DEFAULT 0,
            vip_purchases INTEGER DEFAULT 0,
            chats_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'idle',
            last_hourly_ts INTEGER DEFAULT 0,
            banned_until INTEGER DEFAULT 0,
            referrals INTEGER DEFAULT 0,
            invited_by INTEGER,
            level INTEGER DEFAULT 1,
            total_chats INTEGER DEFAULT 0,
            gender_changed INTEGER DEFAULT 0,
            total_ratings INTEGER DEFAULT 0,
            rating_sum INTEGER DEFAULT 0,
            stars_balance INTEGER DEFAULT 0,
            stars_purchases INTEGER DEFAULT 0,
            premium_until INTEGER DEFAULT 0,
            vip_level INTEGER DEFAULT 0,
            vip_title TEXT DEFAULT '',
            last_reward_ts INTEGER DEFAULT 0,
            referral_code TEXT,
            total_stars_earned INTEGER DEFAULT 0,
            total_stars_spent INTEGER DEFAULT 0
        )
        """)
        
        # التقارير
        c.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter_id INTEGER,
            target_id INTEGER,
            reason TEXT,
            ts INTEGER,
            handled INTEGER DEFAULT 0
        )
        """)
        
        # الإحالات
        c.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            new_user_id INTEGER,
            ts INTEGER
        )
        """)
        
        # المحادثات
        c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_a INTEGER,
            user_b INTEGER,
            start_ts INTEGER,
            last_ts INTEGER,
            active INTEGER DEFAULT 1,
            rating_a INTEGER DEFAULT 0,
            rating_b INTEGER DEFAULT 0,
            messages_count INTEGER DEFAULT 0
        )
        """)
        
        # الرسائل
        c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conv_id INTEGER,
            sender_id INTEGER,
            text TEXT,
            ts INTEGER,
            message_type TEXT DEFAULT 'text'
        )
        """)
        
        # الأصدقاء
        c.execute("""
        CREATE TABLE IF NOT EXISTS friends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            friend_id INTEGER,
            friend_name TEXT,
            ts INTEGER,
            status TEXT DEFAULT 'active'
        )
        """)
        
        # الألعاب
        c.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_type TEXT,
            user_id INTEGER,
            opponent_id INTEGER,
            result TEXT,
            points_won INTEGER,
            stars_won INTEGER DEFAULT 0,
            ts INTEGER,
            duration INTEGER DEFAULT 0
        )
        """)
        
        # الهدايا
        c.execute("""
        CREATE TABLE IF NOT EXISTS gifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            receiver_id INTEGER,
            points INTEGER,
            stars INTEGER DEFAULT 0,
            message TEXT,
            ts INTEGER,
            status TEXT DEFAULT 'sent'
        )
        """)
        
        # مشتريات VIP
        c.execute("""
        CREATE TABLE IF NOT EXISTS vip_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            days INTEGER,
            points_paid INTEGER,
            stars_paid INTEGER DEFAULT 0,
            ts INTEGER,
            purchase_type TEXT DEFAULT 'points'
        )
        """)
        
        # طلبات اللعب
        c.execute("""
        CREATE TABLE IF NOT EXISTS game_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            receiver_id INTEGER,
            game_type TEXT,
            status TEXT DEFAULT 'pending',
            ts INTEGER,
            expires_at INTEGER
        )
        """)
        
        self.conn.commit()

    # --- المستخدمين ---
    def create_user(self, info:Dict[str,Any]):
        c = self.conn.cursor()
        
        # إنشاء كود إحالة فريد
        import random
        import string
        referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        c.execute("""
            INSERT OR IGNORE INTO users 
            (user_id, username, first_name, last_name, join_ts, language, level, referral_code) 
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            info.get("user_id"), 
            info.get("username",""), 
            info.get("first_name",""), 
            info.get("last_name",""), 
            info.get("join_ts", now_ts()),
            info.get("language", "عربي"),
            1,  # level default
            referral_code
        ))
        self.conn.commit()

    def get_user(self, user_id:int) -> Optional[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        r = c.fetchone()
        return dict(r) if r else None

    def update_user_profile(self, user_id:int, updates:Dict[str,Any]):
        c = self.conn.cursor()
        fields = []
        values = []
        for field, value in updates.items():
            if field in ['country', 'gender', 'age', 'bio', 'language', 'gender_changed', 
                        'vip_days', 'vip_purchases', 'total_chats', 'total_ratings', 'rating_sum',
                        'stars_balance', 'stars_purchases', 'premium_until', 'vip_level', 'vip_title',
                        'last_reward_ts', 'referral_code', 'total_stars_earned', 'total_stars_spent']:
                fields.append(f"{field}=?")
                values.append(value)
        if fields:
            values.append(user_id)
            c.execute(f"UPDATE users SET {','.join(fields)} WHERE user_id=?", values)
            self.conn.commit()

    def set_user_status(self, user_id:int, status:str):
        c = self.conn.cursor()
        c.execute("UPDATE users SET status=? WHERE user_id=?", (status, user_id))
        self.conn.commit()

    def list_all_users(self, limit:int=1000) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM users ORDER BY join_ts DESC LIMIT ?", (limit,))
        return [dict(r) for r in c.fetchall()]

    # --- النقاط ---
    def add_points(self, user_id:int, points:int):
        c = self.conn.cursor()
        c.execute("UPDATE users SET points = points + ? WHERE user_id=?", (points, user_id))
        
        # تحديث المستوى
        c.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
        result = c.fetchone()
        if result:
            current_points = result["points"]
            new_level = (current_points // 100) + 1
            c.execute("UPDATE users SET level=? WHERE user_id=?", (new_level, user_id))
        
        self.conn.commit()

    def consume_points(self, user_id:int, points:int) -> bool:
        c = self.conn.cursor()
        c.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
        r = c.fetchone()
        if not r:
            return False
        if r["points"] < points:
            return False
        c.execute("UPDATE users SET points = points - ? WHERE user_id=?", (points, user_id))
        self.conn.commit()
        return True

    def grant_points_direct(self, user_id:int, points:int):
        self.add_points(user_id, points)

    # --- النجوم ---
    def add_stars(self, user_id:int, stars:int):
        c = self.conn.cursor()
        c.execute("UPDATE users SET stars_balance = stars_balance + ?, total_stars_earned = total_stars_earned + ? WHERE user_id=?", 
                 (stars, stars, user_id))
        self.conn.commit()

    def consume_stars(self, user_id:int, stars:int) -> bool:
        c = self.conn.cursor()
        c.execute("SELECT stars_balance FROM users WHERE user_id=?", (user_id,))
        r = c.fetchone()
        if not r:
            return False
        if r["stars_balance"] < stars:
            return False
        c.execute("UPDATE users SET stars_balance = stars_balance - ?, total_stars_spent = total_stars_spent + ? WHERE user_id=?", 
                 (stars, stars, user_id))
        self.conn.commit()
        return True

    def get_stars_balance(self, user_id:int) -> int:
        c = self.conn.cursor()
        c.execute("SELECT stars_balance FROM users WHERE user_id=?", (user_id,))
        r = c.fetchone()
        return r["stars_balance"] if r else 0

    def add_stars_transaction(self, user_id:int, transaction_type:str, stars_amount:int, description:str):
        c = self.conn.cursor()
        c.execute("""
            INSERT INTO stars_transactions 
            (user_id, transaction_type, stars_amount, description, created_at)
            VALUES (?,?,?,?,?)
        """, (user_id, transaction_type, stars_amount, description, now_ts()))
        self.conn.commit()

    def get_stars_transactions(self, user_id:int, limit:int=20) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM stars_transactions WHERE user_id=? ORDER BY created_at DESC LIMIT ?", 
                 (user_id, limit))
        return [dict(r) for r in c.fetchall()]

    # --- التقارير ---
    def add_report(self, reporter_id:int, target_id:int, reason:str):
        c = self.conn.cursor()
        c.execute("INSERT INTO reports (reporter_id, target_id, reason, ts) VALUES (?,?,?,?)", 
                 (reporter_id, target_id, reason, now_ts()))
        self.conn.commit()

    def get_reports(self, limit:int=100) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM reports ORDER BY ts DESC LIMIT ?", (limit,))
        return [dict(r) for r in c.fetchall()]

    # --- الإحالات ---
    def add_referral(self, referrer_id:int, new_user_id:int):
        c = self.conn.cursor()
        c.execute("INSERT INTO referrals (referrer_id, new_user_id, ts) VALUES (?,?,?)", 
                 (referrer_id, new_user_id, now_ts()))
        c.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id=?", (referrer_id,))
        c.execute("UPDATE users SET invited_by = ? WHERE user_id=?", (referrer_id, new_user_id))
        self.conn.commit()

    # --- المطابقة المحسنة ---
    def find_available_partner(self, exclude_user_id:int) -> Optional[Dict]:
        c = self.conn.cursor()
        c.execute("""
            SELECT * FROM users 
            WHERE status='idle' 
            AND user_id != ? 
            AND (banned_until IS NULL OR banned_until < ?)
            AND user_id NOT IN (
                SELECT user_a FROM conversations WHERE active=1 
                UNION 
                SELECT user_b FROM conversations WHERE active=1
            )
            ORDER BY RANDOM() 
            LIMIT 1
        """, (exclude_user_id, now_ts()))
        r = c.fetchone()
        return dict(r) if r else None

    def find_available_partner_by_gender(self, exclude_user_id:int, gender_pref:str) -> Optional[Dict]:
        c = self.conn.cursor()
        c.execute("""
            SELECT * FROM users 
            WHERE status='idle' 
            AND gender=? 
            AND user_id != ? 
            AND (banned_until IS NULL OR banned_until < ?)
            AND user_id NOT IN (
                SELECT user_a FROM conversations WHERE active=1 
                UNION 
                SELECT user_b FROM conversations WHERE active=1
            )
            ORDER BY RANDOM() 
            LIMIT 1
        """, (gender_pref, exclude_user_id, now_ts()))
        r = c.fetchone()
        return dict(r) if r else None

    def find_available_gamer(self, exclude_user_id:int, game_type:str) -> Optional[Dict]:
        c = self.conn.cursor()
        c.execute("""
            SELECT * FROM users 
            WHERE status='idle' 
            AND user_id != ? 
            AND (banned_until IS NULL OR banned_until < ?)
            AND user_id NOT IN (
                SELECT user_a FROM conversations WHERE active=1 
                UNION 
                SELECT user_b FROM conversations WHERE active=1
            )
            ORDER BY RANDOM() 
            LIMIT 1
        """, (exclude_user_id, now_ts()))
        r = c.fetchone()
        return dict(r) if r else None

    # --- المحادثات والرسائل ---
    def create_conversation(self, user_a:int, user_b:int) -> int:
        c = self.conn.cursor()
        ts = now_ts()
        c.execute("INSERT INTO conversations (user_a,user_b,start_ts,last_ts,active) VALUES (?,?,?,?,1)", 
                 (user_a,user_b,ts,ts))
        
        # تحديث إحصائيات المحادثات
        c.execute("UPDATE users SET chats_count = chats_count + 1, total_chats = total_chats + 1 WHERE user_id IN (?,?)", 
                 (user_a, user_b))
        
        self.conn.commit()
        return c.lastrowid

    def close_conversation(self, conv_id:int):
        c = self.conn.cursor()
        ts = now_ts()
        c.execute("UPDATE conversations SET active=0,last_ts=? WHERE id=?", (ts, conv_id))
        self.conn.commit()

    def touch_conversation(self, conv_id:int):
        c = self.conn.cursor()
        ts = now_ts()
        c.execute("UPDATE conversations SET last_ts=? WHERE id=?", (ts, conv_id))
        self.conn.commit()

    def add_message(self, conv_id:int, sender_id:int, text:str, message_type:str="text"):
        c = self.conn.cursor()
        ts = now_ts()
        c.execute("INSERT INTO messages (conv_id,sender_id,text,ts,message_type) VALUES (?,?,?,?,?)", 
                 (conv_id,sender_id,text,ts,message_type))
        # تحديث عدد الرسائل في المحادثة
        c.execute("UPDATE conversations SET messages_count = messages_count + 1 WHERE id=?", (conv_id,))
        self.conn.commit()

    def list_active_conversations(self) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM conversations WHERE active=1")
        return [dict(r) for r in c.fetchall()]

    def get_conversation(self, conv_id:int) -> Optional[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM conversations WHERE id=?", (conv_id,))
        r = c.fetchone()
        return dict(r) if r else None

    def get_messages(self, conv_id:int, limit:int=50) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM messages WHERE conv_id=? ORDER BY id DESC LIMIT ?", (conv_id, limit))
        rows = c.fetchall()
        return [dict(r) for r in rows][::-1]

    def get_partner_info(self, user_id:int, conv_id:int) -> Optional[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT user_a, user_b FROM conversations WHERE id=?", (conv_id,))
        conv = c.fetchone()
        if conv:
            partner_id = conv['user_b'] if conv['user_a'] == user_id else conv['user_a']
            return self.get_user(partner_id)
        return None

    # --- لوحة المتصدرين ---
    def get_leaderboard(self, limit:int=10) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM users ORDER BY points DESC LIMIT ?", (limit,))
        return [dict(r) for r in c.fetchall()]

    def get_stars_leaderboard(self, limit:int=10) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM users ORDER BY stars_balance DESC LIMIT ?", (limit,))
        return [dict(r) for r in c.fetchall()]

    def get_user_rank(self, user_id:int) -> int:
        c = self.conn.cursor()
        c.execute("""
            SELECT COUNT(*) + 1 as rank FROM users 
            WHERE points > (SELECT points FROM users WHERE user_id=?)
        """, (user_id,))
        r = c.fetchone()
        return r["rank"] if r else 1

    def get_user_stars_rank(self, user_id:int) -> int:
        c = self.conn.cursor()
        c.execute("""
            SELECT COUNT(*) + 1 as rank FROM users 
            WHERE stars_balance > (SELECT stars_balance FROM users WHERE user_id=?)
        """, (user_id,))
        r = c.fetchone()
        return r["rank"] if r else 1

    # --- الأصدقاء ---
    def add_friend(self, user_id:int, friend_id:int, friend_name:str):
        c = self.conn.cursor()
        # التحقق من عدم وجود الصديق مسبقاً
        c.execute("SELECT * FROM friends WHERE user_id=? AND friend_id=?", (user_id, friend_id))
        if c.fetchone():
            return False
            
        c.execute("INSERT INTO friends (user_id, friend_id, friend_name, ts) VALUES (?,?,?,?)",
                 (user_id, friend_id, friend_name, now_ts()))
        self.conn.commit()
        return True

    def get_user_friends(self, user_id:int) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM friends WHERE user_id=?", (user_id,))
        return [dict(r) for r in c.fetchall()]

    def remove_friend(self, user_id:int, friend_id:int):
        c = self.conn.cursor()
        c.execute("DELETE FROM friends WHERE user_id=? AND friend_id=?", (user_id, friend_id))
        self.conn.commit()

    # --- الألعاب ---
    def create_game(self, game_type:str, user_id:int, opponent_id:int=0) -> int:
        c = self.conn.cursor()
        c.execute("INSERT INTO games (game_type, user_id, opponent_id, ts) VALUES (?,?,?,?)",
                 (game_type, user_id, opponent_id, now_ts()))
        self.conn.commit()
        return c.lastrowid

    def update_game_result(self, game_id:int, result:str, points_won:int, stars_won:int=0):
        c = self.conn.cursor()
        c.execute("UPDATE games SET result=?, points_won=?, stars_won=? WHERE id=?", 
                 (result, points_won, stars_won, game_id))
        self.conn.commit()

    def get_user_games(self, user_id:int, limit:int=20) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM games WHERE user_id=? OR opponent_id=? ORDER BY ts DESC LIMIT ?", 
                 (user_id, user_id, limit))
        return [dict(r) for r in c.fetchall()]

    # --- طلبات اللعب ---
    def create_game_request(self, sender_id:int, receiver_id:int, game_type:str) -> int:
        c = self.conn.cursor()
        expires_at = now_ts() + 300  # 5 دقائق
        c.execute("INSERT INTO game_requests (sender_id, receiver_id, game_type, ts, expires_at) VALUES (?,?,?,?,?)",
                 (sender_id, receiver_id, game_type, now_ts(), expires_at))
        self.conn.commit()
        return c.lastrowid

    def get_pending_game_requests(self, receiver_id:int) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM game_requests WHERE receiver_id=? AND status='pending' AND expires_at > ?",
                 (receiver_id, now_ts()))
        return [dict(r) for r in c.fetchall()]

    def update_game_request(self, request_id:int, status:str):
        c = self.conn.cursor()
        c.execute("UPDATE game_requests SET status=? WHERE id=?", (status, request_id))
        self.conn.commit()

    # --- الهدايا ---
    def send_gift(self, sender_id:int, receiver_id:int, points:int, message:str="") -> bool:
        c = self.conn.cursor()
        # خصم النقاط من المرسل
        if not self.consume_points(sender_id, points):
            return False
            
        # إضافة النقاط للمستلم
        self.add_points(receiver_id, points)
        
        # تسجيل العملية
        c.execute("INSERT INTO gifts (sender_id, receiver_id, points, message, ts) VALUES (?,?,?,?,?)",
                 (sender_id, receiver_id, points, message, now_ts()))
        self.conn.commit()
        return True

    def send_stars_gift(self, sender_id:int, receiver_id:int, stars:int, message:str="") -> bool:
        c = self.conn.cursor()
        # خصم النجوم من المرسل
        if not self.consume_stars(sender_id, stars):
            return False
            
        # إضافة النجوم للمستلم
        self.add_stars(receiver_id, stars)
        
        # تسجيل العملية
        c.execute("INSERT INTO gifts (sender_id, receiver_id, stars, message, ts) VALUES (?,?,?,?,?)",
                 (sender_id, receiver_id, stars, message, now_ts()))
        self.conn.commit()
        return True

    def get_user_gifts(self, user_id:int) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("""
            SELECT * FROM gifts 
            WHERE receiver_id=? OR sender_id=?
            ORDER BY ts DESC LIMIT 20
        """, (user_id, user_id))
        return [dict(r) for r in c.fetchall()]

    # --- VIP ---
    def set_vip(self, user_id:int, days:int, use_stars:bool=False, stars_paid:int=0):
        c = self.conn.cursor()
        until_ts = now_ts() + (days * 86400)
        
        # تحديث حالة VIP
        c.execute("UPDATE users SET vip_until=?, vip_days=vip_days+?, vip_purchases=vip_purchases+1 WHERE user_id=?", 
                 (until_ts, days, user_id))
        
        # تحديد مستوى VIP بناءً على عدد الأيام
        vip_level = 1
        if days >= 30:
            vip_level = 3
        elif days >= 7:
            vip_level = 2
        
        c.execute("UPDATE users SET vip_level=?, vip_title=? WHERE user_id=?", 
                 (vip_level, f'VIP {vip_level}', user_id))
        
        # تسجيل عملية الشراء
        purchase_type = 'stars' if use_stars else 'points'
        points_paid = 0 if use_stars else self._get_vip_points_price(days)
        
        c.execute("INSERT INTO vip_purchases (user_id, days, points_paid, stars_paid, ts, purchase_type) VALUES (?,?,?,?,?,?)",
                 (user_id, days, points_paid, stars_paid, now_ts(), purchase_type))
        
        # إذا كانت بالنجوم، تسجيل في جدول النجوم
        if use_stars:
            c.execute("INSERT INTO vip_stars_purchases (user_id, vip_days, stars_paid, purchase_date, expiration_date) VALUES (?,?,?,?,?)",
                     (user_id, days, stars_paid, now_ts(), until_ts))
        
        self.conn.commit()

    def _get_vip_points_price(self, days:int) -> int:
        prices = {
            1: 20,
            2: 30,
            3: 40,
            7: 70,
            30: 100
        }
        return prices.get(days, days * 20)

    def purchase_vip(self, user_id:int, days:int, points_cost:int) -> bool:
        if not self.consume_points(user_id, points_cost):
            return False
            
        self.set_vip(user_id, days)
        return True

    def purchase_vip_with_stars(self, user_id:int, days:int, stars_cost:int) -> bool:
        if not self.consume_stars(user_id, stars_cost):
            return False
            
        self.set_vip(user_id, days, use_stars=True, stars_paid=stars_cost)
        return True

    def get_vip_status(self, user_id:int) -> Dict[str, Any]:
        user = self.get_user(user_id)
        if not user:
            return {"is_vip": False, "days_left": 0, "vip_level": 0, "vip_title": ""}
        
        vip_until = user.get('vip_until', 0)
        now = now_ts()
        
        if vip_until > now:
            days_left = (vip_until - now) // 86400
            return {
                "is_vip": True, 
                "days_left": days_left, 
                "until_ts": vip_until,
                "vip_level": user.get('vip_level', 1),
                "vip_title": user.get('vip_title', 'VIP 1')
            }
        else:
            return {
                "is_vip": False, 
                "days_left": 0,
                "vip_level": 0,
                "vip_title": ""
            }

    # --- المشرفين ---
    def ban_user(self, user_id:int, until_ts:int):
        c = self.conn.cursor()
        c.execute("UPDATE users SET banned_until=? WHERE user_id=?", (until_ts, user_id))
        self.conn.commit()

    def unban_user(self, user_id:int):
        c = self.conn.cursor()
        c.execute("UPDATE users SET banned_until=0 WHERE user_id=?", (user_id,))
        self.conn.commit()

    def get_user_by_id(self, user_id:int) -> Optional[Dict]:
        return self.get_user(user_id)

    # --- المكافآت اليومية ---
    def get_last_hourly(self, user_id:int) -> int:
        c = self.conn.cursor()
        c.execute("SELECT last_hourly_ts FROM users WHERE user_id=?", (user_id,))
        r = c.fetchone()
        return r["last_hourly_ts"] or 0 if r else 0

    def set_last_hourly(self, user_id:int, ts:int):
        c = self.conn.cursor()
        c.execute("UPDATE users SET last_hourly_ts=? WHERE user_id=?", (ts, user_id))
        self.conn.commit()

    def get_last_reward(self, user_id:int) -> int:
        c = self.conn.cursor()
        c.execute("SELECT last_reward_ts FROM users WHERE user_id=?", (user_id,))
        r = c.fetchone()
        return r["last_reward_ts"] or 0 if r else 0

    def set_last_reward(self, user_id:int, ts:int):
        c = self.conn.cursor()
        c.execute("UPDATE users SET last_reward_ts=? WHERE user_id=?", (ts, user_id))
        self.conn.commit()

    # --- الإحصائيات المحسنة ---
    def get_stats(self):
        c = self.conn.cursor()
        
        # إجمالي المستخدمين
        c.execute("SELECT COUNT(*) as total_users FROM users")
        total_users = c.fetchone()["total_users"]
        
        # المستخدمين النشطين
        c.execute("SELECT COUNT(*) as active_users FROM users WHERE status='chatting'")
        active_users = c.fetchone()["active_users"]
        
        # المستخدمين في البحث
        c.execute("SELECT COUNT(*) as searching_users FROM users WHERE status='searching'")
        searching_users = c.fetchone()["searching_users"]
        
        # المحادثات النشطة
        c.execute("SELECT COUNT(*) as active_chats FROM conversations WHERE active=1")
        active_chats = c.fetchone()["active_chats"]
        
        # إجمالي النقاط
        c.execute("SELECT SUM(points) as total_points FROM users")
        total_points_result = c.fetchone()
        total_points = total_points_result["total_points"] or 0 if total_points_result else 0
        
        # إجمالي النجوم
        c.execute("SELECT SUM(stars_balance) as total_stars FROM users")
        total_stars_result = c.fetchone()
        total_stars = total_stars_result["total_stars"] or 0 if total_stars_result else 0
        
        # عدد الذكور
        c.execute("SELECT COUNT(*) as male_users FROM users WHERE gender='ذكر'")
        male_users = c.fetchone()["male_users"]
        
        # عدد الإناث
        c.execute("SELECT COUNT(*) as female_users FROM users WHERE gender='أنثى'")
        female_users = c.fetchone()["female_users"]
        
        # عدد المحادثات اليوم
        today_ts = now_ts() - 86400
        c.execute("SELECT COUNT(*) as today_chats FROM conversations WHERE start_ts > ?", (today_ts,))
        today_chats = c.fetchone()["today_chats"]
        
        # عدد المستخدمين الجدد اليوم
        c.execute("SELECT COUNT(*) as new_users_today FROM users WHERE join_ts > ?", (today_ts,))
        new_users_today = c.fetchone()["new_users_today"]
        
        # عدد مستخدمين VIP
        c.execute("SELECT COUNT(*) as vip_users FROM users WHERE vip_until > ?", (now_ts(),))
        vip_users = c.fetchone()["vip_users"]
        
        # عدد الألعاب اليوم
        c.execute("SELECT COUNT(*) as today_games FROM games WHERE ts > ?", (today_ts,))
        today_games = c.fetchone()["today_games"]
        
        # إجمالي الرسائل
        c.execute("SELECT COUNT(*) as total_messages FROM messages")
        total_messages = c.fetchone()["total_messages"]
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "searching_users": searching_users,
            "active_chats": active_chats,
            "total_points": total_points,
            "total_stars": total_stars,
            "male_users": male_users,
            "female_users": female_users,
            "today_chats": today_chats,
            "new_users_today": new_users_today,
            "vip_users": vip_users,
            "today_games": today_games,
            "total_messages": total_messages
        }

    # --- التقييمات ---
    def add_rating(self, user_id: int, rating: int):
        c = self.conn.cursor()
        c.execute("UPDATE users SET total_ratings = total_ratings + 1, rating_sum = rating_sum + ? WHERE user_id=?", 
                 (rating, user_id))
        self.conn.commit()

    def get_average_rating(self, user_id: int) -> float:
        c = self.conn.cursor()
        c.execute("SELECT total_ratings, rating_sum FROM users WHERE user_id=?", (user_id,))
        r = c.fetchone()
        if r and r["total_ratings"] > 0:
            return r["rating_sum"] / r["total_ratings"]
        return 0.0

    def update_conversation_rating(self, conv_id: int, user_id: int, rating: int):
        c = self.conn.cursor()
        conv = self.get_conversation(conv_id)
        if conv:
            if conv['user_a'] == user_id:
                c.execute("UPDATE conversations SET rating_a=? WHERE id=?", (rating, conv_id))
            else:
                c.execute("UPDATE conversations SET rating_b=? WHERE id=?", (rating, conv_id))
            self.conn.commit()

    # --- VIP الإحصائيات ---
    def get_vip_stats(self):
        c = self.conn.cursor()
        c.execute("SELECT SUM(vip_days) as total_vip_days FROM users")
        total_vip_days = c.fetchone()["total_vip_days"] or 0
        
        c.execute("SELECT SUM(vip_purchases) as total_vip_purchases FROM users")
        total_vip_purchases = c.fetchone()["total_vip_purchases"] or 0
        
        c.execute("SELECT SUM(stars_paid) as total_stars_spent FROM vip_purchases WHERE purchase_type='stars'")
        total_stars_spent = c.fetchone()["total_stars_spent"] or 0
        
        return {
            "total_vip_days": total_vip_days,
            "total_vip_purchases": total_vip_purchases,
            "total_stars_spent": total_stars_spent
        }

    # --- إدارة الأخطاء ---
    def backup_database(self):
        """إنشاء نسخة احتياطية من قاعدة البيانات"""
        try:
            backup_path = f"{self.path}.backup"
            import shutil
            shutil.copy2(self.path, backup_path)
            logger.info(f"تم إنشاء نسخة احتياطية: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"خطأ في النسخ الاحتياطي: {e}")
            return False

    def optimize_database(self):
        """تحسين قاعدة البيانات"""
        try:
            c = self.conn.cursor()
            c.execute("VACUUM")
            c.execute("ANALYZE")
            self.conn.commit()
            logger.info("تم تحسين قاعدة البيانات")
            return True
        except Exception as e:
            logger.error(f"خطأ في تحسين قاعدة البيانات: {e}")
            return False