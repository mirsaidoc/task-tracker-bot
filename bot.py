import telebot
from telebot import types
import time
import sqlite3
import schedule
import threading
from datetime import datetime
import os

# ================= BOT TOKEN =================
TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# ================= DATABASE =================
conn = sqlite3.connect("tasks.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    user_id INTEGER,
    username TEXT,
    task_name TEXT,
    start_time INTEGER,
    end_time INTEGER,
    duration INTEGER,
    date TEXT
)
""")
conn.commit()

# ================= MEMORY =================
active_task = {}

# ================= BUTTONS =================
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ New Task", "▶️ Start Task")
    kb.add("⏹ Stop Task")
    kb.add("📊 My Today Stats")
    kb.add("🌍 Global Today Stats")
    return kb

# ================= START =================
@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "👋 Task Focus Tracker\n\nTrack focus time and see group stats.",
        reply_markup=main_menu()
    )

# ================= NEW TASK =================
@bot.message_handler(func=lambda m: m.text == "➕ New Task")
def new_task(message):
    bot.send_message(message.chat.id, "✍️ Send task name:")
    bot.register_next_step_handler(message, save_task)

def save_task(message):
    active_task[message.chat.id] = {
        "name": message.text,
        "start": None
    }
    bot.send_message(message.chat.id, "✅ Task saved. Press ▶️ Start Task")

# ================= START TASK =================
@bot.message_handler(func=lambda m: m.text == "▶️ Start Task")
def start_task(message):
    user_id = message.chat.id

    if user_id not in active_task or active_task[user_id]["start"] is not None:
        bot.send_message(user_id, "❌ Create a task first.")
        return

    active_task[user_id]["start"] = int(time.time())
    bot.send_message(user_id, "▶️ Task started. Focus time running...")

# ================= STOP TASK =================
@bot.message_handler(func=lambda m: m.text == "⏹ Stop Task")
def stop_task(message):
    user_id = message.chat.id
    username = message.from_user.username or message.from_user.first_name

    if user_id not in active_task or active_task[user_id]["start"] is None:
        bot.send_message(user_id, "❌ No active task.")
        return

    start_time = active_task[user_id]["start"]
    end_time = int(time.time())
    duration = (end_time - start_time) // 60
    task_name = active_task[user_id]["name"]
    date = datetime.now().strftime("%Y-%m-%d")

    cursor.execute(
        "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, username, task_name, start_time, end_time, duration, date)
    )
    conn.commit()

    del active_task[user_id]

    bot.send_message(
        user_id,
        f"⏹ Task stopped\n\n"
        f"📝 Task: {task_name}\n"
        f"⏱ Focus time: {duration} min"
    )

# ================= MY TODAY STATS =================
@bot.message_handler(func=lambda m: m.text == "📊 My Today Stats")
def my_today_stats(message):
    user_id = message.chat.id
    today = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT task_name, duration
        FROM tasks
        WHERE user_id = ? AND date = ?
    """, (user_id, today))

    rows = cursor.fetchall()

    if not rows:
        bot.send_message(user_id, "📭 No tasks today.")
        return

    text = f"📊 My Stats ({today})\n\n"
    total = 0

    for task, duration in rows:
        total += duration
        text += f"• {task} — {duration} min\n"

    text += f"\n⏱ Total focus: {total} min"
    bot.send_message(user_id, text)

# ================= GLOBAL TODAY STATS =================
@bot.message_handler(func=lambda m: m.text == "🌍 Global Today Stats")
def global_today_stats(message):
    today = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT username, task_name, duration
        FROM tasks
        WHERE date = ?
        ORDER BY username
    """, (today,))

    rows = cursor.fetchall()

    if not rows:
        bot.send_message(message.chat.id, "📭 No activity today.")
        return

    text = f"🌍 Global Focus Stats ({today})\n\n"
    users = {}

    for username, task, duration in rows:
        users.setdefault(username, []).append((task, duration))

    for username, tasks in users.items():
        total = sum(d for _, d in tasks)
        text += f"👤 @{username}\n"
        for task, duration in tasks:
            text += f"  • {task} — {duration} min\n"
        text += f"  ⏱ Total: {total} min\n\n"

    bot.send_message(message.chat.id, text)

# ================= DAILY AUTO REPORT =================
def daily_report():
    today = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("SELECT DISTINCT user_id FROM tasks")
    users = cursor.fetchall()

    for (user_id,) in users:
        cursor.execute("""
            SELECT duration FROM tasks
            WHERE user_id = ? AND date = ?
        """, (user_id, today))

        rows = cursor.fetchall()
        total = sum(d[0] for d in rows)

        bot.send_message(
            user_id,
            f"🌙 Daily Summary\n\n"
            f"📅 {today}\n"
            f"✅ Tasks done: {len(rows)}\n"
            f"⏱ Focus time: {total} min"
        )

schedule.every().day.at("23:59").do(daily_report)

def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

threading.Thread(target=run_schedule, daemon=True).start()

# ================= RUN =================
bot.infinity_polling()
