#!/usr/bin/env python3
"""
🎯 بوت الدردشة العشوائية المتقدم مع نظام النجوم
✨ مميزات النظام:
• دردشة عشوائية مع أشخاص جدد
• نظام VIP بالنجوم مع ألقاب مميزة
• ألعاب XO مع مكافآت محسنة
• مكافآت يومية 3 نقاط كل ساعة
• إصلاح جميع الأخطاء السابقة
• دعم دفع النجوم الحقيقي
"""

import asyncio
import logging
import time
from bot_main import build_app

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global states (تتم مشاركتها مع bot_main.py)
USER_STATES = {}

async def cleanup_tasks():
    """تنظيف المهام القديمة بشكل دوري"""
    while True:
        try:
            # تنظيف حالات المستخدمين القديمة
            current_time = time.time()
            states_to_remove = []
            
            for user_id, state in USER_STATES.items():
                # تنظيف الحالات القديمة (أكثر من ساعة)
                if current_time - state.get('timestamp', 0) > 3600:
                    states_to_remove.append(user_id)
            
            for user_id in states_to_remove:
                USER_STATES.pop(user_id, None)
            
            logger.info(f"✅ تم تنظيف {len(states_to_remove)} حالة قديمة")
            
            # الانتظار قبل التنظيف التالي
            await asyncio.sleep(300)  # كل 5 دقائق
            
        except Exception as e:
            logger.error(f"❌ خطأ في تنظيف المهام: {e}")
            await asyncio.sleep(60)

async def main():
    """الدالة الرئيسية لتشغيل البوت"""
    try:
        print("=" * 50)
        print("🎯 بوت الدردشة العشوائية المتقدم مع نظام النجوم")
        print("✨ الإصدار: 3.0 | نظام النجوم المدمج")
        print("=" * 50)
        print("\n🚀 **جاري بدء التشغيل...**")
        
        # بناء التطبيق
        app = build_app()
        
        # بدء المهام الخلفية
        asyncio.create_task(cleanup_tasks())
        
        print("✅ **تم تهيئة النظام بنجاح!**")
        print("\n📱 **الأوامر المتاحة:**")
        print("/start - بدء استخدام البوت")
        print("/help - عرض المساعدة")
        print("/profile - عرض الملف الشخصي")
        print("/reward - الحصول على المكافأة")
        print("/report - الإبلاغ عن مستخدم")
        print("\n💎 **مميزات VIP بالنجوم:**")
        print("• يوم واحد: 10 ⭐")
        print("• يومين: 15 ⭐")
        print("• 3 أيام: 25 ⭐")
        print("• أسبوع: 40 ⭐")
        print("• أسبوعين: 70 ⭐")
        print("• شهر: 100 ⭐")
        print("\n💰 **VIP بالنقاط (أسعار مضاعفة):**")
        print("• يوم واحد: 100 🌶️")
        print("• يومين: 180 🌶️ (خصم 10%)")
        print("• 3 أيام: 255 🌶️ (خصم 15%)")
        print("• أسبوع: 560 🌶️ (خصم 20%)")
        print("• أسبوعين: 980 🌶️ (خصم 30%)")
        print("• شهر: 2100 🌶️ (خصم 30%)")
        
        print("\n🤖 **البوت يعمل الآن!**")
        print("💫 **للحصول على المساعدة:** @your_support")
        
        # تشغيل البوت
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        
        # الانتظار حتى يتم إيقاف البوت
        await asyncio.Event().wait()
        
    except KeyboardInterrupt:
        print("\n🛑 **تم إيقاف البوت بواسطة المستخدم.**")
    except Exception as e:
        logger.error(f"❌ خطأ في تشغيل البوت: {e}")
        print(f"\n❌ **حدث خطأ:** {e}")
        print("🔧 **جاري إعادة التشغيل تلقائياً خلال 10 ثواني...**")
        await asyncio.sleep(10)
        await main()
    finally:
        try:
            await app.stop()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(main())