import logging
import sqlite3
import os
import time
from datetime import datetime, timedelta
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    LabeledPrice
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
import asyncio

# 🔧 إعدادات التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ⚙️ إعدادات التطبيق
class StarsConfig:
    BOT_TOKEN = "8221859242:AAFKHjJfujko6gDNXtysdk982wq0MLUo4H4"  # ضع توكن البوت هنا
    
    # مسار قاعدة البيانات
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "databases")
    DB_NAME = os.path.join(DB_PATH, "telegram_stars_payments.db")
    
    # TEST provider token للنجوم (XTR)
    PROVIDER_TOKEN = "284685063:TEST:YzZmZjMxNWE5ZGIz"  # TEST token للنجوم
    
    ADMIN_IDS = [7834574830]  # ضع أيادات المشرفين هنا
    
    # أسعار VIP بالنجوم
    VIP_STARS_PACKAGES = {
        1: {
            'name': '💎 VIP ليوم واحد',
            'description': 'اشتراك VIP لمدة 24 ساعة',
            'price': 10,  # 10 نجوم
            'duration_days': 1,
            'price_usd': 1.00
        },
        2: {
            'name': '💎 VIP ليومين',
            'description': 'اشتراك VIP لمدة يومين',
            'price': 15,  # 15 نجمة
            'duration_days': 2,
            'price_usd': 1.50
        },
        3: {
            'name': '💎 VIP لـ 3 أيام',
            'description': 'اشتراك VIP لمدة 3 أيام',
            'price': 25,  # 25 نجمة
            'duration_days': 3,
            'price_usd': 2.50
        },
        7: {
            'name': '💎 VIP لأسبوع',
            'description': 'اشتراك VIP لمدة أسبوع',
            'price': 40,  # 40 نجمة
            'duration_days': 7,
            'price_usd': 4.00
        },
        14: {
            'name': '💎 VIP لأسبوعين',
            'description': 'اشتراك VIP لمدة أسبوعين',
            'price': 70,  # 70 نجمة
            'duration_days': 14,
            'price_usd': 7.00
        },
        30: {
            'name': '💎 VIP لشهر',
            'description': 'اشتراك VIP لمدة شهر',
            'price': 100,  # 100 نجمة
            'duration_days': 30,
            'price_usd': 10.00
        }
    }
    
    # حزم النجوم للشراء
    STARS_PACKAGES = {
        10: {
            'name': '10 ⭐',
            'description': '10 نجوم تلجرام',
            'price_usd': 1.00,
            'stars': 10
        },
        50: {
            'name': '50 ⭐',
            'description': '50 نجمة تلجرام',
            'price_usd': 4.50,
            'stars': 50
        },
        100: {
            'name': '100 ⭐',
            'description': '100 نجمة تلجرام',
            'price_usd': 8.00,
            'stars': 100
        },
        500: {
            'name': '500 ⭐',
            'description': '500 نجمة تلجرام',
            'price_usd': 35.00,
            'stars': 500
        },
        1000: {
            'name': '1000 ⭐',
            'description': '1000 نجمة تلجرام',
            'price_usd': 65.00,
            'stars': 1000
        }
    }

