import os
import time
import random
import asyncio
import logging
import sys
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand, LabeledPrice
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler, PreCheckoutQueryHandler
from telegram.error import TelegramError

# --- استيراد الملفات المحدثة (تأكد من وجودها في المستودع) ---
from database import Database
from games import GameManager, create_xo_keyboard, calculate_game_rewards
from config import get_config
from stars_payment import TelegramStarsPaymentSystem, StarsKeyboards

# --- إعداد السجلات (Logging) ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- تهيئة قاعدة البيانات السحابية (MongoDB) ---
try:
    # سيقوم الكلاس في database.py بالتحقق من MONGO_URI
    db = Database()
    logger.info("✅ تم ربط عقل البوت بقاعدة البيانات السحابية بنجاح.")
except Exception as e:
    logger.error(f"❌ فشل بدء تشغيل البوت: {e}")
    sys.exit(1) # إيقاف البوت فوراً لأن القاعدة الخارجية غير متصلة

# --- الحصول على الإعدادات ---
config = get_config()

# ملاحظة: تم حذف DB_PATH تماماً لأننا نستخدم MongoDB الآن
TOKEN = os.getenv('BOT_TOKEN') or config['bot_token']
OWNER_ID = config['owner_id']
ADMIN_IDS = config['admin_ids']
MANDATORY_CHANNEL = config['mandatory_channel']
MONITOR_CHANNEL = config['monitor_channel']
DATA_CHANNEL = config['data_channel']

# إعدادات المكافآت والأسعار (تُجلب من السحاب أو Config)
REWARD_POINTS = config.get('reward_points', 10)
REWARD_COOLDOWN = config.get('reward_cooldown', 86400)
GENDER_SEARCH_COST = config.get('gender_search_cost', 5)
GENDER_CHANGE_COST = config.get('gender_change_cost', 50)
FILTERED_WORDS = config.get('filtered_words', [])

# --- تهيئة الأنظمة الفرعية ---
game_manager = GameManager(db)
payment_system = TelegramStarsPaymentSystem(db)

# ----------------------------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# تهيئة قواعد البيانات والنظم
db = Database()
game_manager = GameManager(db)
stars_system = None  # سيتم تهيئتها بعد بناء التطبيق

# Utilities
def now_ts() -> int:
    return int(time.time())

def readable(ts: Optional[int]) -> str:
    if not ts:
        return "—"
    return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S UTC")

def format_time_left(seconds: int) -> str:
    """تنسيق الوقت المتبقي"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    time_str = ""
    if hours > 0:
        time_str += f"{hours} ساعة "
    if minutes > 0:
        time_str += f"{minutes} دقيقة "
    if secs > 0 or (hours == 0 and minutes == 0):
        time_str += f"{secs} ثانية"
    
    return time_str.strip()

def require_user_in_db(user_id:int, tg_user:dict):
    u = db.get_user(user_id)
    if u:
        return u
    
    db.create_user({
        "user_id": user_id,
        "username": tg_user.get("username") or "",
        "first_name": tg_user.get("first_name") or "",
        "last_name": tg_user.get("last_name") or "",
        "join_ts": now_ts()
    })
    
    return db.get_user(user_id)

def safe_get_user(user_id: int):
    """الحصول على بيانات المستخدم بشكل آمن مع معالجة الأخطاء"""
    try:
        return db.get_user(user_id) or {}
    except Exception as e:
        logger.error(f"خطأ في الحصول على بيانات المستخدم {user_id}: {e}")
        return {'user_id': user_id, 'first_name': 'مستخدم', 'points': 0}

# نظام المطابقة المبسط في الذاكرة
waiting_users = set()  # مستخدمين ينتظرون شريك
active_chats = {}      # محادثات نشطة {user_id: partner_id}

# Keyboards
def main_reply_keyboard(is_admin=False):
    kb = [
        ["🚀 بحث عشوائي", "⚤ بحث بالجنس"],
        ["🎩 حسابي", "💰 كسب النقاط"],
        ["🎮 الألعاب", "📊 إحصائيات"],
        ["👑 VIP", "⭐ النجوم", "🏆 المتصدرين"],
        ["🎯 المكافأة"]
    ]
    if is_admin:
        kb.append(["🛠️ لوحة المشرف"])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def stats_keyboard():
    return ReplyKeyboardMarkup([
        ["👥 المستخدمين", "🎯 النشاط"],
        ["💰 النقاط", "⭐ النجوم"],
        ["⬅️ الرئيسية"]
    ], resize_keyboard=True)

def profile_keyboard():
    return ReplyKeyboardMarkup([
        ["📄 ملفي الشخصي", "⚙️ إعدادات الملف"],
        ["⬅️ الرئيسية"]
    ], resize_keyboard=True)

def settings_keyboard(user_id: int):
    user = safe_get_user(user_id)
    gender_changed = user.get('gender_changed', 0)
    
    kb = [
        ["👫 الجنس", "🎂 العمر"],
        ["📍 البلد", "⬅️ الرئيسية"]
    ]
    
    # إضافة تكلفة تغيير الجنس
    if gender_changed:
        kb[0][0] = "👫 الجنس (10 💰)"
    
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def gender_select_keyboard():
    return ReplyKeyboardMarkup([
        ["👦 ذكر", "👧 أنثى"],
        ["⬅️ رجوع"]
    ], resize_keyboard=True)

def country_select_keyboard():
    return ReplyKeyboardMarkup([
        ["🇸🇦 السعودية", "🇦🇪 الإمارات", "🇶🇦 قطر"],
        ["🇰🇼 الكويت", "🇴🇲 عمان", "🇧🇭 البحرين"],
        ["🇪🇬 مصر", "🇯🇴 الأردن", "🇱🇧 لبنان"],
        ["🇮🇶 العراق", "🇸🇾 سوريا", "🇾🇪 اليمن"],
        ["🇩🇿 الجزائر", "🇲🇦 المغرب", "🇹🇳 تونس"],
        ["🇱🇾 ليبيا", "🇸🇩 السودان", "🇸🇴 الصومال"],
        ["🇯🇪 جيبوتي", "🇲🇷 موريتانيا", "🇵🇸 فلسطين"],
        ["🌍 دولة أخرى", "⬅️ رجوع"]
    ], resize_keyboard=True)

def games_keyboard():
    return ReplyKeyboardMarkup([
        [],
        ["🔢 تخمين الرقم", "🎰 لعبة الحظ"],
        ["⬅️ الرئيسية"]
    ], resize_keyboard=True)

def earn_points_keyboard():
    return ReplyKeyboardMarkup([
        ["📤 مشاركة الروابط", "👥 إحالة أصدقاء"],
        ["🎁 هدايا الأصدقاء", "⬅️ الرئيسية"]
    ], resize_keyboard=True)

def friends_keyboard():
    return ReplyKeyboardMarkup([
        ["⭐ إضافة صديق", "📋 قائمة الأصدقاء"],
        ["💌 إرسال نقاط", "🎁 إرسال نجوم"],
        ["⬅️ الرئيسية"]
    ], resize_keyboard=True)

def vip_keyboard():
    return ReplyKeyboardMarkup([
        ["👑 اشتراك VIP", "⭐ VIP بالنجوم"],
        ["📞 تواصل مع المشرف", "⬅️ الرئيسية"]
    ], resize_keyboard=True)

def chat_control_keyboard():
    return ReplyKeyboardMarkup([
        ["⏹️ إنهاء المحادثة", "⭐ إضافة صديق"],
        ["🚫 حظر المستخدم", "⭐ التقييم"],
        ["⬅️ الرئيسية"]
    ], resize_keyboard=True)

def rating_keyboard():
    return ReplyKeyboardMarkup([
        ["⭐ 1", "⭐⭐ 2", "⭐⭐⭐ 3"],
        ["⭐⭐⭐⭐ 4", "⭐⭐⭐⭐⭐ 5", "⬅️ تخطي"]
    ], resize_keyboard=True)

def search_cancel_keyboard():
    return ReplyKeyboardMarkup([
        ["⏹️ إيقاف البحث", "⬅️ الرئيسية"]
    ], resize_keyboard=True)

def admin_keyboard():
    return ReplyKeyboardMarkup([
        ["📊 الإحصائيات الكاملة", "👥 المستخدمين المحظورين"],
        ["💰 توزيع النقاط", "⭐ توزيع النجوم"],
        ["📢 بث سريع", "🔄 تحديث النظام"],
        ["⬅️ الرئيسية"]
    ], resize_keyboard=True)

# Global states
MATCHING: Dict[int, Dict[str,Any]] = {}
GENDER_CONFIRM: Dict[int,str] = {}
USER_STATES: Dict[int, str] = {}
ACTIVE_SEARCHES: Dict[int, asyncio.Task] = {}
GAME_SEARCHES: Dict[int, asyncio.Task] = {}

# VIP prices بالنقاط (أسعار مضاعفة)
VIP_POINTS_PRICES = {
    1: 100,   # يوم واحد
    2: 180,   # يومين (خصم 10%)
    3: 255,   # 3 أيام (خصم 15%)
    7: 560,   # أسبوع (خصم 20%)
    14: 980,  # أسبوعين (خصم 30%)
    30: 2100  # شهر (خصم 30%)
}

# Inline keyboards
def vip_purchase_keyboard():
    kb = []
    for days, price in VIP_POINTS_PRICES.items():
        if days == 1:
            text = f"يوم واحد - {price} 🌶️"
        elif days == 2:
            text = f"يومين - {price} 🌶️"
        elif days == 3:
            text = f"3 أيام - {price} 🌶️"
        elif days == 7:
            text = f"أسبوع - {price} 🌶️"
        elif days == 14:
            text = f"أسبوعين - {price} 🌶️"
        elif days == 30:
            text = f"شهر - {price} 🌶️"
        kb.append([InlineKeyboardButton(text, callback_data=f"vip_buy_{days}")])
    
    kb.append([InlineKeyboardButton("⭐ VIP بالنجوم", callback_data="vip_stars_menu")])
    kb.append([InlineKeyboardButton("⬅️ رجوع", callback_data="vip_back")])
    return InlineKeyboardMarkup(kb)

# Monitoring helpers
async def send_to_monitor(context: ContextTypes.DEFAULT_TYPE, text: str):
    try:
        await context.bot.send_message(chat_id=MONITOR_CHANNEL, text=text)
    except Exception as e:
        logger.debug("Monitor send failed: %s", e)

# --- فحص الاشتراك الإجباري ---
async def check_channel_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not MANDATORY_CHANNEL or MANDATORY_CHANNEL == "@yourchannel":
        return True
        
    user = update.effective_user
    try:
        member = await context.bot.get_chat_member(MANDATORY_CHANNEL.replace("@", ""), user.id)
        if member.status in ['left', 'kicked']:
            return False
    except Exception as e:
        logger.error(f"Error checking channel subscription: {e}")
        return True
        
    return True

async def must_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚠️ لتستطيع استخدام البوت يجب الاشتراك في القناة أولاً:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 اضغط للاشتراك", url=f"https://t.me/{MANDATORY_CHANNEL.replace('@','')}")],
            [InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_subscription")]
        ])
    )

# --- الأساسيات ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    # معالجة الإحالات
    args = context.args
    if args:
        try:
            ref_id = int(args[0])
            if ref_id != user.id:
                db.add_referral(referrer_id=ref_id, new_user_id=user.id)
                db.add_points(ref_id, 20)
                db.add_points(user.id, 10)  # مكافأة للمستخدم الجديد
        except Exception:
            pass
    
    require_user_in_db(user.id, user.to_dict() if user else {})
    
    kb = main_reply_keyboard(is_admin=(user.id in ADMIN_IDS))
    
    welcome_text = f"""
✨ **مرحباً {user.first_name}!** 

🎯 **بوت الدردشة والتعارف المتقدم**

🚀 **المميزات الجديدة:**
• نظام نجوم تليجرام ⭐
• VIP مميز بالنجوم 👑
• ألعاب متقدمة 🎮
• مكافآت ساعوية 🎯
• إحصائيات مفصلة 📊

💎 **ابدأ باستخدام الأزرار أدناه!**
"""
    
    await update.message.reply_text(welcome_text, reply_markup=kb)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🎮 **دليل استخدام البوت المحدث:**

⭐ ***نظام النجوم:**
• شراء النجوم - استخدم عملة تليجرام
• VIP بالنجوم - اشتراكات حصرية
• هدايا النجوم - أرسل النجوم للأصدقاء

👑 **نظام VIP:**
• اشتراك VIP - احصل على مزايا حصرية
• VIP بالنجوم - اشتراك أسهل
• تواصل مع المشرف - للحصول على المساعدة

🎯 **المكافآت:**
• مكافأة كل ساعة - 3 نقاط 🌶️
• رابط الإحالة - 20 نقطة لكل صديق
• هدايا الأصدقاء - أرسل واستقبل النقاط

🎮 **الألعاب:**
• XO العشوائي - ابحث عن خصم تلقائياً (الفائز يكسب 5 نقاط من الخاسر)
• تخمين الرقم - اختر الرقم الصحيح (الفوز: 5 نقاط، الخسارة: -2 نقاط)

💡 **للشكاوى:**
/report <user_id> <السبب> - الإبلاغ عن مستخدم

🔄 **في حالة وجود مشاكل:**
استخدم /start لتحديث بياناتك
"""
    await update.message.reply_text(help_text)

