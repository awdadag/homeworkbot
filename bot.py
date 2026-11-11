import os
from dotenv import load_dotenv
import telebot
from telebot import types
import telebot.apihelper

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise SystemExit("Не найден BOT_TOKEN")

# =========================================================
# ПРИНУДИТЕЛЬНОЕ ПОДКЛЮЧЕНИЕ ПО IP (в обход DNS-блокировки)
# =========================================================
telebot.apihelper.API_URL = "https://149.154.167.220/bot{0}/{1}"

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=["start"])
def cmd_start(message):
    bot.send_message(message.chat.id, "Привет! Я бот для помощи с домашними заданиями.\nНапиши /help, чтобы узнать команды.")

@bot.message_handler(commands=["help"])
def cmd_help(message):
    bot.send_message(message.chat.id, "Доступные команды:\n/start — запустить бота\n/help — показать помощь\n/menu — главное меню")

@bot.message_handler(commands=["menu"])
def cmd_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Мои задания"), types.KeyboardButton("Напоминания"), types.KeyboardButton("Помощь"))
    bot.send_message(message.chat.id, "Главное меню:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "Мои задания")
def btn_tasks(message):
    bot.send_message(message.chat.id, "Здесь позже будет список твоих заданий.")

@bot.message_handler(func=lambda m: m.text == "Напоминания")
def btn_reminders(message):
    bot.send_message(message.chat.id, "Здесь позже будут напоминания.")

@bot.message_handler(func=lambda m: m.text == "Помощь")
def btn_help(message):
    cmd_help(message)

@bot.message_handler(func=lambda m: True)
def fallback(message):
    bot.send_message(message.chat.id, "Не понял. Напиши /help.")

if __name__ == "__main__":
    print("Бот запущен. Нажми Ctrl+C для остановки.")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)