# 🗄️ نظام قاعدة البيانات للنجوم
class StarsDatabase:
    def __init__(self, db_name):
        self.db_name = db_name
        self.db_path = os.path.dirname(db_name)
        self.ensure_db_directory()
        self.init_database()
    
    def ensure_db_directory(self):
        """التأكد من وجود مجلد قواعد البيانات"""
        try:
            if not os.path.exists(self.db_path):
                os.makedirs(self.db_path)
                logger.info(f"✅ تم إنشاء مجلد قواعد البيانات: {self.db_path}")
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء مجلد قواعد البيانات: {e}")
            self.db_name = "telegram_stars_payments.db"
    
    def init_database(self):
        """تهيئة قاعدة البيانات والجداول"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # جدول مستخدمي النجوم
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stars_users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    stars_balance INTEGER DEFAULT 0,
                    total_stars_earned INTEGER DEFAULT 0,
                    total_stars_spent INTEGER DEFAULT 0,
                    vip_until TEXT,
                    vip_purchases INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # جدول معاملات النجوم
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stars_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    transaction_type TEXT,
                    stars_amount INTEGER,
                    description TEXT,
                    status TEXT DEFAULT 'completed',
                    invoice_payload TEXT,
                    telegram_payment_charge_id TEXT,
                    provider_payment_charge_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES stars_users (user_id)
                )
            ''')
            
            # جدول مشتريات VIP بالنجوم
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vip_stars_purchases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    vip_days INTEGER,
                    stars_paid INTEGER,
                    purchase_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    expiration_date TEXT,
                    FOREIGN KEY (user_id) REFERENCES stars_users (user_id)
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info(f"✅ تم تهيئة قاعدة البيانات: {self.db_name}")
            
        except Exception as e:
            logger.error(f"❌ خطأ في تهيئة قاعدة البيانات: {e}")
            raise
    
    def get_connection(self):
        """الحصول على اتصال بقاعدة البيانات"""
        try:
            conn = sqlite3.connect(self.db_name)
            return conn
        except Exception as e:
            logger.error(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
            raise
    
    def get_user(self, user_id):
        """الحصول على بيانات مستخدم النجوم"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM stars_users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()
            conn.close()
            
            if user:
                return {
                    'user_id': user[0],
                    'username': user[1],
                    'first_name': user[2],
                    'last_name': user[3],
                    'stars_balance': user[4],
                    'total_stars_earned': user[5],
                    'total_stars_spent': user[6],
                    'vip_until': user[7],
                    'vip_purchases': user[8],
                    'created_at': user[9],
                    'updated_at': user[10]
                }
            return None
            
        except Exception as e:
            logger.error(f"❌ خطأ في الحصول على بيانات المستخدم: {e}")
            return None
    
    def create_user(self, user_data):
        """إنشاء مستخدم جديد في نظام النجوم"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO stars_users 
                (user_id, username, first_name, last_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
            ''', (
                user_data['user_id'],
                user_data['username'],
                user_data['first_name'],
                user_data['last_name']
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"✅ تم إنشاء/تحديث مستخدم النجوم: {user_data['user_id']}")
            
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء مستخدم النجوم: {e}")
    
    def update_stars_balance(self, user_id, amount):
        """تحديث رصيد النجوم للمستخدم"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if amount > 0:
                cursor.execute('''
                    UPDATE stars_users SET 
                    stars_balance = stars_balance + ?, 
                    total_stars_earned = total_stars_earned + ?,
                    updated_at = datetime('now') 
                    WHERE user_id = ?
                ''', (amount, amount, user_id))
            else:
                cursor.execute('''
                    UPDATE stars_users SET 
                    stars_balance = stars_balance + ?, 
                    total_stars_spent = total_stars_spent + ABS(?),
                    updated_at = datetime('now') 
                    WHERE user_id = ?
                ''', (amount, amount, user_id))
            
            conn.commit()
            conn.close()
            logger.info(f"✅ تم تحديث رصيد النجوم للمستخدم {user_id}: {amount}")
            
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث رصيد النجوم: {e}")
    
    def create_stars_transaction(self, transaction_data):
        """إنشاء معاملة نجوم جديدة"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO stars_transactions 
                (user_id, transaction_type, stars_amount, description, status, invoice_payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (
                transaction_data['user_id'],
                transaction_data['transaction_type'],
                transaction_data['stars_amount'],
                transaction_data['description'],
                transaction_data['status'],
                transaction_data.get('invoice_payload', '')
            ))
            
            transaction_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"✅ تم إنشاء معاملة نجوم: {transaction_id}")
            return transaction_id
            
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء معاملة النجوم: {e}")
            return None
    
    def update_stars_transaction(self, invoice_payload, update_data):
        """تحديث حالة معاملة النجوم"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE stars_transactions SET 
                status = ?, 
                telegram_payment_charge_id = ?,
                provider_payment_charge_id = ?
                WHERE invoice_payload = ?
            ''', (
                update_data['status'],
                update_data.get('telegram_payment_charge_id'),
                update_data.get('provider_payment_charge_id'),
                invoice_payload
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"✅ تم تحديث معاملة النجوم: {invoice_payload}")
            
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث معاملة النجوم: {e}")
    
    def add_vip_purchase(self, user_id, vip_days, stars_paid):
        """إضافة شراء VIP بالنجوم"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            expires_at = (datetime.now() + timedelta(days=vip_days)).strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
                INSERT INTO vip_stars_purchases 
                (user_id, vip_days, stars_paid, purchase_date, expiration_date)
                VALUES (?, ?, ?, datetime('now'), ?)
            ''', (user_id, vip_days, stars_paid, expires_at))
            
            # تحديث حالة VIP للمستخدم
            cursor.execute('''
                UPDATE stars_users SET 
                vip_until = ?,
                vip_purchases = vip_purchases + 1,
                updated_at = datetime('now')
                WHERE user_id = ?
            ''', (expires_at, user_id))
            
            conn.commit()
            conn.close()
            logger.info(f"✅ تم تسجيل شراء VIP بالنجوم للمستخدم {user_id}: {vip_days} يوم")
            
        except Exception as e:
            logger.error(f"❌ خطأ في تسجيل شراء VIP: {e}")
    
    def get_stars_transactions(self, user_id, limit=20):
        """الحصول على سجل معاملات النجوم للمستخدم"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT transaction_type, stars_amount, description, status, created_at 
                FROM stars_transactions 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (user_id, limit))
            
            transactions = cursor.fetchall()
            conn.close()
            
            return [{
                'transaction_type': t[0],
                'stars_amount': t[1],
                'description': t[2],
                'status': t[3],
                'created_at': t[4]
            } for t in transactions]
            
        except Exception as e:
            logger.error(f"❌ خطأ في الحصول على سجل المعاملات: {e}")
            return []
    
    def get_vip_status(self, user_id):
        """الحصول على حالة VIP للمستخدم"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT vip_until FROM stars_users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0]:
                vip_until = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
                now = datetime.now()
                
                if vip_until > now:
                    days_left = (vip_until - now).days
                    return {'is_vip': True, 'days_left': days_left, 'until': vip_until}
            
            return {'is_vip': False, 'days_left': 0, 'until': None}
            
        except Exception as e:
            logger.error(f"❌ خطأ في الحصول على حالة VIP: {e}")
            return {'is_vip': False, 'days_left': 0, 'until': None}

