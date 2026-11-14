import os
import telebot
import requests
from telebot import types

TOKEN = os.getenv("BOT_TOKEN")
DG_API_KEY = "4f107268-001b-41d1-a84c-345fcded5ecb"

if not TOKEN:
    raise SystemExit("Не найден BOT_TOKEN.")

bot = telebot.TeleBot(TOKEN)

current_page = 1
current_query = "Салоны красоты"
region_id = 38 # Питер

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔍 Выбрать нишу"), types.KeyboardButton("🔄 Сбросить поиск"))
    return markup

def niches_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("💇 Салоны красоты"), types.KeyboardButton("✂️ Барбершопы"))
    markup.add(types.KeyboardButton("🦷 Стоматологии"), types.KeyboardButton("🚗 Автосервисы"))
    markup.add(types.KeyboardButton("☕ Кофейни"), types.KeyboardButton("🏋️ Фитнес-залы"))
    markup.add(types.KeyboardButton("🔙 Назад"))
    return markup

@bot.message_handler(commands=["start"])
def cmd_start(message):
    global current_page, current_query
    current_page = 1
    current_query = "Салоны красоты"
    bot.send_message(message.chat.id, "Привет! Я бот-разведчик. Выбери нишу, чтобы найти бизнесы без сайтов в Питере.", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "🔍 Выбрать нишу")
def choose_niche(message):
    bot.send_message(message.chat.id, "Выбери, кого искать:", reply_markup=niches_menu())

@bot.message_handler(func=lambda m: m.text == "🔙 Назад")
def back_to_main(message):
    bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "🔄 Сбросить поиск")
def reset_search(message):
    global current_page
    current_page = 1
    bot.send_message(message.chat.id, f"Поиск по '{current_query}' сброшен.", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text in ["💇 Салоны красоты", "✂️ Барбершопы", "🦷 Стоматологии", "🚗 Автосервисы", "☕ Кофейни", "🏋️ Фитнес-залы"])
def set_niche(message):
    global current_query, current_page
    current_query = message.text.split(" ", 1)[1]
    current_page = 1
    bot.send_message(message.chat.id, f"Выбрано: {current_query}. Ищу...", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("🔍 Найти")))
    find_salons(message)

@bot.message_handler(func=lambda m: m.text == "🔍 Найти")
def find_salons_handler(message):
    find_salons(message)

def find_salons(message):
    global current_page, current_query, region_id
    
    bot.send_message(message.chat.id, f"🔎 Ищу '{current_query}' в Санкт-Петербурге (страница {current_page})...")
    
    url = "https://catalog.api.2gis.com/3.0/items"
    params = {
        "q": current_query,
        "region_id": region_id, 
        "fields": "items.contact_groups,items.external_content,items.full_name,items.address_name,items.point,items.links", 
        "page": current_page,
        "page_size": 10,
        "key": DG_API_KEY
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        if "result" not in data or "items" not in data["result"]:
            bot.send_message(message.chat.id, "❌ Ошибка API или результаты закончились.", reply_markup=main_menu())
            current_page = 1
            return

        found_count = 0
        for item in data["result"]["items"]:
            name = item.get("full_name", "Без названия")
            
            has_site = False
            
            # 1. Проверка external_content (с защитой от строк)
            external = item.get("external_content", [])
            if isinstance(external, list):
                for ext in external:
                    if isinstance(ext, dict) and ext.get("type") == "website":
                        has_site = True
                        break
            
            # 2. Проверка links (с защитой от строк)
            links = item.get("links", [])
            if isinstance(links, list):
                for link in links:
                    if isinstance(link, dict) and link.get("type") == "website":
                        has_site = True
                        break
                    
            # 3. Проверка contact_groups (с защитой от строк)
            contacts = item.get("contact_groups", [])
            if isinstance(contacts, list):
                for group in contacts:
                    if isinstance(group, dict) and group.get("type") == "website":
                        has_site = True
                        break
                    
            if not has_site:
                found_count += 1
                
                item_id = item.get("id", "")
                dgis_link = f"https://2gis.ru/spb/firm/{item_id}"
                address = item.get("address_name", "Адрес скрыт")
                
                text = f"🏢 **{name}**\n📍 {address}\n\n_Нажми на кнопку ниже, чтобы открыть контакты в 2ГИС_"
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("📞 Контакты в 2ГИС", url=dgis_link))
                
                bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup, disable_web_page_preview=True)
        
        if found_count == 0:
            bot.send_message(message.chat.id, f"На странице {current_page} все имеют сайты. Листаем дальше...")
            current_page += 1
            find_salons(message)
        else:
            bot.send_message(message.chat.id, f"✅ Найдено {found_count} на странице {current_page}. Нажми «Найти» для следующей.", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("🔍 Найти")).add(types.KeyboardButton("🔍 Выбрать нишу")))
            current_page += 1
            
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Ошибка: {e}", reply_markup=main_menu())

if __name__ == "__main__":
    print("Бот-разведчик запущен.")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
