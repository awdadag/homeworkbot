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
current_query = "Салоны красоты" # По умолчанию
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

# Обработка выбора ниши
@bot.message_handler(func=lambda m: m.text in ["💇 Салоны красоты", "✂️ Барбершопы", "🦷 Стоматологии", "🚗 Автосервисы", "☕ Кофейни", "🏋️ Фитнес-залы"])
def set_niche(message):
    global current_query, current_page
    current_query = message.text.split(" ", 1)[1] # Убираем эмодзи
    current_page = 1
    bot.send_message(message.chat.id, f"Выбрано: {current_query}. Нажми «Найти», чтобы начать поиск.", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("🔍 Найти")))
    
    # Автоматически начинаем поиск сразу после выбора
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
        "fields": "items.contact_groups,items.external_content,items.full_name,items.address_name,items.point", 
        "page": current_page,
        "page_size": 10,
        "key": DG_API_KEY
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        if "result" not in data or "items" not in data["result"]:
            bot.send_message(message.chat.id, "❌ Ошибка API или результаты закончились. Попробуй сбросить поиск.", reply_markup=main_menu())
            current_page = 1
            return

        found_count = 0
        for item in data["result"]["items"]:
            name = item.get("full_name", "Без названия")
            
            has_site = False
            external = item.get("external_content", [])
            for ext in external:
                if ext.get("type") == "website":
                    has_site = True
                    break
            
            if not has_site:
                found_count += 1
                
                phone = "Нет телефона"
                email = "Нет email"
                vk_link = "Нет ВК"
                tg_link = "Нет ТГ"
                
                contacts = item.get("contact_groups", [])
                for group in contacts:
                    if group.get("type") == "phone":
                        phone_list = group.get("contacts", [])
                        if phone_list: phone = phone_list[0].get("value", "Нет телефона")
                    if group.get("type") == "email":
                        email_list = group.get("contacts", [])
                        if email_list: email = email_list[0].get("value", "Нет email")
                    if group.get("type") == "social":
                        for social in group.get("contacts", []):
                            url_val = social.get("url", "")
                            if "vk.com" in url_val: vk_link = url_val
                            elif "t.me" in url_val: tg_link = url_val
                
                for ext in external:
                    url_val = ext.get("url", "")
                    if "vk.com" in url_val and vk_link == "Нет ВК": vk_link = url_val
                    elif "t.me" in url_val and tg_link == "Нет ТГ": tg_link = url_val
                
                address = item.get("address_name", "Адрес скрыт")
                
                text = f"🏢 **{name}**\n📞 {phone}\n📍 {address}"
                if email != "Нет email": text += f"\n📧 {email}"
                if vk_link != "Нет ВК": text += f"\n🔵 ВК: {vk_link}"
                if tg_link != "Нет ТГ": text += f"\n✈️ ТГ: {tg_link}"
                
                bot.send_message(message.chat.id, text, parse_mode="Markdown", disable_web_page_preview=True)
        
        if found_count == 0:
            bot.send_message(message.chat.id, f"На странице {current_page} все {current_query.lower()} имеют сайты. Листаем дальше...")
            current_page += 1
            # Автоматически ищем следующую страницу
            find_salons(message)
        else:
            bot.send_message(message.chat.id, f"✅ Найдено {found_count} на странице {current_page}. Нажми «Найти» для следующей страницы.", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("🔍 Найти")).add(types.KeyboardButton("🔍 Выбрать нишу")))
            current_page += 1
            
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Ошибка: {e}", reply_markup=main_menu())

if __name__ == "__main__":
    print("Бот-разведчик запущен.")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