# ⌨️ لوحات المفاتيح للنجوم
class StarsKeyboards:
    @staticmethod
    def stars_main_menu():
        """القائمة الرئيسية للنجوم"""
        keyboard = [
            [InlineKeyboardButton("⭐ شراء النجوم", callback_data="buy_stars")],
            [InlineKeyboardButton("💎 شراء VIP", callback_data="buy_vip_stars")],
            [InlineKeyboardButton("💰 رصيد النجوم", callback_data="stars_balance")],
            [InlineKeyboardButton("📊 سجل المعاملات", callback_data="stars_history")],
            [InlineKeyboardButton("🎁 هدايا النجوم", callback_data="stars_gifts")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def stars_packages_menu():
        """قائمة باقات النجوم"""
        keyboard = []
        for package_id, package in StarsConfig.STARS_PACKAGES.items():
            button_text = f"{package['name']} - ${package['price_usd']}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"stars_package_{package_id}")])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="stars_menu")])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def vip_stars_packages_menu():
        """قائمة باقات VIP بالنجوم"""
        keyboard = []
        for days, package in StarsConfig.VIP_STARS_PACKAGES.items():
            button_text = f"{package['name']} - {package['price']} ⭐"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"vip_stars_{days}")])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="stars_menu")])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def confirm_stars_purchase(package_id, is_vip=False):
        """تأكيد شراء النجوم أو VIP"""
        if is_vip:
            package = StarsConfig.VIP_STARS_PACKAGES[package_id]
            callback_data = f"confirm_vip_stars_{package_id}"
        else:
            package = StarsConfig.STARS_PACKAGES[package_id]
            callback_data = f"confirm_stars_{package_id}"
        
        keyboard = [
            [InlineKeyboardButton(f"✅ تأكيد الشراء", callback_data=callback_data)],
            [InlineKeyboardButton("❌ إلغاء", callback_data="stars_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def after_payment():
        """بعد الدفع الناجح"""
        keyboard = [
            [InlineKeyboardButton("🔄 العودة للرئيسية", callback_data="main_menu")],
            [InlineKeyboardButton("⭐ شراء المزيد", callback_data="buy_stars")]
        ]
        return InlineKeyboardMarkup(keyboard)

# 🤖 نظام الدفع بالنجوم الرئيسي
class TelegramStarsPaymentSystem:
    def __init__(self, main_db):
        self.config = StarsConfig()
        self.stars_db = StarsDatabase(self.config.DB_NAME)
        self.main_db = main_db  # قاعدة البيانات الرئيسية للبوت
        
        logger.info("✅ تم تهيئة نظام النجوم")
    
    async def handle_stars_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة استدعاءات نظام النجوم"""
        try:
            query = update.callback_query
            await query.answer()
            
            data = query.data
            user = query.from_user
            
            logger.info(f"استدعاء النجوم: {data} من المستخدم {user.id}")
            
            if data == "stars_menu":
                await self.show_stars_menu(query)
            elif data == "buy_stars":
                await self.show_stars_packages(query)
            elif data == "buy_vip_stars":
                await self.show_vip_stars_packages(query)
            elif data == "stars_balance":
                await self.show_stars_balance(query)
            elif data == "stars_history":
                await self.show_stars_history(query)
            elif data == "stars_gifts":
                await self.show_stars_gifts_menu(query)
            elif data.startswith("stars_package_"):
                package_id = int(data.replace("stars_package_", ""))
                await self.show_stars_package_details(query, package_id)
            elif data.startswith("vip_stars_"):
                days = int(data.replace("vip_stars_", ""))
                await self.show_vip_stars_details(query, days)
            elif data.startswith("confirm_stars_"):
                package_id = int(data.replace("confirm_stars_", ""))
                await self.initiate_stars_purchase(query, context, package_id)
            elif data.startswith("confirm_vip_stars_"):
                days = int(data.replace("confirm_vip_stars_", ""))
                await self.initiate_vip_stars_purchase(query, context, days)
            elif data == "check_payment":
                await query.edit_message_text(
                    "✅ **تم استلام طلب التحقق من الدفع.**\n\n"
                    "💡 **إذا لم تصل الفاتورة، جرب الخروج والعودة للبوت.**"
                )
                
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة استدعاء النجوم: {e}")
            if update.callback_query:
                await update.callback_query.edit_message_text("❌ حدث خطأ في النظام. يرجى المحاولة لاحقاً.")
    
    async def show_stars_menu(self, query):
        """عرض قائمة النجوم"""
        await query.edit_message_text(
            "⭐ **نظام النجوم**\n\n"
            "💫 **النجوم هي العملة الرسمية في تليجرام**\n"
            "يمكنك استخدامها لشراء:\n"
            "• اشتراكات VIP 👑\n"
            "• هدايا للأصدقاء 🎁\n"
            "• مزايا خاصة في البوت ✨\n\n"
            "👇 **اختر من القائمة:**",
            reply_markup=StarsKeyboards.stars_main_menu()
        )
    
    async def show_stars_menu_via_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض قائمة النجوم عبر رسالة"""
        await update.message.reply_text(
            "⭐ **نظام النجوم**\n\n"
            "💫 **النجوم هي العملة الرسمية في تليجرام**\n"
            "يمكنك استخدامها لشراء:\n"
            "• اشتراكات VIP 👑\n"
            "• هدايا للأصدقاء 🎁\n"
            "• مزايا خاصة في البوت ✨\n\n"
            "👇 **اختر من القائمة:**",
            reply_markup=StarsKeyboards.stars_main_menu()
        )
    
    async def show_stars_packages(self, query):
        """عرض باقات النجوم"""
        await query.edit_message_text(
            "🛒 **باقات النجوم المتاحة:**\n\n"
            "💎 **اختر الباقة المناسبة لك:**",
            reply_markup=StarsKeyboards.stars_packages_menu()
        )
    
    async def show_vip_stars_packages(self, query):
        """عرض باقات VIP بالنجوم"""
        await query.edit_message_text(
            "👑 **اشتراكات VIP بالنجوم:**\n\n"
            "✨ **مزايا VIP:**\n"
            "• أولوية في البحث عن الشركاء\n"
            "• مكافآت مضاعفة\n"
            "• إمكانية البحث حسب الجنس مجاناً\n"
            "• لقب VIP مميز\n\n"
            "👇 **اختر الباقة المناسبة:**",
            reply_markup=StarsKeyboards.vip_stars_packages_menu()
        )
    
    async def show_stars_balance(self, query):
        """عرض رصيد النجوم"""
        user = query.from_user
        
        # الحصول من قاعدة النجوم
        stars_user = self.stars_db.get_user(user.id)
        if not stars_user:
            stars_user = {'stars_balance': 0, 'total_stars_earned': 0, 'total_stars_spent': 0}
        
        # الحصول من قاعدة البيانات الرئيسية
        main_user = self.main_db.get_user(user.id)
        main_stars = main_user.get('stars_balance', 0) if main_user else 0
        
        # استخدام القيمة الأكبر
        stars_balance = max(stars_user['stars_balance'], main_stars)
        
        vip_status = self.stars_db.get_vip_status(user.id)
        
        balance_text = f"""
💰 **رصيد النجوم:** {stars_balance} ⭐

📊 **إحصائيات النجوم:**
• النجوم المكتسبة: {stars_user.get('total_stars_earned', 0)} ⭐
• النجوم المنفقة: {stars_user.get('total_stars_spent', 0)} ⭐

👑 **حالة VIP:** {'✅ نشط' if vip_status['is_vip'] else '❌ غير نشط'}
"""
        
        if vip_status['is_vip']:
            balance_text += f"⏰ **الأيام المتبقية:** {vip_status['days_left']} يوم\n"
        
        await query.edit_message_text(
            balance_text,
            reply_markup=StarsKeyboards.stars_main_menu()
        )
    
    async def show_stars_history(self, query):
        """عرض سجل معاملات النجوم"""
        user = query.from_user
        transactions = self.stars_db.get_stars_transactions(user.id)
        
        if not transactions:
            await query.edit_message_text("📭 **لا توجد معاملات نجوم سابقة.**", 
                                        reply_markup=StarsKeyboards.stars_main_menu())
            return
        
        history_text = "📊 **سجل معاملات النجوم:**\n\n"
        for trans in transactions[:10]:
            status_icon = "✅" if trans['status'] == "completed" else "⏳" if trans['status'] == "pending" else "❌"
            sign = "+" if trans['stars_amount'] > 0 else ""
            history_text += f"{status_icon} {trans['description']}\n   {sign}{trans['stars_amount']} ⭐ - {trans['created_at'][:16]}\n\n"
        
        await query.edit_message_text(
            history_text,
            reply_markup=StarsKeyboards.stars_main_menu()
        )
    
    async def show_stars_gifts_menu(self, query):
        """عرض قائمة هدايا النجوم"""
        await query.edit_message_text(
            "🎁 **هدايا النجوم**\n\n"
            "💝 **يمكنك إرسال النجوم كهدايا للأصدقاء**\n\n"
            "⚠️ **سيتم تفعيل هذه الميزة قريباً...**",
            reply_markup=StarsKeyboards.stars_main_menu()
        )
    
    async def show_stars_package_details(self, query, package_id):
        """عرض تفاصيل باقة النجوم"""
        if package_id not in StarsConfig.STARS_PACKAGES:
            await query.edit_message_text("❌ الباقة غير متاحة.")
            return
        
        package = StarsConfig.STARS_PACKAGES[package_id]
        
        details_text = f"""
{package['name']}

📝 **الوصف:** {package['description']}
💰 **السعر:** ${package['price_usd']}
⭐ **عدد النجوم:** {package['stars']} ⭐

💫 **الدفع باستخدام نجوم تليجرام**

✅ هل تريد المتابعة مع الشراء؟
"""
        
        await query.edit_message_text(
            details_text,
            reply_markup=StarsKeyboards.confirm_stars_purchase(package_id, is_vip=False)
        )
    
    async def show_vip_stars_details(self, query, days):
        """عرض تفاصيل باقة VIP بالنجوم"""
        if days not in StarsConfig.VIP_STARS_PACKAGES:
            await query.edit_message_text("❌ الباقة غير متاحة.")
            return
        
        package = StarsConfig.VIP_STARS_PACKAGES[days]
        
        details_text = f"""
{package['name']}

📝 **الوصف:** {package['description']}
💰 **السعر:** {package['price']} ⭐ (${package['price_usd']})
⏰ **المدة:** {package['duration_days']} يوم

✨ **مزايا VIP:**
• أولوية في البحث عن الشركاء
• مكافآت مضاعفة
• لقب VIP مميز
• إمكانية البحث حسب الجنس مجاناً

✅ هل تريد المتابعة مع الشراء؟
"""
        
        await query.edit_message_text(
            details_text,
            reply_markup=StarsKeyboards.confirm_stars_purchase(days, is_vip=True)
        )
    
    async def initiate_stars_purchase(self, query, context: ContextTypes.DEFAULT_TYPE, package_id):
        """بدء عملية شراء النجوم"""
        try:
            if package_id not in StarsConfig.STARS_PACKAGES:
                await query.edit_message_text("❌ الباقة غير متاحة.")
                return
            
            package = StarsConfig.STARS_PACKAGES[package_id]
            user = query.from_user
            
            # إنشاء معاملة pending
            invoice_payload = f"stars_{package_id}_{user.id}_{int(time.time())}"
            
            transaction_data = {
                'user_id': user.id,
                'transaction_type': 'stars_purchase',
                'stars_amount': package['stars'],
                'description': f'شراء {package["name"]}',
                'status': 'pending',
                'invoice_payload': invoice_payload
            }
            
            self.stars_db.create_stars_transaction(transaction_data)
            
            # إنشاء فاتورة الدفع بالنجوم
            # استخدام عملة XTR للنجوم (النجوم التليجرامية)
            prices = [LabeledPrice(package['name'], int(package['price_usd'] * 100))]  # تحويل الدولارات إلى سنتات
            
            logger.info(f"إرسال فاتورة للباقة {package_id}: ${package['price_usd']}")
            
            await context.bot.send_invoice(
                chat_id=query.message.chat_id,
                title=f"شراء {package['name']}",
                description=package['description'],
                payload=invoice_payload,
                # استخدام الـ provider_token للسلع الرقمية
                provider_token=self.config.PROVIDER_TOKEN,
                currency="XTR",  # العملة هي XTR للنجوم
                prices=prices,
                start_parameter=str(package_id),
                need_name=False,
                need_phone_number=False,
                need_email=False,
                need_shipping_address=False,
                is_flexible=False,
                max_tip_amount=0
            )
            
            await query.edit_message_text(
                f"📨 **تم إرسال فاتورة الدفع**\n\n"
                f"💫 **الباقة:** {package['name']}\n"
                f"💰 **المبلغ:** ${package['price_usd']}\n"
                f"⭐ **ستحصل على:** {package['stars']} نجمة\n\n"
                f"يرجى اكمال عملية الدفع في الفاتورة المرسلة.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ تم الدفع", callback_data="check_payment")]
                ])
            )
            
        except Exception as e:
            logger.error(f"❌ خطأ في بدء شراء النجوم: {e}")
            await query.edit_message_text(
                f"❌ حدث خطأ في إنشاء فاتورة الدفع.\n\n"
                f"💡 **التفاصيل:** {str(e)}\n\n"
                f"يرجى المحاولة لاحقاً أو التواصل مع الدعم."
            )
    
    async def initiate_vip_stars_purchase(self, query, context: ContextTypes.DEFAULT_TYPE, days):
        """بدء عملية شراء VIP بالنجوم"""
        try:
            if days not in StarsConfig.VIP_STARS_PACKAGES:
                await query.edit_message_text("❌ الباقة غير متاحة.")
                return
            
            package = StarsConfig.VIP_STARS_PACKAGES[days]
            user = query.from_user
            
            # التحقق من رصيد النجوم
            stars_balance = self.stars_db.get_user(user.id)
            if not stars_balance or stars_balance['stars_balance'] < package['price']:
                await query.edit_message_text(
                    f"❌ **رصيد النجوم غير كافي.**\n\n"
                    f"💰 **السعر:** {package['price']} ⭐\n"
                    f"💎 **رصيدك:** {stars_balance['stars_balance'] if stars_balance else 0} ⭐\n\n"
                    f"يرجى شراء النجوم أولاً.",
                    reply_markup=StarsKeyboards.stars_main_menu()
                )
                return
            
            # خصم النجوم
            self.stars_db.update_stars_balance(user.id, -package['price'])
            
            # تفعيل VIP
            self.stars_db.add_vip_purchase(user.id, days, package['price'])
            
            # تحديث قاعدة البيانات الرئيسية
            self.main_db.purchase_vip_with_stars(user.id, days, package['price'])
            
            # تسجيل المعاملة
            transaction_data = {
                'user_id': user.id,
                'transaction_type': 'vip_purchase',
                'stars_amount': -package['price'],
                'description': f'شراء {package["name"]}',
                'status': 'completed'
            }
            self.stars_db.create_stars_transaction(transaction_data)
            
            success_text = f"""
🎉 **تم شراء VIP بنجاح!** ⭐

✅ **الباقة:** {package['name']}
💰 **السعر:** {package['price']} نجمة
⏰ **المدة:** {package['duration_days']} يوم

✨ **تم تفعيل جميع مزايا VIP لك!**

💫 **مزاياك الجديدة:**
• لقب VIP مميز 👑
• أولوية في البحث
• مكافآت مضاعفة
• خصائص حصرية
"""
            
            await query.edit_message_text(
                success_text,
                reply_markup=StarsKeyboards.after_payment()
            )
            
            logger.info(f"✅ تم شراء VIP بالنجوم للمستخدم {user.id}: {days} يوم")
            
        except Exception as e:
            logger.error(f"❌ خطأ في شراء VIP بالنجوم: {e}")
            await query.edit_message_text(
                f"❌ حدث خطأ في عملية الشراء.\n"
                f"💡 **التفاصيل:** {str(e)}\n"
                f"يرجى المحاولة لاحقاً أو التواصل مع الدعم."
            )
    
    async def pre_checkout_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """التحقق قبل الدفع"""
        query = update.pre_checkout_query
        try:
            await query.answer(ok=True)
            logger.info(f"✅ تم التحقق من الدفع: {query.invoice_payload}")
        except Exception as e:
            logger.error(f"❌ خطأ في التحقق من الدفع: {e}")
            await query.answer(ok=False, error_message="فشل في التحقق من الدفع")
    
    async def successful_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الدفع الناجح"""
        try:
            payment = update.message.successful_payment
            user = update.effective_user
            
            logger.info(f"✅ تم استلام دفعة ناجحة: {payment.invoice_payload}")
            
            # تحديث حالة المعاملة
            update_data = {
                'status': 'completed',
                'telegram_payment_charge_id': payment.telegram_payment_charge_id,
                'provider_payment_charge_id': payment.provider_payment_charge_id
            }
            
            self.stars_db.update_stars_transaction(payment.invoice_payload, update_data)
            
            # استخراج نوع الباقة من payload
            payload_parts = payment.invoice_payload.split('_')
            
            if payload_parts[0] == 'stars' and len(payload_parts) >= 2:
                package_id = int(payload_parts[1])
                
                if package_id in StarsConfig.STARS_PACKAGES:
                    package = StarsConfig.STARS_PACKAGES[package_id]
                    
                    # إضافة النجوم للمستخدم
                    self.stars_db.update_stars_balance(user.id, package['stars'])
                    
                    # تحديث قاعدة البيانات الرئيسية
                    self.main_db.add_stars(user.id, package['stars'])
                    
                    success_text = f"""
