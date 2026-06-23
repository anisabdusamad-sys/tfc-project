"""
╔════════════════════════════════════════════════════════════╗
║  INSTAGRAM VIDEO DOWNLOADER - БЕ АККАУНТ                  ║
║  Озод ва Public бо API                                    ║
╚════════════════════════════════════════════════════════════╝
"""

import logging
import os
import requests
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import json

# ═════════════════════════════════════════════════════════════
# ПАРАМЕТРҲО
# ═════════════════════════════════════════════════════════════

BOT_TOKEN = "8955716993:AAF3ukjFlSZYwyb77aQwP0phKTSPQNOcmdw"  # @BotFather дан ёфт

# ═════════════════════════════════════════════════════════════
# ЛОГИ
# ═════════════════════════════════════════════════════════════

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════════
# КЛАСИ DOWNLOADER (БЕ АККАУНТ!)
# ═════════════════════════════════════════════════════════════

class InstagramDownloaderAPI:
    """Instagram Downloader - БЕ LOGIN"""
    
    def __init__(self):
        """Инициализатсия"""
        self.downloads_dir = "downloads"
        
        # Дорайи боргирӣ
        if not os.path.exists(self.downloads_dir):
            os.makedirs(self.downloads_dir)
        
        logger.info("✅ Бот ба API вомунди аст (БЕ АККАУНТ!)")
    
    # ═════════════════════════════════════════════════════════
    # API METHOD 1: igsave.com
    # ═════════════════════════════════════════════════════════
    
    def download_from_igsave(self, url: str) -> tuple:
        """igsave API-ро истифода баред"""
        try:
            logger.info("🔗 igsave API-ро кӯшиш мекунем...")
            
            response = requests.post(
                "https://api.igsave.com/v1/info",
                json={"url": url},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Видеоро чак кунед
                if data.get('videos'):
                    video_url = data['videos'][0]['url']
                    
                    logger.info(f"✅ igsave: Видео URL ёфт шуд")
                    return video_url, "igsave"
                
                # Аксро чак кунед
                if data.get('images'):
                    image_url = data['images'][0]['url']
                    logger.info(f"✅ igsave: Сурат ёфт шуд (видео нест)")
                    return None, "image"
        
        except Exception as e:
            logger.error(f"❌ igsave ройгон: {str(e)}")
        
        return None, None
    
    # ═════════════════════════════════════════════════════════
    # API METHOD 2: saveig.app
    # ═════════════════════════════════════════════════════════
    
    def download_from_saveig(self, url: str) -> tuple:
        """saveig.app API-ро истифода баред"""
        try:
            logger.info("🔗 saveig API-ро кӯшиш мекунем...")
            
            response = requests.post(
                "https://saveig.app/api/saveinsta",
                data={"url": url},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'ok':
                    # Видеоро чак кунед
                    if data.get('videos'):
                        video_url = data['videos'][0]['url']
                        logger.info(f"✅ saveig: Видео URL ёфт шуд")
                        return video_url, "saveig"
        
        except Exception as e:
            logger.error(f"❌ saveig ройгон: {str(e)}")
        
        return None, None
    
    # ═════════════════════════════════════════════════════════
    # API METHOD 3: rapidapi (Ҳисоб лозим!)
    # ═════════════════════════════════════════════════════════
    
    def download_from_rapidapi(self, url: str) -> tuple:
        """RapidAPI-ро истифода баред (озад)"""
        try:
            logger.info("🔗 RapidAPI-ро кӯшиш мекунем...")
            
            # ОЗАДИ API (3 мартаба дар рӯз)
            response = requests.get(
                f"https://instagram-downloader-download-videos.p.rapidapi.com/index",
                params={"url": url},
                headers={
                    "x-rapidapi-key": "demo",  # Demo key
                    "x-rapidapi-host": "instagram-downloader-download-videos.p.rapidapi.com"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('media'):
                    video_url = data['media'][0]['url']
                    logger.info(f"✅ RapidAPI: Видео URL ёфт шуд")
                    return video_url, "rapidapi"
        
        except Exception as e:
            logger.error(f"❌ RapidAPI ройгон: {str(e)}")
        
        return None, None
    
    # ═════════════════════════════════════════════════════════
    # EXTRACT POST ID
    # ═════════════════════════════════════════════════════════
    
    def extract_post_id(self, url: str) -> str:
        """Post ID-ро бикашед"""
        try:
            patterns = [
                r'/p/([A-Za-z0-9_-]+)',
                r'/reel/([A-Za-z0-9_-]+)',
                r'/tv/([A-Za-z0-9_-]+)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)
            
            return None
        
        except Exception as e:
            logger.error(f"❌ ID extract: {str(e)}")
            return None
    
    # ═════════════════════════════════════════════════════════
    # MAIN DOWNLOAD METHOD
    # ═════════════════════════════════════════════════════════
    
    def download_video(self, url: str) -> tuple:
        """Видеоро боргирӣ кунед (БЕ АККАУНТ!)"""
        try:
            logger.info(f"📥 Видео боргирӣ: {url[:50]}...")
            
            # ID чак
            post_id = self.extract_post_id(url)
            if not post_id:
                return None, "❌ Post ID ёфт нашуд. Пайванд дуруст аст?"
            
            logger.info(f"🔍 Post ID: {post_id}")
            
            # API-ҳоро тартибан кӯшиш кунед
            apis = [
                self.download_from_igsave,
                self.download_from_saveig,
                self.download_from_rapidapi,
            ]
            
            for api_func in apis:
                video_url, source = api_func(url)
                
                if video_url:
                    # Видеоро боргирӣ кунед
                    logger.info(f"⬇️ Видео боргирӣ мешавад ({source})...")
                    
                    video_data = requests.get(video_url, timeout=15)
                    
                    if video_data.status_code == 200:
                        # Файлро сохт кунед
                        file_path = os.path.join(
                            self.downloads_dir,
                            f"video_{post_id}.mp4"
                        )
                        
                        with open(file_path, 'wb') as f:
                            f.write(video_data.content)
                        
                        file_size = len(video_data.content) / (1024 * 1024)
                        logger.info(f"✅ Видео боргирифта шуд! ({file_size:.2f} MB)")
                        
                        return file_path, f"✅ Видео боргирифта шуд! ({file_size:.2f} MB)"
            
            return None, "❌ Видео боргирӣ нашуд. Дуборҳ кӯшиш кунед."
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Download: {error_msg}")
            return None, f"❌ Хатогӣ: {error_msg[:100]}"
    
    # ═════════════════════════════════════════════════════════
    # CHECK LINK
    # ═════════════════════════════════════════════════════════
    
    def is_instagram_link(self, text: str) -> bool:
        """Оё Instagram пайванд аст"""
        return "instagram.com" in text or "instagr.am" in text

# ═════════════════════════════════════════════════════════════
# ГЛОБАЛ ОБЪЕКТ
# ═════════════════════════════════════════════════════════════

bot = InstagramDownloaderAPI()

# ═════════════════════════════════════════════════════════════
# TELEGRAM HANDLERS
# ═════════════════════════════════════════════════════════════

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ҳангоми шуруъ"""
    welcome_text = """
🎬 **INSTAGRAM VIDEO DOWNLOADER** 🎬
✨ *БЕ АККАУНТ - ОЗОД!* ✨

Салом! Ман ботҳои боргирӣ видеои инстаграм ҳастам.
**Аккаунт лозим НЕ АСТА!**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 **ФАРМАНҲО:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎥 Аспӣ пайванд фиристед
   → Видео боргирӣ мешавад!

/help - Маълумоти бештар

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 **МИСОЛ:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

https://www.instagram.com/p/ABC1234567/

https://www.instagram.com/reel/XYZ7890/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ **БЕ АККАУНТ!**
✅ **ОЗОД!**
✅ **ПУБЛИК!**
"""
    
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кӯмак"""
    help_text = """
❓ **КӮМАК:**

📥 **Чӣ кунҷ:**
1. Пайванди видеои инстаграмро фиристед
2. Монатақанӣ интизор бошед
3. Видео баргирифта шавад ✅

⚙️ **Қобилият:**
✅ Reels
✅ Posts (видео)
✅ TV
✅ Carousel (видеоҳо)

❌ **Кор намекунад:**
❌ Stories
❌ DM
❌ Суратҳо

🔐 **Амнон:**
✅ БЕ АККАУНТ!
✅ БЕ ЛОГИН!
✅ ОЗОД!

💡 **Сүрӣ:**
- Пайванди публик истифода баред
- Видео Instagram-и худ бошад
"""
    
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Паёмҳоро тammолли кунед"""
    user_text = update.message.text
    
    # Агар пайванд аст
    if bot.is_instagram_link(user_text):
        msg = await update.message.reply_text(
            "⏳ Видео боргирӣ мешавад...\n\n"
            "(⏱ Монатақанӣ интизор бошед, API нармтар аст)"
        )
        
        # Боргирӣ
        video_path, status = bot.download_video(user_text)
        
        if video_path and os.path.exists(video_path):
            try:
                with open(video_path, 'rb') as video_file:
                    await update.message.reply_video(
                        video=video_file,
                        caption="✅ Видео бомуваффақӣ боргирифта шуд!"
                    )
                
                os.remove(video_path)
                await msg.delete()
                
            except Exception as e:
                await msg.edit_text(f"❌ Фиристодан ройгон: {str(e)[:100]}")
        else:
            await msg.edit_text(status)
    
    else:
        await update.message.reply_text(
            "❌ Ин Instagram пайванд нест\n\n"
            "Пайванди инстаграмро фиристед ё /help гуед"
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Хатогиҳо"""
    logger.error(f"❌ Ошибка: {context.error}")

# ═════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════

def main():
    """Ботро оғоз кунед"""
    
    print("""
    ╔════════════════════════════════════════════════╗
    ║   INSTAGRAM BOT (БЕ АККАУНТ!)                 ║
    ║   Озод ва Public API                          ║
    ╚════════════════════════════════════════════════╝
    """)
    
    # Барнамаро сохт кунед
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Фарманҳо
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    
    # Паёмҳо
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    # Хатогиҳо
    app.add_error_handler(error_handler)
    
    # ОҒОЗ!
    print("✅ БОТ ВОҚЕФ ШУД!")
    print("🚀 POLLING ОҒОЗ МЕШАВАД...")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("\n📝 ОГОҲӢ:")
    print("⚡ БЕ АККАУНТ!")
    print("⚡ ОЗОД!")
    print("⚡ API-ҳо истифода мешавад")
    print("\n")
    
    app.run_polling()

# ═════════════════════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()