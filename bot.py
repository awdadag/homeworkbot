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

# Храним ID уже найденных салонов, чтобы не было повторов
found_ids = set()

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔍 Найти салоны без сайта"))
    return markup

@bot.message_handler(commands=["start"])
def cmd_start(message):
    found_ids.clear() # Очищаем историю поиска при старте
    bot.send_message(message.chat.id, "Привет! Я бот-разведчик. Нажми кнопку, чтобы найти салоны в Питере без сайтов.", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "🔍 Найти салоны без сайта")
def find_salons(message):
    bot.send_message(message.chat.id, "🔎 Ищу салоны в Санкт-Петербурге (с телефонами и соцсетями)...")
    
    url = "https://catalog.api.2gis.com/3.0/items"
    params = {
        "q": "Салоны красоты",
        "region_id": 38, 
        # Запрашиваем ВСЕ возможные поля с контактами
        "fields": "items.point,items.contact_groups,items.external_content,items.full_name,items.address_name,items.schedule,items.reviews", 
        "page_size": 20, # Берем 20 штук за раз
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
            item_id = item.get("id")
            
            # Если уже видели этот салон - пропускаем
            if item_id in found_ids:
                continue

            name = item.get("full_name", "Без названия")
            
            # Проверяем, есть ли сайт
            has_site = False
            external = item.get("external_content", [])
            for ext in external:
                if ext.get("type") == "website":
                    has_site = True
                    break
            
            # Если сайта нет - обрабатываем
            if not has_site:
                found_count += 1
                found_ids.add(item_id) # Запоминаем ID
                
                # Ищем все контакты
                phone = "Нет телефона"
                vk_link = "Нет ВК"
                tg_link = "Нет ТГ"
                
                contacts = item.get("contact_groups", [])
                for group in contacts:
                    # Телефон
                    if group.get("type") == "phone":
                        phone_list = group.get("contacts", [])
                        if phone_list:
                            phone = phone_list[0].get("value", "Нет телефона")
                    
                    # Соцсети (ВК, ТГ и т.д.)
                    if group.get("type") == "social":
                        for social in group.get("contacts", []):
                            url_val = social.get("url", "")
                            if "vk.com" in url_val:
                                vk_link = url_val
                            elif "t.me" in url_val:
                                tg_link = url_val
                
                address = item.get("address_name", "Адрес скрыт")
                
                text = f"🏢 **{name}**\n📞 {phone}\n📍 {address}"
                if vk_link != "Нет ВК": text += f"\n🔵 ВК: {vk_link}"
                if tg_link != "Нет ТГ": text += f"\n✈️ ТГ: {tg_link}"
                
                bot.send_message(message.chat.id, text, parse_mode="Markdown", disable_web_page_preview=True)
        
        if found_count == 0:
            bot.send_message(message.chat.id, "Все найденные салоны уже есть в базе или имеют сайты. Попробуйте позже.")
        else:
            bot.send_message(message.chat.id, f"✅ Найдено {found_count} новых салонов без сайта.")

    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Ошибка API: {e}")

if __name__ == "__main__":
    print("Бот-разведчик запущен.")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
