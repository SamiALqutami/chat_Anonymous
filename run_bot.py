import asyncio
import logging
import sys
from bot_main import build_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def start_logic():
    while True: # حيلة التكرار اللانهائي داخل الكود
        try:
            app = build_app()
            await app.initialize()
            await app.start()
            # drop_pending_updates=True ضرورية جداً عند إعادة التشغيل المتكرر
            await app.updater.start_polling(drop_pending_updates=True)
            
            # انتظر للأبد حتى يتم إيقاف البوت من قبل timeout في YAML
            while True:
                await asyncio.sleep(3600)
                
        except Exception as e:
            logger.error(f"حدث خطأ، إعادة المحاولة بعد 10 ثوانٍ: {e}")
            await asyncio.sleep(10) # انتظر قليلاً قبل المحاولة مجدداً

if __name__ == "__main__":
    try:
        asyncio.run(start_logic())
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