# --- نظام المطابقة المحسن ---
async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    u = require_user_in_db(user.id, user.to_dict() if user else {})
    
    if u.get('banned_until', 0) > now_ts():
        await update.message.reply_text("🚫 حسابك محظور مؤقتاً.")
        return
    
    if uid in active_chats:
        await update.message.reply_text("❌ أنت في محادثة بالفعل! استخدم /stop لإنهائها أولاً.")
        return
    
    # إذا كان هناك شخص في الانتظار
    if waiting_users:
        partner_id = waiting_users.pop(0)
        uid = update.effective_user.id
        
        # 1. تحديث الحالة في قاعدة البيانات السحابية (مهم جداً للربط)
        db.set_user_status(uid, "chatting", partner_id)
        db.set_user_status(partner_id, "chatting", uid)
        
        # 2. إنشاء محادثة (إذا كانت الدالة موجودة في database.py)
        try:
            db.create_conversation(uid, partner_id)
        except:
            pass

        # 3. دالة داخلية لتنسيق الرسالة بشكل جذاب (تمنع تكرار الكود)
        def format_info_msg(user_data):
            p_name = user_data.get('first_name', 'مجهول')
            p_gender = user_data.get('gender', 'غير محدد')
            p_age = user_data.get('age', 'غير محدد')
            p_country = user_data.get('country', 'غير محدد')
            p_points = user_data.get('points', 0)
            
            # معالجة VIP والتقييم
            is_vip = "👑 ذهبي (VIP)" if user_data.get('vip_until', 0) > time.time() else "👤 عادي"
            r_sum = user_data.get('rating_sum', 0)
            r_total = user_data.get('total_ratings', 1)
            p_rating = round(r_sum / max(r_total, 1), 1)
            p_stars = "⭐" * int(p_rating) if p_rating > 0 else "جديد 🆕"

            return (
                f"🎉 **تم العثور على شريك جديد!**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"👤 **معلومات الشريك:**\n"
                f"• **الاسم:** {p_name}\n"
                f"• **الجنس:** {p_gender}\n"
                f"• **العمر:** {p_age} سنة\n"
                f"• **البلد:** {p_country} 🌍\n"
                f"• **النقاط:** {p_points} 💰\n"
                f"• **التقييم:** {p_stars} ({p_rating})\n"
                f"• **العضوية:** {is_vip}\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"💬 **يمكنك الآن البدء بالدردشة مباشرة...**\n"
                f"⚠️ استخدم /stop للإنهاء."
            )

        # 4. جلب معلومات الطرفين
        current_user_info = db.get_user(uid)
        partner_info = db.get_user(partner_id)

        # 5. إرسال الرسالة لك (تحتوي على معلومات الشريك)
        await update.message.reply_text(
            text=format_info_msg(partner_info),
            parse_mode='Markdown',
            reply_markup=chat_control_keyboard()
        )
        
        # 6. إرسال الرسالة للشريك (تحتوي على معلوماتك أنت)
        try:
            await context.bot.send_message(
                chat_id=partner_id,
                text=format_info_msg(current_user_info),
                parse_mode='Markdown',
                reply_markup=chat_control_keyboard()
            )
        except Exception as e:
            logger.error(f"Error sending message to partner: {e}")

            # تنظيف المحادثة
            if uid in active_chats:
                del active_chats[uid]
            if partner in active_chats:
                del active_chats[partner]
            db.set_user_status(uid, "idle")
            await update.message.reply_text("❌ فشل في التواصل مع الشريك. حاول مرة أخرى.")
            return
            
        await send_to_monitor(context, f"🟢 محادثة جديدة: {uid} ↔ {partner}")
        
    else:
        waiting_users.add(uid)
        db.set_user_status(uid, "searching")
        await update.message.reply_text(
            "🔍 **جاري البحث عن شريك...**\n\n"
            "⏳ **سيبقى البحث نشطاً حتى تجد شريكاً**\n"
            "استخدم /stop_search لإيقاف البحث",
            reply_markup=search_cancel_keyboard()
        )

async def stop_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    
    if uid in waiting_users:
        waiting_users.remove(uid)
        db.set_user_status(uid, "idle")
        await update.message.reply_text(
            "⏹️ **تم إيقاف البحث.**",
            reply_markup=main_reply_keyboard(uid in ADMIN_IDS)
        )
    elif uid in active_chats:
        await update.message.reply_text(
            "❌ **أنت في محادثة حالياً.**\n"
            "استخدم /stop لإنهاء المحادثة أولاً."
        )
    else:
        await update.message.reply_text(
            "ℹ️ **لا يوجد بحث نشط لإيقافه.**",
            reply_markup=main_reply_keyboard(uid in ADMIN_IDS)
        )

async def stop_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    
    if uid not in active_chats:
        await update.message.reply_text("❌ **لا توجد محادثة نشطة.**")
        return
    
    partner = active_chats[uid]
    
    # إزالة من القواميس
    if uid in active_chats:
        del active_chats[uid]
    if partner in active_chats:
        del active_chats[partner]
    
    # تحديث الحالة في قاعدة البيانات
    db.set_user_status(uid, "idle")
    db.set_user_status(partner, "idle")
    
    # إغلاق المحادثة في قاعدة البيانات
    convs = db.list_active_conversations()
    for conv in convs:
        if (conv['user_a'] == uid and conv['user_b'] == partner) or \
           (conv['user_a'] == partner and conv['user_b'] == uid):
            db.close_conversation(conv['id'])
            break
    
    # إرسال إشعارات
    await update.message.reply_text(
        "✅ **تم إنهاء المحادثة.**",
        reply_markup=main_reply_keyboard(uid in ADMIN_IDS)
    )
    
    try:
        await context.bot.send_message(
            chat_id=partner,
            text="🔴 **الشريك أنهى المحادثة.**",
            reply_markup=main_reply_keyboard(partner in ADMIN_IDS)
        )
    except Exception:
        pass
    
    await send_to_monitor(context, f"🔴 محادثة منتهية: {uid} ↔ {partner}")

# --- البحث حسب الجنس ---
async def gender_search_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    u = db.get_user(user.id)
    
    if not u or u.get('points', 0) < GENDER_SEARCH_COST:
        await update.message.reply_text(
            f"❌ نقاطك غير كافية. تحتاج {GENDER_SEARCH_COST} نقاط للبحث حسب الجنس.",
            reply_markup=main_reply_keyboard(user.id in ADMIN_IDS)
        )
        return
    
    await update.message.reply_text(
        f"🔍 **البحث حسب الجنس**\n\n"
        f"💰 **التكلفة:** {GENDER_SEARCH_COST} نقاط\n"
        f"💎 **رصيدك:** {u.get('points', 0)} نقطة\n\n"
        f"✨ **اختر الجنس المطلوب:**",
        reply_markup=ReplyKeyboardMarkup([['👦 ذكر','👧 أنثى'],['إلغاء']], resize_keyboard=True)
    )
    USER_STATES[user.id] = 'waiting_gender_choice'

# --- معالجة الرسائل في المحادثات ---
async def handle_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    
    if uid not in active_chats:
        return
    
    partner = active_chats[uid]
    
    # تصفية الكلمات المحظورة
    text = update.message.text
    if text:
        penalty = 0
        lowered = text.lower()
        for bad in FILTERED_WORDS:
            if bad in lowered:
                penalty += 5
                
        if penalty:
            db.consume_points(uid, penalty)
            await update.message.reply_text(f"⚠️ **تم خصم {penalty} نقاط لاستخدام كلمات محظورة.**")
            await send_to_monitor(context, f"🚫 مستخدم {uid} استخدم كلمات محظورة: {text}")
    
    # إرسال الرسالة للشريك
    try:
        if update.message.text:
            await context.bot.send_message(chat_id=partner, text=text)
        elif update.message.photo:
            await context.bot.send_photo(chat_id=partner, photo=update.message.photo[-1].file_id)
        elif update.message.video:
            await context.bot.send_video(chat_id=partner, video=update.message.video.file_id)
        elif update.message.voice:
            await context.bot.send_voice(chat_id=partner, voice=update.message.voice.file_id)
        elif update.message.document:
            await context.bot.send_document(chat_id=partner, document=update.message.document.file_id)
        elif update.message.sticker:
            await context.bot.send_sticker(chat_id=partner, sticker=update.message.sticker.file_id)
        elif update.message.audio:
            await context.bot.send_audio(chat_id=partner, audio=update.message.audio.file_id)
        
        # محاكاة مؤشر الكتابة
        async def show_typing_to_partner():
            try:
                await context.bot.send_chat_action(chat_id=partner, action="typing")
                await asyncio.sleep(1)
            except:
                pass
                
        asyncio.create_task(show_typing_to_partner())
        
    except Exception as e:
        await update.message.reply_text("⚠️ **فشل في إرسال الرسالة.** قد يكون الشريك غادر المحادثة.")
        # تنظيف المحادثة
        if uid in active_chats:
            partner = active_chats[uid]
            if uid in active_chats:
                del active_chats[uid]
            if partner in active_chats:
                del active_chats[partner]
            db.set_user_status(uid, "idle")
            db.set_user_status(partner, "idle")

# --- نظام المكافآت المحسن ---
async def reward_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    u = require_user_in_db(user.id, user.to_dict() if user else {})
    
    last_reward = db.get_last_reward(user.id)
    now = now_ts()
    
    if now - last_reward < REWARD_COOLDOWN:
        remaining = REWARD_COOLDOWN - (now - last_reward)
        
        time_left = format_time_left(remaining)
            
        await update.message.reply_text(
            f"⏳ **يرجى الانتظار للحصول على المكافأة التالية**\n\n"
            f"⏰ **الوقت المتبقي:** {time_left}\n"
            f"💰 **المكافأة:** {REWARD_POINTS} نقاط 🌶️\n\n"
            f"💡 يمكنك كسب المزيد من النقاط عبر زر '💰 كسب النقاط'"
        )
        return
    
    # منح المكافأة
    db.add_points(user.id, REWARD_POINTS)
    db.set_last_reward(user.id, now)
    
    # إذا كان مستخدم VIP، يعطي مكافأة مضاعفة
    vip_status = db.get_vip_status(user.id)
    if vip_status['is_vip']:
        bonus = REWARD_POINTS * 2
        db.add_points(user.id, bonus)
        reward_text = f"""
🎉 **تم منحك مكافأة الساعة!** 👑

💰 **المكافأة:** {REWARD_POINTS} نقاط
✨ **مكافأة VIP:** {bonus} نقاط
💎 **الإجمالي:** {REWARD_POINTS + bonus} نقاط 🌶️

⏰ **المكافأة التالية بعد:** ساعة واحدة
🎁 **شكراً لكونك مستخدم VIP!**
"""
    else:
        reward_text = f"""
🎉 **تم منحك مكافأة الساعة!**

💰 **المكافأة:** {REWARD_POINTS} نقاط 🌶️
💎 **رصيدك الجديد:** {u.get('points', 0) + REWARD_POINTS} نقطة

⏰ **المكافأة التالية بعد:** ساعة واحدة
👑 **اشترك في VIP للحصول على مكافآت مضاعفة!**
"""
    
    await update.message.reply_text(reward_text, reply_markup=main_reply_keyboard(user.id in ADMIN_IDS))

# --- كسب النقاط ---
async def earn_points_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    await update.message.reply_text("💰 **طرق كسب النقاط:**", reply_markup=earn_points_keyboard())

async def share_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    user = update.effective_user
    bot_username = (await context.bot.get_me()).username
    
    links_text = f"""
📤 **كسب النقاط عبر مشاركة الروابط**

🎁 **احصل على 20 نقطة لكل صديق ينضم عبر رابطك!**

🔗 **رابط الدعوة الخاص بك:**
https://t.me/{bot_username}?start={user.id}

💎 **كود الإحالة:** {db.get_user(user.id).get('referral_code', '')}

📊 **إحصائياتك الحالية:**
• عدد الإحالات: {db.get_user(user.id).get('referrals', 0)}
• النقاط المحصلة: {db.get_user(user.id).get('referrals', 0) * 20} نقطة

🔥 **ابدأ المشاركة الآن واكسب المزيد!**
"""
    
    await update.message.reply_text(links_text, reply_markup=earn_points_keyboard())

