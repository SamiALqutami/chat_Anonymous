#!/usr/bin/env python3
"""
🎯 بوت الدردشة العشوائية المتقدم - نسخة MongoDB السحابية
✨ تم التحديث ليعمل مع GitHub Actions بشكل مستمر وبدون فقدان بيانات.
"""

import asyncio
import logging
import os
import sys
from bot_main import build_app

# إعداد التسجيل (Logging) - تم تعديله ليرسل السجلات لشاشة GitHub Actions مباشرة
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout) # عرض السجلات في الـ Console لسهولة المراقبة
    ]
)
logger = logging.getLogger(__name__)

async def main():
    """الدالة الرئيسية لتشغيل البوت بنظام السحاب"""
    try:
        print("=" * 50)
        print("🚀 بدء تشغيل البوت بنظام MongoDB السحابي")
        print("⚙️ النظام: GitHub Actions Continuous Deployment")
        print("=" * 50)
        
        # التأكد من وجود المتغيرات الأساسية
        if not os.getenv('BOT_TOKEN'):
            print("❌ خطأ: BOT_TOKEN غير موجود في Secrets!")
            return
        if not os.getenv('MONGO_URI'):
            print("❌ خطأ: MONGO_URI غير موجود في Secrets!")
            return

        # بناء التطبيق (يتم استدعاء Database() داخل build_app تلقائياً)
        app = build_app()
        
        print("\n✅ تم الاتصال بقاعدة البيانات السحابية.")
        print("🤖 البوت جاهز الآن لاستقبال الرسائل...")
        
        # تهيئة وتشغيل البوت
        await app.initialize()
        await app.start()
        
        # drop_pending_updates=True تجعل البوت يتجاهل الرسائل التي أُرسلت أثناء توقفه
        # وهذا يمنع "انفجار" الرسائل عند إعادة التشغيل التلقائي كل 4 ساعات
        await app.updater.start_polling(drop_pending_updates=True)
        
        print("\n✨ البوت يعمل الآن بأقصى سرعة!")
        
        # الحفاظ على الجلسة حية
        stop_event = asyncio.Event()
        await stop_event.wait()
        
    except Exception as e:
        logger.error(f"❌ خطأ فادح في التشغيل: {e}")
        # في بيئة GitHub Actions، نفضل الخروج ليقوم الـ Workflow بإعادة التشغيل
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 تم إيقاف التشغيل.")
 