🎉 **تم الدفع بنجاح!** ⭐

✅ **الباقة:** {package['name']}
💰 **المبلغ:** ${package['price_usd']}
⭐ **تم إضافة:** {package['stars']} نجمة
🆔 **معرف المعاملة:** {payment.telegram_payment_charge_id}

💫 **يمكنك الآن استخدام النجوم لشراء:**
• اشتراكات VIP 👑
• هدايا للأصدقاء 🎁
• مزايا خاصة ✨

🚀 **استمتع بتجربتك الجديدة!**
"""
                    
                    await update.message.reply_text(
                        success_text,
                        reply_markup=StarsKeyboards.after_payment()
                    )
                    
                    logger.info(f"✅ تم إضافة {package['stars']} نجمة للمستخدم {user.id}")
                else:
                    await update.message.reply_text(
                        "❌ حدث خطأ في تفعيل الباقة. يرجى التواصل مع الدعم.\n\n"
                        f"معرف المعاملة: {payment.telegram_payment_charge_id}"
                    )
            else:
                await update.message.reply_text(
                    "❌ حدث خطأ في معالجة الدفع. يرجى التواصل مع الدعم.\n\n"
                    f"معرف المعاملة: {payment.telegram_payment_charge_id}"
                )
                
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة الدفع الناجح: {e}")
            await update.message.reply_text(
                f"❌ حدث خطأ في معالجة الدفع. يرجى التواصل مع الدعم.\n\n"
                f"💡 **التفاصيل:** {str(e)}"
            )
    
    def get_stars_system(self):
        """الحصول على نظام النجوم للإضافة للبوت الرئيسي"""
        return {
            'keyboards': StarsKeyboards,
            'config': StarsConfig,
            'show_stars_menu': self.show_stars_menu,
            'show_stars_balance': self.show_stars_balance
        }