#[file name]: config.py
#[file content begin]
"""
⚙️ ملف إعدادات البوت
"""

import os
from datetime import timedelta

# 🔐 التوكنات والمفاتيح
BOT_TOKEN = "8221859242:AAHrIxpZW4RVCcb32NGFXgfRPLkQo4Pzzbg"
STARS_PROVIDER_TOKEN = "284685063:TEST:YzZmZjMxNWE5ZGIz"  # TEST token للنجوم

# 👑 المشرفين
OWNER_ID = 7834574830
ADMIN_IDS = {OWNER_ID}

# 📢 القنوات
MANDATORY_CHANNEL = "@NN26S"  # قناة الاشتراك الإجباري
MONITOR_CHANNEL = "@-1003463880550"
DATA_CHANNEL = "-1003378437796"

# 🗄️ قاعدة البيانات
DB_PATH = "bot_data.sqlite"

# ⚙️ إعدادات النظام
REWARD_POINTS = 3  # نقاط المكافأة الساعوية
REWARD_COOLDOWN = 3600  # ثانية (ساعة واحدة)

# 💰 التكاليف
GENDER_SEARCH_COST = 3  # نقاط للبحث حسب الجنس
GENDER_CHANGE_COST = 10  # نقاط لتغيير الجنس

# 🎮 إعدادات الألعاب
XO_WIN_POINTS = 5  # نقاط للفوز في XO (يكسبها من الخاسر)
XO_LOSS_POINTS = 5  # نقاط يخسرها الخاسر في XO
XO_DRAW_POINTS = 0  # نقاط في حالة التعادل

GUESS_WIN_POINTS = 5  # نقاط للفوز في لعبة التخمين
GUESS_LOSS_POINTS = 2  # نقاط يخسرها في لعبة التخمين

# 👑 باقات VIP بالنجوم (الأسعار القديمة)
VIP_PACKAGES = {
    'vip_1_day': {
        'name': '💎 VIP ليوم واحد',
        'description': 'اشتراك VIP ليوم واحد مع جميع المميزات',
        'price': 10,  # 10 نجمة
        'days': 1,
        'title': '💎 عضو مميز'
    },
    'vip_2_days': {
        'name': '⭐ VIP ليومين',
        'description': 'اشتراك VIP ليومين مع جميع المميزات',
        'price': 15,  # 15 نجمة
        'days': 2,
        'title': '⭐ عضو VIP'
    },
    'vip_3_days': {
        'name': '✨ VIP لـ3 أيام',
        'description': 'اشتراك VIP لـ3 أيام مع جميع المميزات',
        'price': 25,  # 25 نجمة
        'days': 3,
        'title': '✨ عضو بلاتينيوم'
    },
    'vip_1_week': {
        'name': '🔥 VIP لأسبوع',
        'description': 'اشتراك VIP لأسبوع مع جميع المميزات',
        'price': 40,  # 40 نجمة
        'days': 7,
        'title': '🔥 عضو VIP برو'
    },
    'vip_2_weeks': {
        'name': '👑 VIP لأسبوعين',
        'description': 'اشتراك VIP لأسبوعين مع جميع المميزات',
        'price': 70,  # 70 نجمة
        'days': 14,
        'title': '👑 عضو بلاتينيوم برو'
    },
    'vip_1_month': {
        'name': '🚀 VIP لشهر كامل',
        'description': 'اشتراك VIP لشهر كامل مع جميع المميزات',
        'price': 100,  # 100 نجمة
        'days': 30,
        'title': '🚀 عضو ماسي'
    }
}

# 🚫 الكلمات المحظورة
FILTERED_WORDS = {
    "سكس", "طيز", "خنزير", "فحش", "عارية", "شرموطة", 
    "زنا", "زاني", "دعارة", "قحبة", "عاهرة", "منيوك"
}

# 📊 إعدادات التسجيل
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = "bot.log"

# 🎯 إعدادات المطابقة
MAX_SEARCH_TIME = 300  # 5 دقائق كحد أقصى للبحث
MAX_CHAT_TIME = 3600  # ساعة كحد أقصى للمحادثة
XO_SEARCH_TIMEOUT = 60  # 60 ثانية للبحث عن خصم XO

# 💰 أسعار VIP بالنقاط (المضاعفة)
VIP_POINTS_PRICES = {
    1: 100,   # يوم واحد
    2: 180,   # يومين (خصم 10%)
    3: 255,   # 3 أيام (خصم 15%)
    7: 560,   # أسبوع (خصم 20%)
    14: 980,  # أسبوعين (خصم 30%)
    30: 2100  # شهر (خصم 30%)
}

def get_config():
    """الحصول على إعدادات التكوين"""
    return {
        'bot_token': BOT_TOKEN,
        'stars_provider_token': STARS_PROVIDER_TOKEN,
        'owner_id': OWNER_ID,
        'admin_ids': ADMIN_IDS,
        'mandatory_channel': MANDATORY_CHANNEL,
        'monitor_channel': MONITOR_CHANNEL,
        'data_channel': DATA_CHANNEL,
        'db_path': DB_PATH,
        'reward_points': REWARD_POINTS,
        'reward_cooldown': REWARD_COOLDOWN,
        'gender_search_cost': GENDER_SEARCH_COST,
        'gender_change_cost': GENDER_CHANGE_COST,
        'xo_win_points': XO_WIN_POINTS,
        'xo_loss_points': XO_LOSS_POINTS,
        'xo_draw_points': XO_DRAW_POINTS,
        'guess_win_points': GUESS_WIN_POINTS,
        'guess_loss_points': GUESS_LOSS_POINTS,
        'vip_packages': VIP_PACKAGES,
        'vip_points_prices': VIP_POINTS_PRICES,
        'filtered_words': FILTERED_WORDS,
        'log_level': LOG_LEVEL,
        'log_format': LOG_FORMAT,
        'log_file': LOG_FILE,
        'max_search_time': MAX_SEARCH_TIME,
        'max_chat_time': MAX_CHAT_TIME,
        'xo_search_timeout': XO_SEARCH_TIMEOUT
    }
#[file content end]