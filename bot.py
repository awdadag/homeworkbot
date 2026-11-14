import os
import telebot
import requests
from telebot import types

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 6984430179  # Твой ID
DG_API_KEY = "4f107268-001b-41d1-a84c-345fcded5ecb" # Твой ключ 2ГИС

if not TOKEN:
    raise SystemExit("Не найден BOT_TOKEN.")

bot = telebot.TeleBot(TOKEN)

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔍 Найти салоны без сайта"))
    markup.add(types.KeyboardButton("📞 Мои контакты"), types.KeyboardButton("❓ Помощь"))
    return markup

@bot.message_handler(commands=["start"])
def cmd_start(message):
    bot.send_message(message.chat.id, "Привет! Я бот-разведчик. Я ищу салоны красоты в Питере, у которых НЕТ сайта. Тебе останется только написать им.", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "🔍 Найти салоны без сайта")
def find_salons(message):
    bot.send_message(message.chat.id, "🔎 Ищу салоны в Санкт-Петербурге... Это займет пару секунд.")
    
    # Запрос к API 2ГИС (Поиск по категории "Салоны красоты" в СПб)
    url = "https://catalog.api.2gis.com/3.0/items"
    params = {
        "q": "Салоны красоты",
        "region_id": 38, # ID региона для Санкт-Петербурга в 2ГИС
        "fields": "items.point,items.contact_groups,items.external_content,items.full_name",
        "page_size": 10, # Берем первые 10 для теста
        "key": DG_API_KEY
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        if "result" not in data or "items" not in data["result"]:
            bot.send_message(message.chat.id, "❌ Ничего не найдено или ошибка API.")
            return

        found_count = 0
        for item in data["result"]["items"]:
            name = item.get("full_name", "Без названия")
            
            # Проверяем, есть ли ссылка на сайт в external_content
            has_site = False
            external = item.get("external_content", [])
            for ext in external:
                if ext.get("type") == "website":
                    has_site = True
                    break
            
            # Если сайта нет - выводим контакт
            if not has_site:
                found_count += 1
                
                # Ищем телефон в контактах
                phone = "Телефон не указан"
                contacts = item.get("contact_groups", [])
                for group in contacts:
                    if group.get("type") == "phone":
                        phone = group["contacts"][0].get("value", "Не указан")
                        break
                
                # Адрес
                address = item.get("address_name", "Адрес скрыт")
                
                text = f"🏢 **{name}**\n📞 {phone}\n📍 {address}\n(Сайта нет)"
                bot.send_message(message.chat.id, text, parse_mode="Markdown")
        
        if found_count == 0:
            bot.send_message(message.chat.id, "Все найденные салоны уже имеют сайты. Попробуйте позже.")
        else:
            bot.send_message(message.chat.id, f"✅ Найдено {found_count} салонов без сайта. Напиши им!")

    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == "📞 Мои контакты")
def cmd_contacts(message):
    bot.send_message(message.chat.id, "Твоя ссылка для связи: https://t.me/HomeworkHelper_1bot")

@bot.message_handler(func=lambda m: m.text == "❓ Помощь")
def cmd_help(message):
    bot.send_message(message.chat.id, "Этот бот ищет салоны без сайтов. Нажми на кнопку 'Найти салоны', чтобы получить список.")

if __name__ == "__main__":
    print("Бот-разведчик запущен.")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
