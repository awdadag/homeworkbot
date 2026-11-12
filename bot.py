import os
import sqlite3
import telebot
from telebot import types

# Токен берется из переменных окружения (Bothost)
TOKEN = os.getenv("BOT_TOKEN")
# Твой ID для уведомлений
ADMIN_ID = 6984430179

if not TOKEN:
    raise SystemExit("Не найден BOT_TOKEN. Проверь переменные в Bothost.")

bot = telebot.TeleBot(TOKEN)

# ==========================================
# БАЗА ДАННЫХ (SQLite)
# ==========================================
conn = sqlite3.connect('booking.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    service TEXT,
    date_time TEXT
)''')
conn.commit()

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

# ==========================================
# КОМАНДЫ И КНОПКИ
# ==========================================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    bot.send_message(message.chat.id, f"Привет, {message.from_user.first_name}!\nЭто бот для записи на услуги. Выбери действие:", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "❓ Помощь")
def cmd_help(message):
    bot.send_message(message.chat.id, "Этот бот помогает записаться на услуги.\n\nНажми «📝 Записаться», выбери услугу, введи имя и время.\n\nПосле записи тебе придет уведомление.")

@bot.message_handler(func=lambda m: m.text == "📞 Контакты")
def cmd_contacts(message):
    bot.send_message(message.chat.id, "Наш телефон: +7 (999) 123-45-67\nНаш адрес: г. Москва, ул. Пушкина, д. 10")

@bot.message_handler(func=lambda m: m.text == "📝 Записаться")
def start_booking(message):
    bot.send_message(message.chat.id, "Выбери услугу, на которую хочешь записаться:", reply_markup=services_menu())

@bot.message_handler(func=lambda m: m.text in ["💇 Стрижка", "💅 Маникюр", "🦷 Стоматология"])
def choose_service(message):
    bot.send_message(message.chat.id, f"Ты выбрал: {message.text}.\nТеперь напиши свое имя:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, get_name, message.text)

def get_name(message, service):
    user_name = message.text
    bot.send_message(message.chat.id, "Отлично! Теперь напиши желаемую дату и время (например: 25.10 в 15:00):")
    bot.register_next_step_handler(message, get_date_time, service, user_name)

def get_date_time(message, service, user_name):
    date_time = message.text
    
    # Сохраняем в базу данных
    cursor.execute("INSERT INTO bookings (user_id, username, service, date_time) VALUES (?, ?, ?, ?)",
                   (message.from_user.id, user_name, service, date_time))
    conn.commit()
    
    bot.send_message(message.chat.id, f"✅ Запись создана!\nУслуга: {service}\nИмя: {user_name}\nВремя: {date_time}\n\nМы вас ждем!", reply_markup=main_menu())
    
    # Отправляем уведомление админу
    try:
        bot.send_message(ADMIN_ID, f"🔔 НОВАЯ ЗАПИСЬ!\nКлиент: {user_name} (ID: {message.from_user.id})\nУслуга: {service}\nВремя: {date_time}")
    except Exception as e:
        print(f"Ошибка отправки админу: {e}")

@bot.message_handler(func=lambda m: m.text == "📋 Мои записи")
def show_bookings(message):
    cursor.execute("SELECT service, date_time FROM bookings WHERE user_id = ?", (message.from_user.id,))
    rows = cursor.fetchall()
    
    if not rows:
        bot.send_message(message.chat.id, "У тебя пока нет записей.")
        return
    
    text = "Твои записи:\n\n"
    for row in rows:
        text += f"• {row[0]} — {row[1]}\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "🔙 Назад")
def back_to_main(message):
    bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_menu())

# ==========================================
# ЗАПУСК
# ==========================================
if __name__ == "__main__":
    print("Бот запущен. Нажми Ctrl+C для остановки.")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
