import telebot
from telebot import types
import time
import sqlite3
import schedule
import threading
from datetime import datetime

# 🔑 PUT YOUR BOT TOKEN HERE
TOKEN = "8273793653:AAEPXeyeYaLONA65H00FuqV-WEdgG0zy7cs"
bot = telebot.TeleBot(TOKEN)

# ================= DATABASE =================
conn = sqlite3.connect("tasks.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    user_id INTEGER,
    task_name TEXT,
    start_time INTEGER,
    end_time INTEGER,
    date TEXT
)
""")
conn.commit()

# Active task storage (RAM)
active_task = {}

# ================= BUTTONS =================
def main_menu():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("➕ New Task", "▶️ Start Task")
    keyboard.add("⏹ Stop Task")
    keyboard.add("📊 Today Stats")
    return keyboard

# ================= START =================
@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "👋 Task Tracker Bot\n\nTrack your tasks and time easily.",
        reply_markup=main_menu()
    )

# ================= NEW TASK =================
@bot.message_handler(func=lambda m: m.text == "➕ New Task")
def new_task(message):
    bot.send_message(message.chat.id, "✍️ Send task name:")
    bot.register_next_step_handler(message, save_task_name)

def save_task_name(message):
    active_task[message.chat.id] = {
        "name": message.text,
        "start": None
    }
    bot.send_message(
        message.chat.id,
        f"✅ Task '{message.text}' saved.\nPress ▶️ Start Task"
    )

# ================= START TASK =================
@bot.message_handler(func=lambda m: m.text == "▶️ Start Task")
def start_task(message):
    user_id = message.chat.id

    if user_id not in active_task or active_task[user_id]["start"] is not None:
        bot.send_message(user_id, "❌ Create a task first.")
        return

    active_task[user_id]["start"] = int(time.time())
    bot.send_message(user_id, "▶️ Task started.")

# ================= STOP TASK =================
@bot.message_handler(func=lambda m: m.text == "⏹ Stop Task")
def stop_task(message):
    user_id = message.chat.id

    if user_id not in active_task or active_task[user_id]["start"] is None:
        bot.send_message(user_id, "❌ No active task.")
        return

    start_time = active_task[user_id]["start"]
    end_time = int(time.time())
    task_name = active_task[user_id]["name"]
    date = datetime.now().strftime("%Y-%m-%d")

    cursor.execute(
        "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
        (user_id, task_name, start_time, end_time, date)
    )
    conn.commit()

    duration_minutes = (end_time - start_time) // 60
    del active_task[user_id]

    bot.send_message(
        user_id,
        f"⏹ Task stopped: {task_name}\n⏱ Duration: {duration_minutes} minutes"
    )

# ================= TODAY STATS =================
@bot.message_handler(func=lambda m: m.text == "📊 Today Stats")
def today_stats(message):
    user_id = message.chat.id
    today = datetime.now().strftime("%Y-%m-%d")

    cursor.execute(
        "SELECT task_name, start_time, end_time FROM tasks WHERE user_id=? AND date=?",
        (user_id, today)
    )
    rows = cursor.fetchall()

    if not rows:
        bot.send_message(user_id, "📭 No tasks today.")
        return

    text = f"📊 Today ({today})\n\n"
    total_minutes = 0

    for task, start, end in rows:
        minutes = (end - start) // 60
        total_minutes += minutes
        text += f"✅ {task} — {minutes} min\n"

    text += f"\n⏱ Total time: {total_minutes} minutes"
    bot.send_message(user_id, text)

# ================= DAILY REPORT =================
def daily_report():
    today = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("SELECT DISTINCT user_id FROM tasks")
    users = cursor.fetchall()

    for (user_id,) in users:
        cursor.execute(
            "SELECT start_time, end_time FROM tasks WHERE user_id=? AND date=?",
            (user_id, today)
        )
        rows = cursor.fetchall()

        total = sum((end - start) // 60 for start, end in rows)

        bot.send_message(
            user_id,
            f"🌙 Daily Report\n\n"
            f"📅 Date: {today}\n"
            f"✅ Tasks done: {len(rows)}\n"
            f"⏱ Total time: {total} minutes"
        )

# Schedule daily report at 23:59
schedule.every().day.at("23:59").do(daily_report)

def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

threading.Thread(target=run_schedule, daemon=True).start()

# ================= RUN BOT =================
bot.infinity_polling()