async def invite_friends(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    user = update.effective_user
    bot_username = (await context.bot.get_me()).username
    
    invite_text = f"""
👥 **دعوة الأصدقاء**

🎁 **المكافآت:**
• 20 نقطة لكل صديق يدخل عبر رابطك
• 10 نقاط إضافية عندما يكمل صديقك ملفه الشخصي
• فرصة الظهور في لوحة المتصدرين

🔗 **رابط الدعوة الخاص بك:**
https://t.me/{bot_username}?start={user.id}

💎 **كود الإحالة:** {db.get_user(user.id).get('referral_code', '')}

📋 **تعليمات الدعوة:**
1. انسخ الرابط أعلاه
2. أرسله لأصدقائك عبر واتساب، تليجرام، إنستغرام
3. احصل على 20 نقطة فور انضمام كل صديق

📊 **إحصائيات دعوتك:**
• عدد الأصدقاء المدعوين: {db.get_user(user.id).get('referrals', 0)}
• النقاط المحصلة: {db.get_user(user.id).get('referrals', 0) * 20} نقطة
"""
    
    await update.message.reply_text(invite_text, reply_markup=earn_points_keyboard())

async def friends_gifts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """قائمة هدايا الأصدقاء"""
    await update.message.reply_text(
        "🎁 **هدايا الأصدقاء**\n\n"
        "💝 **يمكنك إرسال واستقبال الهدايا من الأصدقاء:**\n\n"
        "👇 **اختر من القائمة:**",
        reply_markup=friends_keyboard()
    )

# --- الملف الشخصي المحسن ---
async def profile_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    await update.message.reply_text("🧾 **الملف الشخصي:**", reply_markup=profile_keyboard())

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    user = update.effective_user
    u = safe_get_user(user.id)
    
    # حساب المستوى
    level = u.get('level', 1)
    points = u.get('points', 0)
    next_level_points = level * 100
    progress = min((points / next_level_points) * 100, 100) if next_level_points > 0 else 0
    
    # حساب متوسط التقييم
    avg_rating = db.get_average_rating(user.id)
    
    # حالة VIP
    vip_status = db.get_vip_status(user.id)
    vip_info = f"❌ غير مشترك" 
    if vip_status['is_vip']:
        vip_info = f"✅ {vip_status['vip_title']} ({vip_status['days_left']} يوم متبقي)"
    
    # رصيد النجوم
    stars_balance = db.get_stars_balance(user.id)
    
    profile_text = f"""
📄 **الملف الشخصي لـ {user.first_name}**

👤 **المعلومات الشخصية:**
• **الاسم:** {user.first_name} {user.last_name or ''}
• **اسم المستخدم:** @{user.username or 'غير محدد'}
• **البلد:** {u.get('country') or 'غير محدد'}
• **الجنس:** {u.get('gender') or 'غير محدد'}
• **العمر:** {u.get('age') or '—'}
• **اللغة:** {u.get('language') or 'عربي'}

📊 **الإحصائيات:**
• **النقاط:** {points} 🌶️
• **النجوم:** {stars_balance} ⭐
• **المستوى:** {level} 🎯
• **التقدم:** {progress:.1f}%
• **التقييم:** {avg_rating:.1f} ⭐
• **عدد المحادثات:** {u.get('chats_count',0)}
• **عدد الإحالات:** {u.get('referrals',0)}

👑 **حالة VIP:** {vip_info}
"""
    
    await update.message.reply_text(profile_text, reply_markup=profile_keyboard())

async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    user = update.effective_user
    await update.message.reply_text("⚙️ **إعدادات الملف الشخصي:**", reply_markup=settings_keyboard(user.id))

async def update_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    user = update.effective_user
    u = db.get_user(user.id)
    
    if u and u.get('gender') and u.get('gender_changed', 0) == 1:
        if u.get('points', 0) < GENDER_CHANGE_COST:
            await update.message.reply_text(
                f"❌ تحتاج {GENDER_CHANGE_COST} نقاط لتغيير الجنس.",
                reply_markup=settings_keyboard(user.id)
            )
            return
        else:
            db.consume_points(user.id, GENDER_CHANGE_COST)
            await update.message.reply_text(
                f"💰 تم خصم {GENDER_CHANGE_COST} نقاط لتغيير الجنس."
            )
    
    await update.message.reply_text(
        "👫 **اختر جنسك:**\n\n"
        "⚠️ **ملاحظة:** يمكن تغيير الجنس مرة واحدة فقط مجاناً!",
        reply_markup=gender_select_keyboard()
    )
    USER_STATES[user.id] = 'waiting_gender_update'

async def update_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    user = update.effective_user
    USER_STATES[user.id] = 'waiting_age_update'
    await update.message.reply_text(
        "🎂 **أدخل عمرك:**\n\n"
        "⚠️ **الشرط:** يجب أن يكون العمر بين 15 و 60 سنة"
    )

async def update_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    await update.message.reply_text(
        "📍 **تحديد البلد:**\n\n"
        "👇 **اختر بلدك من القائمة:**",
        reply_markup=country_select_keyboard()
    )
    USER_STATES[update.effective_user.id] = 'waiting_country_update'

# --- تحديث البيانات ---
async def handle_gender_update(update: Update, context: ContextTypes.DEFAULT_TYPE, gender: str):
    user = update.effective_user
    try:
        db.update_user_profile(user.id, {
            'gender': gender,
            'gender_changed': 1
        })
        await update.message.reply_text(
            f"✅ **تم تحديث الجنس إلى:** {gender}\n\n"
            f"⚠️ **ملاحظة:** يمكنك تغيير الجنس مرة أخرى مقابل {GENDER_CHANGE_COST} نقاط",
            reply_markup=settings_keyboard(user.id)
        )
        USER_STATES.pop(user.id, None)
    except Exception as e:
        logger.error(f"خطأ في تحديث الجنس: {e}")
        await update.message.reply_text(
            "❌ حدث خطأ في تحديث البيانات. أرسل /start لتحديث بياناتك.",
            reply_markup=main_reply_keyboard(user.id in ADMIN_IDS)
        )

async def handle_age_update(update: Update, context: ContextTypes.DEFAULT_TYPE, age: str):
    user = update.effective_user
    try:
        age_int = int(age)
        if age_int < 15 or age_int > 60:
            await update.message.reply_text("⚠️ العمر يجب أن يكون بين 15 و 60 سنة.")
            return
        
        db.update_user_profile(user.id, {'age': age_int})
        await update.message.reply_text(
            f"✅ **تم تحديث العمر إلى:** {age} سنة",
            reply_markup=settings_keyboard(user.id)
        )
        USER_STATES.pop(user.id, None)
    except ValueError:
        await update.message.reply_text("⚠️ يرجى إدخال عمر صحيح (أرقام فقط).")
    except Exception as e:
        logger.error(f"خطأ في تحديث العمر: {e}")
        await update.message.reply_text(
            "❌ حدث خطأ في تحديث البيانات. أرسل /start لتحديث بياناتك.",
            reply_markup=main_reply_keyboard(user.id in ADMIN_IDS)
        )

async def handle_country_update(update: Update, context: ContextTypes.DEFAULT_TYPE, country: str):
    user = update.effective_user
    try:
        if country == "🌍 دولة أخرى":
            await update.message.reply_text("🌍 **أدخل اسم بلدك:**")
            USER_STATES[user.id] = 'waiting_country_name'
            return
            
        db.update_user_profile(user.id, {'country': country})
        await update.message.reply_text(
            f"✅ **تم تحديث البلد إلى:** {country}",
            reply_markup=settings_keyboard(user.id)
        )
        USER_STATES.pop(user.id, None)
    except Exception as e:
        logger.error(f"خطأ في تحديث البلد: {e}")
        await update.message.reply_text(
            "❌ حدث خطأ في تحديث البيانات. أرسل /start لتحديث بياناتك.",
            reply_markup=main_reply_keyboard(user.id in ADMIN_IDS)
        )

# --- نظام الألعاب المحسن ---
async def games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    await update.message.reply_text("🎮 **الألعاب:**", reply_markup=games_keyboard())

async def xo_game_random(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    user = update.effective_user
    
    # إزالة أي حالة سابقة
    if user.id in USER_STATES and USER_STATES[user.id].startswith('playing_xo_'):
        USER_STATES.pop(user.id, None)
    
    # البحث عن خصم
    await update.message.reply_text("🔍 **جاري البحث عن خصم...**")
    
    opponent_id = await game_manager.search_xo_opponent(user.id, context, max_wait=60)
    
    if opponent_id:
        # إنشاء لعبة جديدة
        game = game_manager.create_xo_game(user.id, opponent_id, is_random=True)
        
        # إرسال رسالة للمستخدم
        msg1 = await update.message.reply_text(
            f"🎮 **تم العثور على خصم!**\n\n"
            f"💰 **المكافآت:**\n"
            f"• الفائز: يحصل على 5 نقاط من الخاسر\n"
            f"• الخاسر: يخسر 5 نقاط للفائز\n\n"
            f"👇 **دورك الآن، اختر خانة:**",
            reply_markup=create_xo_keyboard(game.board, game.game_id, can_play=(game.current_player == user.id))
        )
        game.message_ids[user.id] = msg1.message_id
        
        try:
            # إرسال رسالة للخصم
            opponent_info = db.get_user(opponent_id)
            opponent_name = opponent_info.get('first_name', 'لاعب') if opponent_info else 'لاعب'
            
            msg2 = await context.bot.send_message(
                chat_id=opponent_id,
                text=f"🎮 **تم العثور على خصم!**\n\n"
                     f"💰 **المكافآت:**\n"
                     f"• الفائز: يحصل على 5 نقاط من الخاسر\n"
                     f"• الخاسر: يخسر 5 نقاط للفائز\n\n"
                     f"👇 **دورك الآن، اختر خانة:**",
                reply_markup=create_xo_keyboard(game.board, game.game_id, can_play=(game.current_player == opponent_id))
            )
            game.message_ids[opponent_id] = msg2.message_id
            
        except Exception as e:
            logger.error(f"خطأ في إرسال رسالة للخصم: {e}")
            await update.message.reply_text("❌ فشل في التواصل مع الخصم.")
            game_manager.delete_xo_game(game.game_id)
    else:
        await update.message.reply_text(
            "⏳ **لم يتم العثور على خصم حالياً.**\n\n"
            "💡 **يمكنك المحاولة مرة أخرى لاحقاً.**",
            reply_markup=games_keyboard()
        )

async def guess_number_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    user = update.effective_user
    game = game_manager.create_guess_game(user.id)
    
    await update.message.reply_text(
        "🔢 **لعبة تخمين الرقم**\n\n"
        "🎯 **القواعد:**\n"
        "• الرقم بين 1 و 100\n"
        "• لديك 10 محاولات\n"
        "• **الفوز: +5 نقاط**\n"
        "• **الخسارة: -2 نقاط**\n\n"
        "👇 **أدخل رقمك الأول:**"
    )
    
    USER_STATES[user.id] = f'playing_guess_{game.game_id}'

async def handle_xo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data
    
    if data.startswith("xo_move_"):
        parts = data.split("_")
        if len(parts) != 4:
            return
        
        game_id = int(parts[2])
        position = int(parts[3])
        
        game = game_manager.get_xo_game(game_id)
        if not game:
            await query.edit_message_text("❌ **اللعبة غير موجودة.**")
            return
        
        if game.status != 'active':
            await query.edit_message_text("❌ **اللعبة غير نشطة.**")
            return
        
        if user.id not in [game.player1, game.player2]:
            await query.answer("❌ **أنت لست لاعباً في هذه اللعبة.**")
            return
        
        success, result, winner = game.make_move(user.id, position)
        if not success:
            await query.answer("❌ **حركة غير صالحة.**")
            return
        
        # تحديث لوحة اللعبة
        if result == "فوز":
            # حساب الفائز والخاسر
            loser = game.player2 if winner == game.player1 else game.player1
            
            # توزيع النقاط: الفائز يكسب 5 نقاط من الخاسر
            db.add_points(winner, 5)
            db.consume_points(loser, 5)
            
            winner_text = f"""
🎉 **{game.symbols[winner]} فاز!**

💰 **المكافآت:**
• الفائز: +5 نقاط 🌶️
• الخاسر: -5 نقاط 🌶️

👑 **مبروك للفائز!**
"""
            
            await query.edit_message_text(
                winner_text,
                reply_markup=create_xo_keyboard(game.board, game_id, can_play=False)
            )
            
            # تحديث رسالة الخصم
            if user.id == game.player1 and game.player2 in game.message_ids:
                try:
                    await context.bot.edit_message_text(
                        chat_id=game.player2,
                        message_id=game.message_ids[game.player2],
                        text=winner_text,
                        reply_markup=create_xo_keyboard(game.board, game_id, can_play=False)
                    )
                except:
                    pass
            elif user.id == game.player2 and game.player1 in game.message_ids:
                try:
                    await context.bot.edit_message_text(
                        chat_id=game.player1,
                        message_id=game.message_ids[game.player1],
                        text=winner_text,
                        reply_markup=create_xo_keyboard(game.board, game_id, can_play=False)
                    )
                except:
                    pass
            
            # تسجيل اللعبة في قاعدة البيانات
            db.create_game('xo', winner, loser)
            db.update_game_result(game_id, 'win', 5, 0)
            
            # تنظيف اللعبة بعد فترة
            await asyncio.sleep(10)
            game_manager.delete_xo_game(game_id)
            
        elif result == "تعادل":
            tie_text = "🤝 **تعادل!**\n\n💰 **لا توجد نقاط مكتسبة أو خاسرة.**"
            await query.edit_message_text(
                tie_text,
                reply_markup=create_xo_keyboard(game.board, game_id, can_play=False)
            )
            
            if user.id == game.player1 and game.player2 in game.message_ids:
                try:
                    await context.bot.edit_message_text(
                        chat_id=game.player2,
                        message_id=game.message_ids[game.player2],
                        text=tie_text,
                        reply_markup=create_xo_keyboard(game.board, game_id, can_play=False)
                    )
                except:
                    pass
            elif user.id == game.player2 and game.player1 in game.message_ids:
                try:
                    await context.bot.edit_message_text(
                        chat_id=game.player1,
                        message_id=game.message_ids[game.player1],
                        text=tie_text,
                        reply_markup=create_xo_keyboard(game.board, game_id, can_play=False)
                    )
                except:
                    pass
            
            # تسجيل اللعبة
            db.create_game('xo', game.player1, game.player2)
            db.update_game_result(game_id, 'draw', 0, 0)
            
            await asyncio.sleep(10)
            game_manager.delete_xo_game(game_id)
            
        else:  # استمرار
            current_symbol = game.symbols[game.current_player]
            await query.edit_message_text(
                f"🎮 **دور:** {current_symbol}\n👇 **اختر خانة:**",
                reply_markup=create_xo_keyboard(game.board, game_id, can_play=(game.current_player == user.id))
            )
            
            opponent_id = game.player2 if game.player1 == user.id else game.player1
            if opponent_id in game.message_ids:
                try:
                    await context.bot.edit_message_text(
                        chat_id=opponent_id,
                        message_id=game.message_ids[opponent_id],
                        text=f"🎮 **دور:** {current_symbol}\n👇 **اختر خانة:**",
                        reply_markup=create_xo_keyboard(game.board, game_id, can_play=(game.current_player == opponent_id))
                    )
                except:
                    pass
    
    elif data.startswith("xo_restart_"):
        game_id = int(data.split("_")[2])
        game = game_manager.get_xo_game(game_id)
        
        if game and user.id in [game.player1, game.player2]:
            game.restart()
            current_symbol = game.symbols[game.current_player]
            await query.edit_message_text(
                f"🔄 **تم إعادة اللعبة**\n🎮 **دور:** {current_symbol}\n👇 **اختر خانة:**",
                reply_markup=create_xo_keyboard(game.board, game_id, can_play=(game.current_player == user.id))
            )
            
            opponent_id = game.player2 if game.player1 == user.id else game.player1
            if opponent_id in game.message_ids:
                try:
                    await context.bot.edit_message_text(
                        chat_id=opponent_id,
                        message_id=game.message_ids[opponent_id],
                        text=f"🔄 **تم إعادة اللعبة**\n🎮 **دور:** {current_symbol}\n👇 **اختر خانة:**",
                        reply_markup=create_xo_keyboard(game.board, game_id, can_play=(game.current_player == opponent_id))
                    )
                except:
                    pass
    
    elif data.startswith("xo_exit_"):
        game_id = int(data.split("_")[2])
        game = game_manager.get_xo_game(game_id)
        
        if game:
            opponent_id = game.player2 if game.player1 == user.id else game.player1
            if opponent_id in game.message_ids:
                try:
                    await context.bot.send_message(
                        chat_id=opponent_id,
                        text="❌ **خرج الخصم من اللعبة.**"
                    )
                except:
                    pass
            
            game_manager.delete_xo_game(game_id)
            await query.edit_message_text("❌ **تم الخروج من اللعبة.**", reply_markup=games_keyboard())
    
    elif data.startswith("xo_start_"):
        game_id = int(data.split("_")[2])
        game = game_manager.get_xo_game(game_id)
        
        if game and user.id in [game.player1, game.player2]:
            current_symbol = game.symbols[game.current_player]
            await query.edit_message_text(
                f"🎮 **دور:** {current_symbol}\n👇 **اختر خانة:**",
                reply_markup=create_xo_keyboard(game.board, game_id, can_play=(game.current_player == user.id))
            )

# --- نظام النجوم في البوت الرئيسي ---
async def stars_menu_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة النجوم من الزر الرئيسي"""
    if stars_system:
        if update.callback_query:
            await stars_system.show_stars_menu(update.callback_query)
        else:
            await stars_system.show_stars_menu_via_message(update, context)
    else:
        await update.message.reply_text(
            "⭐ **نظام النجوم**\n\n"
            "🚧 **قيد التطوير...**\n"
            "سيتم تفعيل نظام النجوم قريباً.",
            reply_markup=main_reply_keyboard(update.effective_user.id in ADMIN_IDS)
        )

async def show_stars_balance_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض رصيد النجوم من الزر الرئيسي"""
    user = update.effective_user
    
    stars_balance = db.get_stars_balance(user.id)
    vip_status = db.get_vip_status(user.id)
    
    balance_text = f"""
💰 **رصيد النجوم:** {stars_balance} ⭐

👑 **حالة VIP:** {'✅ نشط' if vip_status['is_vip'] else '❌ غير نشط'}
"""
    
    if vip_status['is_vip']:
        balance_text += f"⏰ **الأيام المتبقية:** {vip_status['days_left']} يوم\n"
    
    balance_text += "\n👇 **استخدم الأزرار للتحكم في النجوم:**"
    
    await update.message.reply_text(
        balance_text,
        reply_markup=StarsKeyboards.stars_main_menu()
    )

async def handle_stars_callback_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة استدعاءات النجوم"""
    if stars_system:
        await stars_system.handle_stars_callback(update, context)
    else:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "⭐ **نظام النجوم**\n\n"
            "🚧 **قيد التطوير...**\n"
            "سيتم تفعيل نظام النجوم قريباً."
        )

# --- نظام VIP المحسن ---
async def vip_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    user = update.effective_user
    u = db.get_user(user.id)
    vip_status = db.get_vip_status(user.id)
    
    vip_text = f"""
👑 **نظام VIP**

✨ **مزايا VIP:**
• أولوية في البحث عن الشركاء
• إمكانية البحث حسب الجنس مجاناً
• مكافآت نقاط مضاعفة (x2)
• إمكانية التحدث مع المشرف مباشرة
• لقب VIP مميز في الملف الشخصي
• مكافآت نجوم في الألعاب

💰 **طرق الاشتراك:**
• **بالنقاط:** أسعار تقليدية
• **بالنجوم:** أسهل وأسرع (⭐)

📊 **حالتك الحالية:**
• **النقاط:** {u.get('points', 0)} 🌶️
• **النجوم:** {db.get_stars_balance(user.id)} ⭐
• **حالة VIP:** {'✅ نشط' if vip_status['is_vip'] else '❌ غير نشط'}
• **الأيام المتبقية:** {vip_status['days_left'] if vip_status['is_vip'] else 0}

👇 **اختر طريقة الاشتراك:**
"""
    
    await update.message.reply_text(vip_text, reply_markup=vip_keyboard())

async def vip_purchase_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    user = update.effective_user
    u = db.get_user(user.id)
    
    vip_text = f"""
🛒 **شراء اشتراك VIP بالنقاط**

💰 **رصيدك الحالي:** {u.get('points', 0)} نقطة 🌶️

👇 **اختر مدة الاشتراك:**
"""
    
    await update.message.reply_text(vip_text, reply_markup=vip_purchase_keyboard())

async def vip_stars_menu_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """قائمة VIP بالنجوم"""
    if stars_system:
        if update.callback_query:
            await stars_system.show_vip_stars_packages(update.callback_query)
        else:
            await update.message.reply_text(
                "⭐ **VIP بالنجوم**\n\n"
                "👇 **الرجاء استخدام الزر أدناه:**",
                reply_markup=StarsKeyboards.stars_main_menu()
            )
    else:
        await update.message.reply_text(
            "⭐ **VIP بالنجوم**\n\n"
            "🚧 **قيد التطوير...**\n"
            "سيتم تفعيل نظام النجوم قريباً.",
            reply_markup=vip_keyboard()
        )

async def handle_vip_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE, days: int):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    price = VIP_POINTS_PRICES.get(days, 0)
    
    if price == 0:
        await query.edit_message_text("❌ **الباقة غير متوفرة.**")
        return
    
    u = db.get_user(user.id)
    if not u or u.get('points', 0) < price:
        await query.edit_message_text(f"❌ **نقاطك غير كافية.** تحتاج {price} نقطة.")
        return
    
    # شراء VIP
    if db.purchase_vip(user.id, days, price):
        vip_status = db.get_vip_status(user.id)
        
        # تحديث معلومات VIP في قاعدة البيانات
        db.set_vip(user.id, days)
        
        await query.edit_message_text(
            f"✅ **تم شراء اشتراك VIP بنجاح!**\n\n"
            f"📅 **المدة:** {days} يوم\n"
            f"💰 **السعر:** {price} نقطة 🌶️\n"
            f"📊 **الأيام المتبقية:** {vip_status['days_left']}\n"
            f"👑 **لقبك:** {vip_status['vip_title']}\n\n"
            f"✨ **تم تفعيل جميع مزايا VIP لك!**"
        )
        
        # إرسال إشعار للمشرف
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"💰 **عملية شراء VIP جديدة:**\n\n"
                         f"👤 **المشتري:** {user.first_name} (ID: {user.id})\n"
                         f"📅 **المدة:** {days} يوم\n"
                         f"💰 **السعر:** {price} نقطة"
                )
            except:
                pass
    else:
        await query.edit_message_text("❌ **فشل في عملية الشراء.**")

async def vip_contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تواصل VIP مع المشرف"""
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    user = update.effective_user
    vip_status = db.get_vip_status(user.id)
    
    if not vip_status['is_vip']:
        await update.message.reply_text(
            "❌ **هذه الميزة متاحة لأعضاء VIP فقط.**\n\n"
            "👑 **اشترك في VIP للحصول على:**\n"
            "• الدعم الفني المباشر\n"
            "• إصلاح المشاكل بسرعة\n"
            "• اقتراحات مخصصة",
            reply_markup=vip_keyboard()
        )
        return
    
    await update.message.reply_text(
        "👑 **تواصل مع المشرف**\n\n"
        "💬 **يمكنك التواصل مع المشرف عبر البوت التالي:**\n"
        "👉 @ssvv119\n\n"
        "📞 **أو أرسل رسالتك هنا وسيتم إرسالها للمشرف:**"
    )
    USER_STATES[user.id] = 'waiting_admin_message'

# --- الإحصائيات والوظائف الإضافية ---
async def stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """قائمة الإحصائيات"""
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    await update.message.reply_text("📊 **الإحصائيات:**", reply_markup=stats_keyboard())

async def show_users_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات المستخدمين"""
    stats = db.get_stats()
    
    stats_text = f"""
👥 **إحصائيات المستخدمين:**

📊 **العامة:**
• إجمالي المستخدمين: {stats.get('total_users', 0)}
• المستخدمين النشطين: {stats.get('active_users', 0)}
• في حالة البحث: {stats.get('searching_users', 0)}
• مستخدمين VIP: {stats.get('vip_users', 0)}

👫 **التوزيع حسب الجنس:**
• الذكور: {stats.get('male_users', 0)}
• الإناث: {stats.get('female_users', 0)}

📈 **إحصائيات اليوم:**
• المحادثات الجديدة: {stats.get('today_chats', 0)}
• المستخدمين الجدد: {stats.get('new_users_today', 0)}
• الألعاب المنتهية: {stats.get('today_games', 0)}
"""
    
    await update.message.reply_text(stats_text, reply_markup=stats_keyboard())

async def show_activity_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات النشاط"""
    stats = db.get_stats()
    
    activity_text = f"""
🎯 **إحصائيات النشاط:**

💬 **المحادثات:**
• المحادثات النشطة: {stats.get('active_chats', 0)}
• إجمالي الرسائل: {stats.get('total_messages', 0)}
• المحادثات اليوم: {stats.get('today_chats', 0)}

🎮 **الألعاب:**
• الألعاب اليوم: {stats.get('today_games', 0)}

💰 **الرصيد:**
• إجمالي النقاط: {stats.get('total_points', 0)}
• إجمالي النجوم: {stats.get('total_stars', 0)}
"""
    
    await update.message.reply_text(activity_text, reply_markup=stats_keyboard())

async def show_points_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات النقاط"""
    stats = db.get_stats()
    
    points_text = f"""
💰 **إحصائيات النقاط:**

💎 **الإجمالي:**
• مجموع النقاط: {stats.get('total_points', 0)}

📊 **التوزيع:**
• المتوسط لكل مستخدم: {stats.get('total_points', 0) / max(stats.get('total_users', 1), 1):.1f}

✨ **يمكنك زيادة نقاطك عن طريق:**
• المكافأة الساعوية 🎯
• دعوة الأصدقاء 👥
• اللعب والفوز 🎮
"""
    
    await update.message.reply_text(points_text, reply_markup=stats_keyboard())

async def show_stars_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات النجوم"""
    stats = db.get_stats()
    
    stars_text = f"""
⭐ **إحصائيات النجوم:**

💎 **الإجمالي:**
• مجموع النجوم: {stats.get('total_stars', 0)}

💰 **مشتروات VIP بالنجوم:**
• إجمالي النجوم المنفقة: {stats.get('total_stars_spent', 0)}

✨ **النجوم هي عملة تليجرام الرسمية:**
• يمكنك شرائها من خلال البوت
• تستخدم لشراء VIP والألعاب المميزة
"""
    
    await update.message.reply_text(stars_text, reply_markup=stats_keyboard())

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لوحة المتصدرين"""
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    user = update.effective_user
    
    try:
        # الحصول على أفضل 10 مستخدمين حسب النقاط
        top_users = db.get_leaderboard(limit=10)
        
        if not top_users:
            await update.message.reply_text(
                "🏆 **لوحة المتصدرين**\n\n"
                "📭 **لا يوجد مستخدمين بعد.**",
                reply_markup=main_reply_keyboard(user.id in ADMIN_IDS)
            )
            return
        
        leaderboard_text = "🏆 **أفضل 10 لاعبين حسب النقاط:**\n\n"
        
        for i, u in enumerate(top_users, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            name = u.get('first_name', 'مستخدم')[:15]
            points = u.get('points', 0)
            leaderboard_text += f"{medal} **{name}** - {points} نقطة 🌶️\n"
        
        # ترتيب المستخدم الحالي
        user_rank = db.get_user_rank(user.id)
        user_info = db.get_user(user.id)
        user_points = user_info.get('points', 0) if user_info else 0
        
        leaderboard_text += f"\n📊 **ترتيبك الحالي:** #{user_rank}\n"
        leaderboard_text += f"💎 **نقاطك:** {user_points} نقطة 🌶️"
        
        await update.message.reply_text(
            leaderboard_text,
            reply_markup=main_reply_keyboard(user.id in ADMIN_IDS)
        )
        
    except Exception as e:
        logger.error(f"خطأ في عرض لوحة المتصدرين: {e}")
        await update.message.reply_text(
            "❌ **حدث خطأ في عرض لوحة المتصدرين.**\n\n"
            "🔧 **يرجى المحاولة لاحقاً.**",
            reply_markup=main_reply_keyboard(user.id in ADMIN_IDS)
        )

# --- المشرفين ---
async def admin_opener_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لوحة المشرف"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ **ليس لديك صلاحية للوصول لهذه الصفحة.**")
        return
    
    try:
        # جلب الإحصائيات من قاعدة البيانات
        stats = db.get_stats()
        
        admin_text = f"""
🛠️ **لوحة المشرف**

📊 **إحصائيات النظام:**
• **عدد المستخدمين:** {stats.get('total_users', 0)}
• **المستخدمين النشطين:** {stats.get('active_users', 0)}
• **في حالة البحث:** {stats.get('searching_users', 0)}
• **المحادثات النشطة:** {stats.get('active_chats', 0)}
• **إجمالي النقاط:** {stats.get('total_points', 0)}
• **إجمالي النجوع:** {stats.get('total_stars', 0)}
• **المستخدمين الجدد اليوم:** {stats.get('new_users_today', 0)}

⚙️ **الأوامر المتاحة:**
/broadcast <الرسالة> - بث رسالة لجميع المستخدمين
/ban <user_id> <السبب> <المدة بالأيام> - حظر مستخدم
/unban <user_id> - إلغاء حظر مستخدم
/addpoints <user_id> <العدد> - إضافة نقاط لمستخدم
/removepoints <user_id> <العدد> - خصم نقاط من مستخدم

📈 **تقارير النظام متاحة عبر الأزرار أدناه.**
"""
        
        await update.message.reply_text(admin_text, reply_markup=admin_keyboard())
        
    except Exception as e:
        logger.error(f"خطأ في لوحة المشرف: {e}")
        await update.message.reply_text(
            "❌ **حدث خطأ في تحميل الإحصائيات.**\n\n"
            "🔧 **يرجى المحاولة لاحقاً.**",
            reply_markup=main_reply_keyboard(user.id in ADMIN_IDS)
        )

async def admin_stats_full(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الإحصائيات الكاملة للمشرف"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ **ليس لديك صلاحية للوصول لهذه الصفحة.**")
        return
    
    try:
        stats = db.get_stats()
        vip_stats = db.get_vip_stats()
        
        stats_text = f"""
📊 **الإحصائيات الكاملة:**

👥 **المستخدمين:**
• إجمالي المستخدمين: {stats.get('total_users', 0)}
• الذكور: {stats.get('male_users', 0)}
• الإناث: {stats.get('female_users', 0)}
• مستخدمين VIP: {stats.get('vip_users', 0)}
• المستخدمين الجدد اليوم: {stats.get('new_users_today', 0)}

💬 **النشاط:**
• المستخدمين النشطين: {stats.get('active_users', 0)}
• في حالة البحث: {stats.get('searching_users', 0)}
• المحادثات النشطة: {stats.get('active_chats', 0)}
• المحادثات اليوم: {stats.get('today_chats', 0)}
• إجمالي الرسائل: {stats.get('total_messages', 0)}

💰 **الرصيد:**
• إجمالي الفلفل🌶️: {stats.get('total_points', 0)}
• إجمالي النجوم: {stats.get('total_stars', 0)}

🎮 **الألعاب:**
• الألعاب اليوم: {stats.get('today_games', 0)}

👑 **إحصائيات VIP:**
• إجمالي أيام VIP: {vip_stats.get('total_vip_days', 0)}
• إجمالي المشتريات: {vip_stats.get('total_vip_purchases', 0)}
• النجوم المنفقة: {vip_stats.get('total_stars_spent', 0)}
"""
        
        await update.message.reply_text(stats_text, reply_markup=admin_keyboard())
        
    except Exception as e:
        logger.error(f"خطأ في الإحصائيات الكاملة: {e}")
        await update.message.reply_text(
            "❌ **حدث خطأ في تحميل الإحصائيات.**",
            reply_markup=admin_keyboard()
        )

async def admin_banned_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض المستخدمين المحظورين"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ **ليس لديك صلاحية للوصول لهذه الصفحة.**")
        return
    
    try:
        # الحصول على جميع المستخدمين
        all_users = db.list_all_users(limit=1000)
        banned_users = []
        
        now = now_ts()
        for u in all_users:
            if u.get('banned_until', 0) > now:
                banned_users.append(u)
        
        if not banned_users:
            await update.message.reply_text(
                "👮 **المستخدمين المحظورين:**\n\n"
                "✅ **لا يوجد مستخدمين محظورين حالياً.**",
                reply_markup=admin_keyboard()
            )
            return
        
        banned_text = "👮 **المستخدمين المحظورين:**\n\n"
        
        for i, u in enumerate(banned_users[:20], 1):
            user_id = u.get('user_id')
            username = f"@{u.get('username')}" if u.get('username') else "لا يوجد"
            first_name = u.get('first_name', 'مجهول')
            banned_until = u.get('banned_until', 0)
            
            if banned_until > 0:
                time_left = banned_until - now
                if time_left > 0:
                    days_left = time_left // 86400
                    if days_left > 0:
                        ban_info = f"{days_left} يوم"
                    else:
                        hours_left = time_left // 3600
                        ban_info = f"{hours_left} ساعة"
                else:
                    ban_info = "منتهي"
            else:
                ban_info = "دائم"
            
            banned_text += f"{i}. **{first_name}** (ID: {user_id})\n"
            banned_text += f"   👤 {username} | ⏰ {ban_info}\n\n"
        
        await update.message.reply_text(banned_text, reply_markup=admin_keyboard())
        
    except Exception as e:
        logger.error(f"خطأ في عرض المحظورين: {e}")
        await update.message.reply_text(
            "❌ **حدث خطأ في عرض المستخدمين المحظورين.**",
            reply_markup=admin_keyboard()
        )

# --- معالجة الرسائل الرئيسية المحسنة ---
async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
        
    user = update.effective_user
    text = update.message.text.strip()
    
    # التحقق من الاشتراك الإجباري
    if text not in ["/start", "/help", "/check_subscription"]:
        if not await check_channel_subscription(update, context):
            await must_subscribe(update, context)
            return
    
    # معالجة الأخطاء العامة
    try:
        await _relay_message_internal(update, context, user, text)
    except Exception as e:
        logger.error(f"خطأ في معالجة الرسالة: {e}")
        await update.message.reply_text(
            f"❌ **حدث خطأ في النظام.**\n\n"
            f"🔧 **يرجى إرسال /start لتحديث بياناتك**\n"
            f"💡 إذا استمر الخطأ، تواصل مع المشرف.",
            reply_markup=main_reply_keyboard(user.id in ADMIN_IDS)
        )

async def _relay_message_internal(update: Update, context: ContextTypes.DEFAULT_TYPE, user, text: str):
    # معالجة التقييمات
    if user.id in USER_STATES and USER_STATES[user.id] == 'waiting_for_rating':
        if '⭐ 1' in text:
            rating = 1
            USER_STATES.pop(user.id, None)
            await update.message.reply_text(
                f"⭐ **شكراً لتقييمك!** تم تسجيل {rating} نجوم.", 
                reply_markup=main_reply_keyboard(user.id in ADMIN_IDS)
            )
        elif '⭐⭐ 2' in text:
            rating = 2
            USER_STATES.pop(user.id, None)
            await update.message.reply_text(
                f"⭐⭐ **شكراً لتقييمك!** تم تسجيل {rating} نجوم.", 
                reply_markup=main_reply_keyboard(user.id in ADMIN_IDS)
            )
        elif '⭐⭐⭐ 3' in text:
            rating = 3
            USER_STATES.pop(user.id, None)
            await update.message.reply_text(
                f"⭐⭐⭐ **شكراً لتقييمك!** تم تسجيل {rating} نجوم.", 
                reply_markup=main_reply_keyboard(user.id in ADMIN_IDS)
            )
        elif '⭐⭐⭐⭐ 4' in text:
            rating = 4
            USER_STATES.pop(user.id, None)
            await update.message.reply_text(
                f"⭐⭐⭐⭐ **شكراً لتقييمك!** تم تسجيل {rating} نجوم.", 
                reply_markup=main_reply_keyboard(user.id in ADMIN_IDS)
            )
        elif '⭐⭐⭐⭐⭐ 5' in text:
            rating = 5
            USER_STATES.pop(user.id, None)
            await update.message.reply_text(
                f"⭐⭐⭐⭐⭐ **شكراً لتقييمك!** تم تسجيل {rating} نجوم.", 
                reply_markup=main_reply_keyboard(user.id in ADMIN_IDS)
            )
        elif 'تخطي' in text:
            USER_STATES.pop(user.id, None)
            await update.message.reply_text(
                "✅ **تم تخطي التقييم.**", 
                reply_markup=main_reply_keyboard(user.id in ADMIN_IDS)
            )
        return
    
    # معالجة رسائل المشرف من VIP
    if user.id in USER_STATES and USER_STATES[user.id] == 'waiting_admin_message':
        message = text
        USER_STATES.pop(user.id, None)
        
        # إرسال الرسالة للمشرفين
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"📩 **رسالة من VIP:**\n\n"
                         f"👤 **المستخدم:** {user.first_name} (ID: {user.id})\n"
                         f"💬 **الرسالة:** {message}\n\n"
                         f"📨 **للرد:** /reply {user.id} <الرسالة>"
                )
            except:
                pass
        
        await update.message.reply_text(
            "✅ **تم إرسال رسالتك للمشرف بنجاح.**\n\n"
            "👨‍💼 **سيتم الرد عليك في أقرب وقت.**",
            reply_markup=vip_keyboard()
        )
        return
    
    # معالجة اسم البلد المخصص
    if user.id in USER_STATES and USER_STATES[user.id] == 'waiting_country_name':
        db.update_user_profile(user.id, {'country': text})
        await update.message.reply_text(
            f"✅ **تم تحديث البلد إلى:** {text}",
            reply_markup=settings_keyboard(user.id)
        )
        USER_STATES.pop(user.id, None)
        return

    # معالجة حالات المستخدم
    if user.id in USER_STATES:
        state = USER_STATES[user.id]
        
        if state == 'waiting_gender_choice':
            await handle_gender_choice(update, context, text)
            return
            
        elif state == 'waiting_gender_confirm':
            await handle_gender_confirm(update, context, text)
            return
            
        elif state == 'waiting_gender_update':
            if text == '👦 ذكر':
                await handle_gender_update(update, context, 'ذكر')
            elif text == '👧 أنثى':
                await handle_gender_update(update, context, 'أنثى')
            elif text == '⬅️ رجوع':
                USER_STATES.pop(user.id, None)
                await update.message.reply_text("↩️ **تم الرجوع.**", reply_markup=settings_keyboard(user.id))
            return
            
        elif state == 'waiting_age_update':
            await handle_age_update(update, context, text)
            return
            
        elif state == 'waiting_country_update':
            if text != '⬅️ رجوع':
                await handle_country_update(update, context, text)
            else:
                USER_STATES.pop(user.id, None)
                await update.message.reply_text("↩️ **تم الرجوع.**", reply_markup=settings_keyboard(user.id))
            return
            
        elif state.startswith('playing_guess_'):
            await handle_guess_game(update, context, state, text)
            return

    # معالجة الأزرار الرئيسية
    if text == "🚀 بحث عشوائي":
        await start_search(update, context)
    elif text == "⚤ بحث بالجنس":
        await gender_search_entry(update, context)
    elif text == "🎩 حسابي":
        await profile_menu(update, context)
    elif text == "📄 ملفي الشخصي":
        await show_profile(update, context)
    elif text == "⚙️ إعدادات الملف":
        await settings_menu(update, context)
    elif text == "👫 الجنس" or text == "👫 الجنس (10 💰)":
        await update_gender(update, context)
    elif text == "🎂 العمر":
        await update_age(update, context)
    elif text == "📍 البلد":
        await update_country(update, context)
    elif text == "💰 كسب النقاط":
        await earn_points_menu(update, context)
    elif text == "📤 مشاركة الروابط":
        await share_links(update, context)
    elif text == "👥 إحالة أصدقاء":
        await invite_friends(update, context)
    elif text == "🎁 هدايا الأصدقاء":
        await friends_gifts_menu(update, context)
    elif text == "":
        await reward_handler(update, context)
    elif text == "🎮 الألعاب":
        await games_menu(update, context)
    elif text == "🎯 XO العشوائي":
        await xo_game_random(update, context)
    elif text == "  ":
        await guess_number_game(update, context)
    elif text == "🎰 لعبة الحظ":
        await update.message.reply_text("🎰 **لعبة الحظ قريباً...**", reply_markup=games_keyboard())
    elif text == "📊 إحصائيات":
        await stats_menu(update, context)
    elif text == "👥 المستخدمين":
        await show_users_stats(update, context)
    elif text == "🎯 النشاط":
        await show_activity_stats(update, context)
    elif text == "💰 النقاط":
        await show_points_stats(update, context)
    elif text == "⭐ النجوم":
        await show_stars_stats(update, context)
    elif text == "⭐ النجوم" and text != "⭐ النجوم":  # معالجة زر النجوم الرئيسي
        await stars_menu_main(update, context)
    elif text == "👑 VIP":
        await vip_menu(update, context)
    elif text == "🏆 المتصدرين":
        await leaderboard(update, context)
    elif text == "🛠️ لوحة المشرف":
        await admin_opener_handler(update, context)
    elif text == "⏹️ إيقاف البحث":
        await stop_search(update, context)
    elif text == "⬅️ الرئيسية":
        await update.message.reply_text("🏠 **القائمة الرئيسية**", 
                                      reply_markup=main_reply_keyboard(user.id in ADMIN_IDS))
    elif text == "⬅️ رجوع":
        await update.message.reply_text("↩️ **تم الرجوع.**", reply_markup=settings_keyboard(user.id))
    elif text == "👑 اشتراك VIP":
        await vip_purchase_menu(update, context)
    elif text == "⭐ VIP بالنجوم":
        await vip_stars_menu_main(update, context)
    elif text == "📞 تواصل مع المشرف":
        await vip_contact_admin(update, context)
    elif text in ['👦 ذكر', '👧 أنثى']:
        if USER_STATES.get(user.id) == 'waiting_gender_update':
            await handle_gender_update(update, context, 'ذكر' if 'ذكر' in text else 'أنثى')
    elif text in ['نعم ✅', 'لا ❌'] and USER_STATES.get(user.id) == 'waiting_gender_confirm':
        pass  # تمت المعالجة أعلاه
    elif text == "⏹️ إنهاء المحادثة":
        await stop_chat(update, context)
    elif text == "⭐ إضافة صديق":
        await add_friend(update, context)
    elif text == "📋 قائمة الأصدقاء":
        await friends_list(update, context)
    elif text == "💌 إرسال نقاط":
        await send_points_to_friend(update, context)
    elif text == "⭐ التقييم" and user.id in active_chats:
        await update.message.reply_text(
            "⭐ **كيف تقيم تجربة الدردشة مع الشريك؟**",
            reply_markup=rating_keyboard()
        )
        USER_STATES[user.id] = 'waiting_for_rating'
    elif text == "📊 الإحصائيات الكاملة":
        await admin_stats_full(update, context)
    elif text == "👥 المستخدمين المحظورين":
        await admin_banned_users(update, context)
    elif text == "💰 توزيع النقاط":
        await admin_distribute_points(update, context)
    elif text == "⭐ توزيع النجوم":
        await admin_distribute_stars(update, context)
    elif text == "📢 بث سريع":
        await admin_broadcast(update, context)
    elif text == "🔄 تحديث النظام":
        await admin_update_system(update, context)
    
    # معالجة المحادثات النشطة
    elif user.id in active_chats:
        await handle_chat_message(update, context)
    
    else:
        await update.message.reply_text(
            "🤔 **لم أفهم طلبك.**\n"
            "استخدم الأزرار للتفاعل مع البوت 🎮", 
            reply_markup=main_reply_keyboard(user.id in ADMIN_IDS)
        )

# --- معالجات المساعدة ---
async def handle_gender_choice(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    user = update.effective_user
    
    if text == '👦 ذكر':
        choice = 'ذكر'
    elif text == '👧 أنثى':
        choice = 'أنثى'
    elif text == 'إلغاء':
        USER_STATES.pop(user.id, None)
        await update.message.reply_text(
            "تم الإلغاء.",
            reply_markup=main_reply_keyboard(user.id in ADMIN_IDS)
        )
        return
    else:
        return
    
    GENDER_CONFIRM[user.id] = choice
    u = db.get_user(user.id)
    
    await update.message.reply_text(
        f"✅ **تم الاختيار:** {choice}\n"
        f"💰 **سيتم خصم:** {GENDER_SEARCH_COST} نقاط\n"
        f"💎 **رصيدك:** {u.get('points', 0)} نقطة\n\n"
        f"هل تريد المتابعة؟",
        reply_markup=ReplyKeyboardMarkup([['نعم ✅','لا ❌']], resize_keyboard=True)
    )
    USER_STATES[user.id] = 'waiting_gender_confirm'

async def handle_gender_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    user = update.effective_user
    
    if 'لا' in text or '❌' in text:
        GENDER_CONFIRM.pop(user.id, None)
        USER_STATES.pop(user.id, None)
        await update.message.reply_text("تم إلغاء البحث.", reply_markup=main_reply_keyboard(user.id in ADMIN_IDS))
        return
        
    if 'نعم' not in text and '✅' not in text:
        return
        
    choice = GENDER_CONFIRM.get(user.id)
    if not choice:
        USER_STATES.pop(user.id, None)
        await update.message.reply_text("لم يتم اختيار الجنس.", reply_markup=main_reply_keyboard(user.id in ADMIN_IDS))
        return
        
    u = db.get_user(user.id)
    if not u or u.get('points',0) < GENDER_SEARCH_COST:
        await update.message.reply_text("نقاطك غير كافية.", reply_markup=main_reply_keyboard(user.id in ADMIN_IDS))
        GENDER_CONFIRM.pop(user.id, None)
        USER_STATES.pop(user.id, None)
        return
        
    ok = db.consume_points(user.id, GENDER_SEARCH_COST)
    if not ok:
        await update.message.reply_text("فشل في خصم النقاط.", reply_markup=main_reply_keyboard(user.id in ADMIN_IDS))
        GENDER_CONFIRM.pop(user.id, None)
        USER_STATES.pop(user.id, None)
        return
    
    # البحث عن شريك بنفس الجنس
    db.set_user_status(user.id, "searching")
    await update.message.reply_text(
        "🔍 **جاري البحث عن شريك حسب الجنس...**\n"
        "⏳ **سيستمر البحث حتى تجد شريكاً**",
        reply_markup=search_cancel_keyboard()
    )
    
    # البحث في قاعدة البيانات
    partner = db.find_available_partner_by_gender(user.id, choice)
    if partner:
        # ربط المستخدمين
        active_chats[user.id] = partner['user_id']
        active_chats[partner['user_id']] = user.id
        
        db.set_user_status(user.id, "chatting")
        db.set_user_status(partner['user_id'], "chatting")
        
        conv_id = db.create_conversation(user.id, partner['user_id'])
        
        await update.message.reply_text(
            f"🎉 **تم العثور على شريك!**\n\n"
            f"👤 **معلومات الشريك:**\n"
            f"• **الاسم:** {partner.get('first_name', 'مستخدم')}\n"
            f"• **الجنس:** {partner.get('gender', 'غير محدد')}\n"
            f"• **العمر:** {partner.get('age', '—')}\n\n"
            f"💬 **اكتب له الآن للبدء بالدردشة!**",
            reply_markup=chat_control_keyboard()
        )
        
        try:
            user_info = db.get_user(user.id)
            user_name = user_info.get('first_name', 'مستخدم') if user_info else 'مستخدم'
            user_gender = user_info.get('gender', 'غير محدد') if user_info else 'غير محدد'
            
            await context.bot.send_message(
                chat_id=partner['user_id'],
                text=f"🎉 **تم العثور على شريك!**\n\n"
                     f"👤 **معلومات الشريك:**\n"
                     f"• **الاسم:** {user_name}\n"
                     f"• **الجنس:** {user_gender}\n\n"
                     f"💬 **اكتب له الآن للبدء بالدردشة!**",
                reply_markup=chat_control_keyboard()
            )
        except:
            pass
        
        await send_to_monitor(context, f"🟢 محادثة (جنس): {user.id} ↔ {partner['user_id']}")
    else:
        waiting_users.add(user.id)
    
    GENDER_CONFIRM.pop(user.id, None)
    USER_STATES.pop(user.id, None)

async def handle_guess_game(update: Update, context: ContextTypes.DEFAULT_TYPE, state: str, text: str):
    user = update.effective_user
    game_id = int(state.replace('playing_guess_', ''))
    
    game = game_manager.get_guess_game(game_id)
    if not game:
        await update.message.reply_text("❌ **اللعبة غير موجودة.**", reply_markup=games_keyboard())
        USER_STATES.pop(user.id, None)
        return
    
    try:
        guess = int(text)
        finished, message, points = game.guess(guess)
        
        if finished:
            if points != 0:
                if points > 0:
                    db.add_points(user.id, points)
                    result_type = "win"
                else:
                    # التأكد من أن المستخدم لديه نقاط كافية قبل الخصم
                    user_info = db.get_user(user.id)
                    current_points = user_info.get('points', 0) if user_info else 0
                    
                    if current_points >= abs(points):
                        db.consume_points(user.id, abs(points))
                        result_type = "lose"
                    else:
                        # إذا لم يكن لديه نقاط كافية، لا نخصم
                        message += f"\n\n⚠️ **لا يمكن خصم {abs(points)} نقاط لأن رصيدك {current_points} نقطة فقط.**"
                        points = 0
                        result_type = "lose_no_points"
                await update.message.reply_text(
                    f"{message}\n💰 **التغير في النقاط:** {points:+} نقطة 🌶️",
                    reply_markup=main_reply_keyboard(user.id in ADMIN_IDS)
                )
            else:
                await update.message.reply_text(
                    message,
                    reply_markup=main_reply_keyboard(user.id in ADMIN_IDS)
                )
            
            # تسجيل اللعبة في قاعدة البيانات
            db.create_game('guess', user.id)
            if points > 0:
                db.update_game_result(game_id, 'win', points, 0)
            elif points < 0:
                db.update_game_result(game_id, 'lose', points, 0)
            else:
                db.update_game_result(game_id, 'lose', 0, 0)
            
            game_manager.delete_guess_game(game_id)
            USER_STATES.pop(user.id, None)
            
        else:
            await update.message.reply_text(message)
            
    except ValueError:
        await update.message.reply_text("⚠️ **يرجى إدخال رقم صحيح بين 1 و 100:**")

# --- وظائف الأصدقاء ---
async def add_friend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إضافة صديق"""
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    user = update.effective_user
    await update.message.reply_text(
        "👤 **إضافة صديق**\n\n"
        "📝 **أدخل معرف صديقك:**\n"
        "مثال: 123456789"
    )
    USER_STATES[user.id] = 'waiting_for_friend_id'

async def friends_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """قائمة الأصدقاء"""
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    user = update.effective_user
    friends = db.get_user_friends(user.id)
    
    if not friends:
        await update.message.reply_text(
            "📋 **قائمة الأصدقاء فارغة.**\n\n"
            "👥 **استخدم زر '⭐ إضافة صديق' لإضافة أصدقاء.**",
            reply_markup=friends_keyboard()
        )
        return
    
    friends_text = "📋 **قائمة أصدقائك:**\n\n"
    
    for friend in friends:
        friend_id = friend.get('friend_id')
        friend_info = db.get_user(friend_id)
        if friend_info:
            name = friend_info.get('first_name', 'مستخدم')
            friends_text += f"👤 **{name}** (ID: {friend_id})\n"
    
    await update.message.reply_text(friends_text, reply_markup=friends_keyboard())

async def send_points_to_friend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال نقاط لصديق"""
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    user = update.effective_user
    await update.message.reply_text(
        "💰 **إرسال نقاط لصديق**\n\n"
        "📝 **أدخل معرف صديقك وعدد النقاط:**\n"
        "مثال: 123456789 50"
    )
    USER_STATES[user.id] = 'waiting_for_friend_points'

async def handle_friend_points(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """معالجة إرسال نقاط لصديق"""
    user = update.effective_user
    
    try:
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text(
                "❌ **صيغة غير صحيحة.**\n"
                "مثال: 123456789 50",
                reply_markup=friends_keyboard()
            )
            return
        
        friend_id = int(parts[0])
        points = int(parts[1])
        
        if points <= 0:
            await update.message.reply_text(
                "❌ **عدد النقاط يجب أن يكون أكبر من صفر.**",
                reply_markup=friends_keyboard()
            )
            return
        
        # التحقق من وجود الصديق
        friend = db.get_user(friend_id)
        if not friend:
            await update.message.reply_text(
                "❌ **المستخدم غير موجود.**",
                reply_markup=friends_keyboard()
            )
            return
        
        # التحقق من رصيد المستخدم
        u = db.get_user(user.id)
        if u.get('points', 0) < points:
            await update.message.reply_text(
                f"❌ **نقاطك غير كافية.**\n"
                f"💎 **رصيدك:** {u.get('points', 0)} نقطة\n"
                f"💰 **المطلوب:** {points} نقطة",
                reply_markup=friends_keyboard()
            )
            return
        
        # إرسال النقاط
        if db.send_gift(user.id, friend_id, points, "هدية نقاط من صديق"):
            await update.message.reply_text(
                f"✅ **تم إرسال {points} نقطة لصديقك بنجاح.**",
                reply_markup=friends_keyboard()
            )
        else:
            await update.message.reply_text(
                "❌ **فشل في إرسال النقاط.**",
                reply_markup=friends_keyboard()
            )
        
        USER_STATES.pop(user.id, None)
        
    except ValueError:
        await update.message.reply_text(
            "❌ **يرجى إدخال أرقام صحيحة.**\n"
            "مثال: 123456789 50",
            reply_markup=friends_keyboard()
        )
    except Exception as e:
        logger.error(f"خطأ في إرسال نقاط: {e}")
        await update.message.reply_text(
            "❌ **حدث خطأ في إرسال النقاط.**",
            reply_markup=friends_keyboard()
        )
        USER_STATES.pop(user.id, None)

# --- وظائف المشرفين الإضافية ---
async def admin_distribute_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """توزيع نقاط للمشرف"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ **ليس لديك صلاحية للوصول لهذه الصفحة.**")
        return
    
    await update.message.reply_text(
        "💰 **توزيع النقاط**\n\n"
        "📝 **أدخل معرف المستخدم وعدد النقاط:**\n"
        "مثال: 123456789 100\n\n"
        "💡 **للتوزيع الجماعي:**\n"
        "all 50 - يعطي 50 نقطة للجميع"
    )
    USER_STATES[user.id] = 'admin_distribute_points'

async def admin_distribute_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """توزيع نجوم للمشرف"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ **ليس لديك صلاحية للوصول لهذه الصفحة.**")
        return
    
    await update.message.reply_text(
        "⭐ **توزيع النجوم**\n\n"
        "📝 **أدخل معرف المستخدم وعدد النجوم:**\n"
        "مثال: 123456789 10\n\n"
        "💡 **للتوزيع الجماعي:**\n"
        "all 5 - يعطي 5 نجوم للجميع"
    )
    USER_STATES[user.id] = 'admin_distribute_stars'

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بث رسالة للمشرف"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ **ليس لديك صلاحية للوصول لهذه الصفحة.**")
        return
    
    await update.message.reply_text(
        "📢 **بث رسالة لجميع المستخدمين**\n\n"
        "💬 **اكتب الرسالة التي تريد بثها:**\n\n"
        "⚠️ **ملاحظة:** سيتم إرسال الرسالة لجميع المستخدمين المسجلين."
    )
    USER_STATES[user.id] = 'admin_broadcast'

async def admin_update_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحديث النظام للمشرف"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ **ليس لديك صلاحية للوصول لهذه الصفحة.**")
        return
    
    try:
        # تنظيف الموارد القديمة
        await cleanup_resources()
        
        # تحسين قاعدة البيانات
        db.optimize_database()
        
        await update.message.reply_text(
            "🔄 **تم تحديث النظام بنجاح!**\n\n"
            "✅ **الإجراءات المكتملة:**\n"
            "• تنظيف الموارد القديمة\n"
            "• تحسين قاعدة البيانات\n"
            "• إعادة تحميل الإعدادات\n\n"
            "✨ **النظام يعمل الآن بشكل أفضل.**",
            reply_markup=admin_keyboard()
        )
        
    except Exception as e:
        logger.error(f"خطأ في تحديث النظام: {e}")
        await update.message.reply_text(
            f"❌ **حدث خطأ في تحديث النظام:** {e}",
            reply_markup=admin_keyboard()
        )

# --- معالجة الرسائل من المشرفين ---
async def handle_admin_messages(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """معالجة رسائل المشرفين"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        return False
    
    if user.id in USER_STATES:
        state = USER_STATES[user.id]
        
        if state == 'admin_distribute_points':
            await handle_admin_distribute_points(update, context, text)
            return True
            
        elif state == 'admin_distribute_stars':
            await handle_admin_distribute_stars(update, context, text)
            return True
            
        elif state == 'admin_broadcast':
            await handle_admin_broadcast(update, context, text)
            return True
    
    return False

async def handle_admin_distribute_points(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """معالجة توزيع النقاط"""
    user = update.effective_user
    
    try:
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text(
                "❌ **صيغة غير صحيحة.**\n"
                "مثال: 123456789 100",
                reply_markup=admin_keyboard()
            )
            return
        
        target = parts[0]
        points = int(parts[1])
        
        if points <= 0:
            await update.message.reply_text(
                "❌ **عدد النقاط يجب أن يكون أكبر من صفر.**",
                reply_markup=admin_keyboard()
            )
            return
        
        if target.lower() == 'all':
            # توزيع على جميع المستخدمين
            all_users = db.list_all_users()
            count = 0
            
            for u in all_users:
                db.add_points(u['user_id'], points)
                count += 1
            
            await update.message.reply_text(
                f"✅ **تم توزيع {points} نقطة على {count} مستخدم.**",
                reply_markup=admin_keyboard()
            )
        else:
            # توزيع لمستخدم محدد
            target_id = int(target)
            target_user = db.get_user(target_id)
            
            if not target_user:
                await update.message.reply_text(
                    "❌ **المستخدم غير موجود.**",
                    reply_markup=admin_keyboard()
                )
                return
            
            db.add_points(target_id, points)
            await update.message.reply_text(
                f"✅ **تم إضافة {points} نقطة للمستخدم {target_user.get('first_name', 'مجهول')}.**",
                reply_markup=admin_keyboard()
            )
        
        USER_STATES.pop(user.id, None)
        
    except ValueError:
        await update.message.reply_text(
            "❌ **يرجى إدخال أرقام صحيحة.**\n"
            "مثال: 123456789 100",
            reply_markup=admin_keyboard()
        )
    except Exception as e:
        logger.error(f"خطأ في توزيع النقاط: {e}")
        await update.message.reply_text(
            f"❌ **حدث خطأ في توزيع النقاط:** {e}",
            reply_markup=admin_keyboard()
        )
        USER_STATES.pop(user.id, None)

async def handle_admin_distribute_stars(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """معالجة توزيع النجوم"""
    user = update.effective_user
    
    try:
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text(
                "❌ **صيغة غير صحيحة.**\n"
                "مثال: 123456789 10",
                reply_markup=admin_keyboard()
            )
            return
        
        target = parts[0]
        stars = int(parts[1])
        
        if stars <= 0:
            await update.message.reply_text(
                "❌ **عدد النجوم يجب أن يكون أكبر من صفر.**",
                reply_markup=admin_keyboard()
            )
            return
        
        if target.lower() == 'all':
            # توزيع على جميع المستخدمين
            all_users = db.list_all_users()
            count = 0
            
            for u in all_users:
                db.add_stars(u['user_id'], stars)
                count += 1
            
            await update.message.reply_text(
                f"✅ **تم توزيع {stars} نجمة على {count} مستخدم.**",
                reply_markup=admin_keyboard()
            )
        else:
            # توزيع لمستخدم محدد
            target_id = int(target)
            target_user = db.get_user(target_id)
            
            if not target_user:
                await update.message.reply_text(
                    "❌ **المستخدم غير موجود.**",
                    reply_markup=admin_keyboard()
                )
                return
            
            db.add_stars(target_id, stars)
            await update.message.reply_text(
                f"✅ **تم إضافة {stars} نجمة للمستخدم {target_user.get('first_name', 'مجهول')}.**",
                reply_markup=admin_keyboard()
            )
        
        USER_STATES.pop(user.id, None)
        
    except ValueError:
        await update.message.reply_text(
            "❌ **يرجى إدخال أرقام صحيحة.**\n"
            "مثال: 123456789 10",
            reply_markup=admin_keyboard()
        )
    except Exception as e:
        logger.error(f"خطأ في توزيع النجوم: {e}")
        await update.message.reply_text(
            f"❌ **حدث خطأ في توزيع النجوم:** {e}",
            reply_markup=admin_keyboard()
        )
        USER_STATES.pop(user.id, None)

async def handle_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """معالجة بث الرسالة"""
    user = update.effective_user
    
    try:
        # الحصول على جميع المستخدمين
        all_users = db.list_all_users()
        total = len(all_users)
        success = 0
        failed = 0
        
        await update.message.reply_text(
            f"📤 **جاري إرسال الرسالة لـ {total} مستخدم...**\n\n"
            f"💬 **الرسالة:** {text[:100]}..."
        )
        
        for u in all_users:
            try:
                await context.bot.send_message(
                    chat_id=u['user_id'],
                    text=f"📢 **إعلان من الإدارة:**\n\n{text}"
                )
                success += 1
                await asyncio.sleep(0.1)  # تجنب rate limit
            except Exception as e:
                failed += 1
                logger.error(f"فشل إرسال للمستخدم {u['user_id']}: {e}")
        
        await update.message.reply_text(
            f"✅ **تم الانتهاء من البث!**\n\n"
            f"📊 **النتائج:**\n"
            f"• ✅ الناجحة: {success}\n"
            f"• ❌ الفاشلة: {failed}\n"
            f"• 📊 الإجمالي: {total}",
            reply_markup=admin_keyboard()
        )
        
        USER_STATES.pop(user.id, None)
        
    except Exception as e:
        logger.error(f"خطأ في البث: {e}")
        await update.message.reply_text(
            f"❌ **حدث خطأ في البث:** {e}",
            reply_markup=admin_keyboard()
        )
        USER_STATES.pop(user.id, None)

# --- معالجة الوسائط ---
async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الوسائط في المحادثات"""
    user = update.effective_user
    uid = user.id
    
    if uid in active_chats:
        await handle_chat_message(update, context)

# --- معالجة الاستدعاءات ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة استدعاءات الإنلاين"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = query.from_user
    
    # معالجة VIP
    if data.startswith("vip_buy_"):
        try:
            days = int(data.split("_")[2])
            await handle_vip_purchase(update, context, days)
        except:
            await query.edit_message_text("❌ **خطأ في معالجة الطلب.**")
    
    elif data == "vip_stars_menu":
        await vip_stars_menu_main(update, context)
    
    elif data == "vip_back":
        await query.edit_message_text(
            "👑 **نظام VIP**\n\nاختر طريقة الاشتراك:",
            reply_markup=vip_keyboard()
        )
    
    # معالجة الاشتراك الإجباري
    elif data == "check_subscription":
        if await check_channel_subscription(update, context):
            await query.edit_message_text(
                "✅ **تم التحقق من الاشتراك بنجاح!**\n\n"
                "يمكنك الآن استخدام البوت.",
                reply_markup=main_reply_keyboard(user.id in ADMIN_IDS)
            )
        else:
            await query.edit_message_text(
                "❌ **لم يتم الاشتراك بعد.**\n\n"
                "يرجى الاشتراك في القناة أولاً.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 اضغط للاشتراك", url=f"https://t.me/{MANDATORY_CHANNEL.replace('@','')}")],
                    [InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_subscription")]
                ])
            )
    
    # معالجة ألعاب XO
    elif data.startswith("xo_"):
        await handle_xo_callback(update, context)
    
    # معالجة استدعاءات النجوم
    elif data.startswith("stars_") or data.startswith("buy_") or data.startswith("vip_stars_"):
        await handle_stars_callback_main(update, context)
    
    else:
        await query.edit_message_text("❌ **زر غير معروف.**")

# --- أوامر المشرفين ---
async def admin_broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بث رسالة من الأمر"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ **ليس لديك صلاحية لهذا الأمر.**")
        return
    
    if not context.args:
        await update.message.reply_text("⚠️ **طريقة الاستخدام:** /broadcast <الرسالة>")
        return
    
    message = " ".join(context.args)
    await handle_admin_broadcast(update, context, message)

async def admin_ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حظر مستخدم من الأمر"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ **ليس لديك صلاحية لهذا الأمر.**")
        return
    
    if len(context.args) < 3:
        await update.message.reply_text(
            "⚠️ **طريقة الاستخدام:** /ban <user_id> <السبب> <المدة بالأيام>\n\n"
            "📝 **مثال:** /ban 123456789 إساءة استخدام 7"
        )
        return
    
    try:
        target_id = int(context.args[0])
        reason = context.args[1]
        days = int(context.args[2])
        
        if days <= 0:
            await update.message.reply_text("❌ **المدة يجب أن تكون أكبر من صفر.**")
            return
        
        target_user = db.get_user(target_id)
        if not target_user:
            await update.message.reply_text("❌ **المستخدم غير موجود.**")
            return
        
        # حساب وقت انتهاء الحظر
        until_ts = now_ts() + (days * 86400)
        db.ban_user(target_id, until_ts)
        
        await update.message.reply_text(
            f"✅ **تم حظر المستخدم بنجاح.**\n\n"
            f"👤 **المستخدم:** {target_user.get('first_name', 'مجهول')}\n"
            f"📝 **السبب:** {reason}\n"
            f"⏰ **المدة:** {days} يوم\n"
            f"📅 **ينتهي في:** {readable(until_ts)}"
        )
        
        # إرسال إشعار للمستخدم المحظور
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"🚫 **تم حظر حسابك.**\n\n"
                     f"📝 **السبب:** {reason}\n"
                     f"⏰ **المدة:** {days} يوم\n"
                     f"📅 **ينتهي الحظر في:** {readable(until_ts)}\n\n"
                     f"📞 **للشكوى:** تواصل مع الإدارة."
            )
        except:
            pass
        
    except ValueError:
        await update.message.reply_text("❌ **يرجى إدخال أرقام صحيحة.**")
    except Exception as e:
        logger.error(f"خطأ في حظر المستخدم: {e}")
        await update.message.reply_text(f"❌ **حدث خطأ في الحظر:** {e}")

async def admin_unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء حظر مستخدم"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ **ليس لديك صلاحية لهذا الأمر.**")
        return
    
    if not context.args:
        await update.message.reply_text("⚠️ **طريقة الاستخدام:** /unban <user_id>")
        return
    
    try:
        target_id = int(context.args[0])
        target_user = db.get_user(target_id)
        
        if not target_user:
            await update.message.reply_text("❌ **المستخدم غير موجود.**")
            return
        
        db.unban_user(target_id)
        
        await update.message.reply_text(
            f"✅ **تم إلغاء حظر المستخدم بنجاح.**\n\n"
            f"👤 **المستخدم:** {target_user.get('first_name', 'مجهول')}"
        )
        
        # إرسال إشعار للمستخدم
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="✅ **تم إلغاء حظر حسابك.**\n\nيمكنك الآن استخدام البوت مرة أخرى."
            )
        except:
            pass
        
    except ValueError:
        await update.message.reply_text("❌ **يرجى إدخال رقم صحيح.**")
    except Exception as e:
        logger.error(f"خطأ في إلغاء الحظر: {e}")
        await update.message.reply_text(f"❌ **حدث خطأ في إلغاء الحظر:** {e}")

async def admin_add_points_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إضافة نقاط لمستخدم"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ **ليس لديك صلاحية لهذا الأمر.**")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("⚠️ **طريقة الاستخدام:** /addpoints <user_id> <العدد>")
        return
    
    try:
        target_id = int(context.args[0])
        points = int(context.args[1])
        
        if points <= 0:
            await update.message.reply_text("❌ **عدد النقاط يجب أن يكون أكبر من صفر.**")
            return
        
        target_user = db.get_user(target_id)
        if not target_user:
            await update.message.reply_text("❌ **المستخدم غير موجود.**")
            return
        
        db.add_points(target_id, points)
        
        await update.message.reply_text(
            f"✅ **تم إضافة {points} نقطة للمستخدم.**\n\n"
            f"👤 **المستخدم:** {target_user.get('first_name', 'مجهول')}\n"
            f"💰 **النقاط الجديدة:** {target_user.get('points', 0) + points}"
        )
        
    except ValueError:
        await update.message.reply_text("❌ **يرجى إدخال أرقام صحيحة.**")
    except Exception as e:
        logger.error(f"خطأ في إضافة النقاط: {e}")
        await update.message.reply_text(f"❌ **حدث خطأ في إضافة النقاط:** {e}")

async def admin_remove_points_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خصم نقاط من مستخدم"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ **ليس لديك صلاحية لهذا الأمر.**")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("⚠️ **طريقة الاستخدام:** /removepoints <user_id> <العدد>")
        return
    
    try:
        target_id = int(context.args[0])
        points = int(context.args[1])
        
        if points <= 0:
            await update.message.reply_text("❌ **عدد النقاط يجب أن يكون أكبر من صفر.**")
            return
        
        target_user = db.get_user(target_id)
        if not target_user:
            await update.message.reply_text("❌ **المستخدم غير موجود.**")
            return
        
        if target_user.get('points', 0) < points:
            await update.message.reply_text(
                f"❌ **نقاط المستخدم غير كافية.**\n"
                f"💎 **رصيده:** {target_user.get('points', 0)} نقطة"
            )
            return
        
        db.consume_points(target_id, points)
        
        await update.message.reply_text(
            f"✅ **تم خصم {points} نقطة من المستخدم.**\n\n"
            f"👤 **المستخدم:** {target_user.get('first_name', 'مجهول')}\n"
            f"💰 **النقاط المتبقية:** {target_user.get('points', 0) - points}"
        )
        
    except ValueError:
        await update.message.reply_text("❌ **يرجى إدخال أرقام صحيحة.**")
    except Exception as e:
        logger.error(f"خطأ في خصم النقاط: {e}")
        await update.message.reply_text(f"❌ **حدث خطأ في خصم النقاط:** {e}")

# --- إضافة دالة report_user المفقودة ---
async def report_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الإبلاغ عن مستخدم"""
    user = update.effective_user
    
    # التحقق من الاشتراك الإجباري
    if not await check_channel_subscription(update, context):
        await must_subscribe(update, context)
        return
    
    args = context.args
    
    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ **طريقة الاستخدام:**\n"
            "/report <معرف_المستخدم> <السبب>\n\n"
            "📝 **مثال:**\n"
            "/report 123456789 استخدام كلمات غير لائقة"
        )
        return
    
    try:
        reported_id = int(args[0])
        reason = " ".join(args[1:])
        
        # الحصول على معلومات المستخدم المبلغ عنه
        reported_user = db.get_user(reported_id)
        
        if not reported_user:
            await update.message.reply_text("❌ **المستخدم غير موجود.**")
            return
        
        if reported_id == user.id:
            await update.message.reply_text("❌ **لا يمكنك الإبلاغ عن نفسك.**")
            return
        
        # تسجيل البلاغ
        db.add_report(
            reporter_id=user.id,
            target_id=reported_id,
            reason=reason
        )
        
        # إرسال إشعار للمشرفين
        report_text = f"""
🚨 **تم الإبلاغ عن مستخدم جديد!**

👤 **المبلغ عنه:**
• **الاسم:** {reported_user.get('first_name', 'مستخدم')}
• **المعرف:** {reported_id}
• **اسم المستخدم:** @{reported_user.get('username', 'غير محدد')}

👥 **المبلغ:**
• **الاسم:** {user.first_name}
• **المعرف:** {user.id}

📝 **السبب:** {reason}
"""
        
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=report_text)
            except:
                pass
        
        await update.message.reply_text(
            "✅ **تم الإبلاغ عن المستخدم بنجاح.**\n\n"
            f"📝 **السبب:** {reason}\n\n"
            "👮 **سيقوم المشرف بمراجعة البلاغ في أسرع وقت.**"
        )
        
    except ValueError:
        await update.message.reply_text("❌ **معرف المستخدم يجب أن يكون رقماً.**")
    except Exception as e:
        logger.error(f"خطأ في الإبلاغ: {e}")
        await update.message.reply_text("❌ **حدث خطأ في تسجيل البلاغ.**")

# --- معالجات الدفع بالنجوم ---
async def pre_checkout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التحقق قبل الدفع"""
    if stars_system:
        await stars_system.pre_checkout_callback(update, context)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الدفع الناجح"""
    if stars_system:
        await stars_system.successful_payment(update, context)

# بناء التطبيق
def build_app():
    global stars_system
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    # تهيئة نظام النجوم
    
    try:
        stars_system = TelegramStarsPaymentSystem(db)
    except Exception as e:
        logger.error(f"فشل في تهيئة نظام النجوم: {e}")
        stars_system = None
    
    # الأوامر الأساسية
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("profile", show_profile))
    app.add_handler(CommandHandler("reward", reward_handler))
    app.add_handler(CommandHandler("report", report_user))
    app.add_handler(CommandHandler("stop", stop_chat))
    app.add_handler(CommandHandler("stop_search", stop_search))
    app.add_handler(CommandHandler("invite", invite_friends))
    
    # أوامر المشرفين
    app.add_handler(CommandHandler("broadcast", admin_broadcast_cmd))
    app.add_handler(CommandHandler("ban", admin_ban_cmd))
    app.add_handler(CommandHandler("unban", admin_unban_cmd))
    app.add_handler(CommandHandler("addpoints", admin_add_points_cmd))
    app.add_handler(CommandHandler("removepoints", admin_remove_points_cmd))
    
    # معالجات الرسائل النصية
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, relay_message))
    
    # معالجات الوسائط
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.VOICE | filters.AUDIO | filters.VIDEO_NOTE, 
        media_handler
    ))
    
    # معالجات الاستدعاء
    app.add_handler(CallbackQueryHandler(callback_handler))
    
    # معالجات الدفع بالنجوم
    if stars_system:
        app.add_handler(PreCheckoutQueryHandler(pre_checkout_callback))
        app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    
    # معالج الأخطاء
    app.add_error_handler(error_handler)
    
    return app

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    try:
        if update and isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "❌ **حدث خطأ في النظام.**\n\n"
                "🔧 **يرجى إرسال /start لتحديث بياناتك**\n"
                "💡 إذا استمر الخطأ، تواصل مع المشرف."
            )
        await context.bot.send_message(chat_id=OWNER_ID, text=f"⚠️ **خطأ في البوت:** {context.error}")
    except Exception:
        pass

