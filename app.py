import os
import sqlite3
import threading
import datetime
import uuid
from flask import Flask
from telebot import TeleBot, types

app = Flask(__name__)

BOT_TOKEN = '7823644703:AAHxf9L9eB7x3lvRV5a_xe_56GWgyP3ZIj8'  # Replace with your Telegram Bot Token
ADMIN_ID = 6324825537  # Replace with your Telegram Admin User ID

bot = TeleBot(BOT_TOKEN)

# Database setup
DB_FILE = 'database.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            premium_until TEXT DEFAULT NULL,
            redeem_used INTEGER DEFAULT 0,
            is_banned BOOLEAN DEFAULT FALSE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS keys (
            key TEXT PRIMARY KEY,
            days INTEGER,
            used BOOLEAN DEFAULT FALSE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            name TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    # Initialize free_unlimited if not set
    cursor.execute("INSERT OR IGNORE INTO settings (name, value) VALUES ('free_unlimited', 'False')")
    conn.commit()
    conn.close()

init_db()

# Helper functions
def is_admin(user_id):
    return user_id == ADMIN_ID

def is_premium(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT premium_until FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result and result[0]:
        premium_until = datetime.datetime.fromisoformat(result[0])
        return datetime.datetime.now() < premium_until
    return False

def get_redeem_used(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT redeem_used FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def increment_redeem_used(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET redeem_used = redeem_used + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def is_free_unlimited():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE name = 'free_unlimited'")
    result = cursor.fetchone()
    conn.close()
    return result[0] == 'True' if result else False

def set_free_unlimited(value):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET value = ? WHERE name = 'free_unlimited'", ('True' if value else 'False',))
    conn.commit()
    conn.close()

def add_user_if_not_exists(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def is_banned(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else False

def set_banned(user_id, banned):
    add_user_if_not_exists(user_id)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (banned, user_id))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results]

# Bot handlers
@bot.message_handler(commands=['start'])
def handle_start(message):
    add_user_if_not_exists(message.from_user.id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('/redeem')
    btn2 = types.KeyboardButton('/premium')
    markup.add(btn1, btn2)
    bot.send_message(message.chat.id, "Welcome To Aizen Bot ⚡️\nPlease Use this /redeem Command For Get Prime video 🧑‍💻 For Premium use This Command /premium", reply_markup=markup)

@bot.message_handler(commands=['redeem'])
def handle_redeem(message):
    user_id = message.from_user.id
    add_user_if_not_exists(user_id)
    if is_banned(user_id):
        bot.reply_to(message, "You are banned from using this bot.")
        return
    if is_premium(user_id) or is_free_unlimited() or get_redeem_used(user_id) == 0:
        # Forward the entire message to admin
        bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
        bot.reply_to(message, "processing")
        if not is_premium(user_id):
            increment_redeem_used(user_id)
    else:
        bot.reply_to(message, "please Purchase Premium Key For Use 🗝️")

@bot.message_handler(commands=['premium'])
def handle_premium(message):
    user_id = message.from_user.id
    add_user_if_not_exists(user_id)
    try:
        key = message.text.split()[1]
    except IndexError:
        bot.reply_to(message, "Please provide a key: /premium <key>")
        return
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT days, used FROM keys WHERE key = ?", (key,))
    result = cursor.fetchone()
    if result and not result[1]:
        days = result[0]
        premium_until = (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat()
        cursor.execute("UPDATE users SET premium_until = ? WHERE user_id = ?", (premium_until, user_id))
        cursor.execute("UPDATE keys SET used = TRUE WHERE key = ?", (key,))
        conn.commit()
        bot.reply_to(message, "Premium Activated ⚡️")
        bot.send_message(ADMIN_ID, f"User {user_id} has activated premium for {days} days using key {key}")
    else:
        bot.reply_to(message, "Invalid or already used key.")
    conn.close()

@bot.message_handler(commands=['genk'])
def handle_genk(message):
    if not is_admin(message.from_user.id):
        return
    try:
        days = int(message.text.split()[1])
    except (IndexError, ValueError):
        bot.reply_to(message, "Usage: /genk <days>")
        return
    key = str(uuid.uuid4())
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO keys (key, days) VALUES (?, ?)", (key, days))
    conn.commit()
    conn.close()
    bot.reply_to(message, f"Generated key for {days} days: {key}")

@bot.message_handler(commands=['broadcast'])
def handle_broadcast(message):
    if not is_admin(message.from_user.id):
        return
    text = message.text[11:].strip()  # Remove /broadcast
    if not text:
        bot.reply_to(message, "Usage: /broadcast <message>")
        return
    users = get_all_users()
    for user_id in users:
        try:
            bot.send_message(user_id, text)
        except:
            pass  # Skip if can't send (blocked or error)
    bot.reply_to(message, "Broadcast sent.")

@bot.message_handler(commands=['ban'])
def handle_ban(message):
    if not is_admin(message.from_user.id):
        return
    try:
        user_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        bot.reply_to(message, "Usage: /ban <user_id>")
        return
    set_banned(user_id, True)
    bot.reply_to(message, f"User {user_id} banned.")

@bot.message_handler(commands=['unban'])
def handle_unban(message):
    if not is_admin(message.from_user.id):
        return
    try:
        user_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        bot.reply_to(message, "Usage: /unban <user_id>")
        return
    set_banned(user_id, False)
    bot.reply_to(message, f"User {user_id} unbanned.")

@bot.message_handler(commands=['on'])
def handle_on(message):
    if not is_admin(message.from_user.id):
        return
    set_free_unlimited(True)
    bot.reply_to(message, "Free unlimited redeem activated.")

@bot.message_handler(commands=['off'])
def handle_off(message):
    if not is_admin(message.from_user.id):
        return
    set_free_unlimited(False)
    bot.reply_to(message, "Free unlimited redeem deactivated.")

# Handle personal replies from admin
@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.reply_to_message)
def handle_admin_reply(message):
    if message.reply_to_message.forward_from:
        user_id = message.reply_to_message.forward_from.id
        try:
            bot.send_message(user_id, message.text)
        except:
            bot.reply_to(message, "Failed to send reply to user.")

# Run bot polling in a thread
def run_bot():
    bot.infinity_polling(non_stop=True)

threading.Thread(target=run_bot).start()

# Flask route to keep alive
@app.route('/')
def home():
    return "Bot is running"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
