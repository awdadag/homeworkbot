import os
import telebot
import requests
from telebot import types

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 6984430179
DG_API_KEY = "4f107268-001b-41d1-a84c-345fcded5ecb" # Твой ключ 2ГИС

if not TOKEN:
    raise SystemExit("Не найден BOT_TOKEN.")

bot = telebot.TeleBot(TOKEN)

# --- КЛАВИАТУРА (Только нужные кнопки) ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔍 Найти салоны без сайта"))
    return markup

@bot.message_handler(commands=["start"])
def cmd_start(message):
    # Удаляем старую клавиатуру принудительно
    msg = bot.send_message(message.chat.id, "Привет! Я бот-разведчик. Ищу салоны в Питере без сайтов.", reply_markup=main_menu())
    
@bot.message_handler(func=lambda m: m.text == "🔍 Найти салоны без сайта")
def find_salons(message):
    bot.send_message(message.chat.id, "🔎 Ищу салоны в Санкт-Петербурге...")
    
    url = "https://catalog.api.2gis.com/3.0/items"
    params = {
        "q": "Салоны красоты",
        "region_id": 38, 
        # ЗАПРАШИВАЕМ КОНТАКТЫ (phone, website, email и т.д.)
        "fields": "items.point,items.contact_groups,items.external_content,items.full_name,items.address_name", 
        "page_size": 10, 
        "key": DG_API_KEY
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        if "result" not in data or "items" not in data["result"]:
            bot.send_message(message.chat.id, "❌ Ничего не найдено.")
            return

        found_count = 0
        for item in data["result"]["items"]:
            name = item.get("full_name", "Без названия")
            
            # Проверка на сайт
            has_site = False
            external = item.get("external_content", [])
            for ext in external:
                if ext.get("type") == "website":
                    has_site = True
                    break
            
            if not has_site:
                found_count += 1
                
                # --- ИЩЕМ ТЕЛЕФОН В КОНТАКТАХ ---
                phone = "Не указан"
                contacts = item.get("contact_groups", [])
                for group in contacts:
                    if group.get("type") == "phone":
                        phone_list = group.get("contacts", [])
                        if phone_list:
                            phone = phone_list[0].get("value", "Не указан")
                            break
                
                address = item.get("address_name", "Адрес скрыт")
                
                # Вывод
                text = f"🏢 **{name}**\n📞 {phone}\n📍 {address}"
                bot.send_message(message.chat.id, text, parse_mode="Markdown")
        
        if found_count == 0:
            bot.send_message(message.chat.id, "Все найденные салоны уже имеют сайты.")
        else:
            bot.send_message(message.chat.id, f"✅ Найдено {found_count} салонов без сайта.")

    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Ошибка: {e}")

if __name__ == "__main__":
    print("Бот-разведчик запущен.")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