async def cleanup_resources():
    """تنظيف الموارد القديمة"""
    current_time = time.time()
    
    # تنظيف الألعاب القديمة
    removed = game_manager.cleanup_old_games()
    if removed > 0:
        logger.info(f"تم تنظيف {removed} لعبة قديمة")
    
    # تنظيف حالات المستخدمين القديمة
    states_to_remove = []
    for user_id, state in USER_STATES.items():
        if state.startswith('waiting_') and user_id not in waiting_users and user_id not in active_chats:
            states_to_remove.append(user_id)
    
    for user_id in states_to_remove:
        USER_STATES.pop(user_id, None)
    
    # تنظيف عمليات البحث القديمة
    searches_to_remove = []
    for user_id, task in ACTIVE_SEARCHES.items():
        if task.done():
            searches_to_remove.append(user_id)
    
    for user_id in searches_to_remove:
        ACTIVE_SEARCHES.pop(user_id, None)
    
    # تنظيف المستخدمين المنتظرين الذين تجاوزوا الحد الزمني
    users_to_remove = []
    for uid in waiting_users:
        user = db.get_user(uid)
        if user and user.get('status') == 'searching':
            # إذا كان ينتظر أكثر من 5 دقائق
            if current_time - user.get('last_activity', current_time) > 300:
                users_to_remove.append(uid)
    
    for uid in users_to_remove:
        waiting_users.remove(uid)
        db.set_user_status(uid, "idle")
    
    logger.info(f"✅ تم تنظيف {len(states_to_remove)} حالة و {len(searches_to_remove)} بحث و {len(users_to_remove)} مستخدم")

# تشغيل البوت
if __name__ == "__main__":
    print("🚀 **بدء تشغيل بوت الدردشة المتقدم المحدث...**")
    
    # إنشاء ملف السجل
    logging.basicConfig(
        filename='bot.log',
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    # تشغيل تنظيف الموارد بشكل دوري
    async def periodic_cleanup():
        while True:
            await asyncio.sleep(300)  # كل 5 دقائق
            await cleanup_resources()
    
    app = build_app()
    
    print("✅ **البوت المحدث جاهز للعمل!**")
    print("✨ **المميزات الجديدة:**")
    print("• نظام نجوم تليجرام ⭐")
    print("• VIP بالنجوم 👑")
    print("• مكافآت ساعوية 🎯")
    print("• ألعاب متقدمة 🎮")
    print("• **لعبة XO العشوائية:** الفائز يكسب 5 نقاط من الخاسر")
    print("• **لعبة التخمين:** الفوز: +5 نقاط، الخسارة: -2 نقاط")
    print("• إصلاحات كاملة للأخطاء 🔧")
    
    app.run_polling()
#[file content end]
