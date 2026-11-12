import os
import sqlite3
import telebot
from telebot import types
from datetime import datetime, timedelta

# Токен и ID админа
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 6984430179

if not TOKEN:
    raise SystemExit("Не найден BOT_TOKEN.")

bot = telebot.TeleBot(TOKEN)

# ==========================================
# БАЗА ДАННЫХ
# ==========================================
conn = sqlite3.connect('booking.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    service TEXT,
    date TEXT,
    time TEXT
)''')
conn.commit()

# ==========================================
# НАСТРОЙКИ
# ==========================================
WORK_TIMES = ["10:00", "12:00", "14:00", "16:00", "18:00"]

# ==========================================
# КЛАВИАТУРЫ
# ==========================================
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("📝 Записаться"), types.KeyboardButton("📋 Мои записи"))
    markup.add(types.KeyboardButton("📞 Контакты"), types.KeyboardButton("❓ Помощь"))
    return markup

def services_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("💇 Стрижка"), types.KeyboardButton("💅 Маникюр"))
    markup.add(types.KeyboardButton("🦷 Стоматология"), types.KeyboardButton("🔙 Назад"))
    return markup

def dates_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    buttons = []
    for i in range(1, 8):
        date = datetime.now() + timedelta(days=i)
        date_str = date.strftime("%d.%m")
        buttons.append(types.KeyboardButton(date_str))
    markup.add(*buttons)
    markup.add(types.KeyboardButton("🔙 Назад"))
    return markup

# ==========================================
# ОСНОВНЫЕ ФУНКЦИИ
# ==========================================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    bot.send_message(message.chat.id, f"Привет, {message.from_user.first_name}!\nЭто бот для записи на услуги. Выбери действие:", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "❓ Помощь")
def cmd_help(message):
    bot.send_message(message.chat.id, "Этот бот помогает записаться на услуги.\n\nНажми «📝 Записаться», выбери услугу, введи имя, выбери дату и время.\n\nЕсли передумал — зайди в «📋 Мои записи» и отмени.")

@bot.message_handler(func=lambda m: m.text == "📞 Контакты")
def cmd_contacts(message):
    bot.send_message(message.chat.id, "Наш телефон: +7 (999) 123-45-67")

@bot.message_handler(func=lambda m: m.text == "📝 Записаться")
def start_booking(message):
    bot.send_message(message.chat.id, "Выбери услугу, на которую хочешь записаться:", reply_markup=services_menu())

@bot.message_handler(func=lambda m: m.text in ["💇 Стрижка", "💅 Маникюр", "🦷 Стоматология"])
def choose_service(message):
    bot.send_message(message.chat.id, f"Ты выбрал: {message.text}.\nТеперь напиши свое имя:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, get_name, message.text)

def get_name(message, service):
    user_name = message.text.strip()
    if user_name.startswith("/") or len(user_name) < 2 or "." in user_name:
        bot.send_message(message.chat.id, "❌ Пожалуйста, напиши свое настоящее имя:")
        bot.register_next_step_handler(message, get_name, service)
        return
    bot.send_message(message.chat.id, "Отлично! Выбери дату из списка ниже:", reply_markup=dates_menu())
    bot.register_next_step_handler(message, get_date, service, user_name)

def get_date(message, service, user_name):
    date = message.text
    if date == "🔙 Назад":
        start_booking(message)
        return
    if len(date) > 5 or "." not in date:
        bot.send_message(message.chat.id, "❌ Пожалуйста, выбери дату именно из кнопок ниже:", reply_markup=dates_menu())
        bot.register_next_step_handler(message, get_date, service, user_name)
        return

    # Блокировка времени глобально для этой услуги
    cursor.execute("SELECT time FROM bookings WHERE date = ? AND service = ?", (date, service))
    busy_times = [row[0] for row in cursor.fetchall()]
    free_times = [t for t in WORK_TIMES if t not in busy_times]
    
    if not free_times:
        bot.send_message(message.chat.id, f"❌ На {date} на услугу {service} все места заняты.", reply_markup=dates_menu())
        bot.register_next_step_handler(message, get_date, service, user_name)
        return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    markup.add(*[types.KeyboardButton(t) for t in free_times])
    markup.add(types.KeyboardButton("🔙 Назад"))
    bot.send_message(message.chat.id, f"Свободное время на {date}:", reply_markup=markup)
    bot.register_next_step_handler(message, save_booking, service, user_name, date)

def save_booking(message, service, user_name, date):
    time = message.text
    if time == "🔙 Назад":
        start_booking(message)
        return
    if time not in WORK_TIMES:
        bot.send_message(message.chat.id, "❌ Пожалуйста, выбери время из кнопок.")
        get_date(message, service, user_name)
        return
        
    cursor.execute("SELECT id FROM bookings WHERE date = ? AND time = ? AND service = ?", (date, time, service))
    if cursor.fetchone():
        bot.send_message(message.chat.id, "❌ Упс! Это время только что заняли.", reply_markup=dates_menu())
        get_date(message, service, user_name)
        return
    
    cursor.execute("INSERT INTO bookings (user_id, username, service, date, time) VALUES (?, ?, ?, ?, ?)",
                   (message.from_user.id, user_name, service, date, time))
    conn.commit()
    
    bot.send_message(message.chat.id, f"✅ Запись создана!\nУслуга: {service}\nИмя: {user_name}\nДата: {date}\nВремя: {time}\n\nМы вас ждем!", reply_markup=main_menu())
    
    try:
        bot.send_message(ADMIN_ID, f"🔔 НОВАЯ ЗАПИСЬ!\nКлиент: {user_name}\nУслуга: {service}\nДата: {date}\nВремя: {time}")
    except Exception:
        pass

# ==========================================
# МОИ ЗАПИСИ И ОТМЕНА КЛИЕНТОМ
# ==========================================
@bot.message_handler(func=lambda m: m.text == "📋 Мои записи")
def show_bookings(message):
    cursor.execute("SELECT id, service, date, time FROM bookings WHERE user_id = ?", (message.from_user.id,))
    rows = cursor.fetchall()
    
    if not rows:
        bot.send_message(message.chat.id, "У тебя пока нет записей.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for row in rows:
        # row[0] - id, row[1] - service, row[2] - date, row[3] - time
        text = f"❌ Отменить: {row[1]} {row[2]} в {row[3]}"
        markup.add(types.InlineKeyboardButton(text, callback_data=f"userdel_{row[0]}"))
    
    bot.send_message(message.chat.id, "Твои записи (нажми, чтобы отменить):", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('userdel_'))
def user_cancel_booking(call):
    booking_id = call.data.split('_')[1]
    
    # Получаем данные записи перед удалением
    cursor.execute("SELECT user_id, username, service, date, time FROM bookings WHERE id = ?", (booking_id,))
    row = cursor.fetchone()
    
    # Проверяем, что клиент отменяет именно СВОЮ запись
    if row and row[0] == call.from_user.id:
        username, service, date, time = row[1], row[2], row[3], row[4]
        
        cursor.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        conn.commit()
        
        bot.answer_callback_query(call.id, "Запись отменена!")
        bot.edit_message_text(f"✅ Ты отменил запись:\n{service} на {date} в {time}.", call.message.chat.id, call.message.message_id)
        
        # УВЕДОМЛЕНИЕ АДМИНУ ОБ ОТМЕНЕ
        try:
            bot.send_message(ADMIN_ID, f"⚠️ КЛИЕНТ ОТМЕНИЛ ЗАПИСЬ!\nКлиент: {username}\nУслуга: {service}\nДата: {date}\nВремя: {time}")
        except Exception:
            pass
    else:
        bot.answer_callback_query(call.id, "Ошибка: это не твоя запись.")

@bot.message_handler(func=lambda m: m.text == "🔙 Назад")
def back_to_main(message):
    bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_menu())

# ==========================================
# ЗАПУСК
# ==========================================
if __name__ == "__main__":
    print("Бот запущен.")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
