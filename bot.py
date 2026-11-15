# Телеграм-бот: ищет малый бизнес без сайта (API 2ГИС)

import asyncio
import csv
import io
import logging
import sqlite3
from dataclasses import dataclass, field
from html import escape
from urllib.parse import urlparse

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import BufferedInputFile
from aiogram.types import CallbackQuery
from aiogram.types import InlineKeyboardButton
from aiogram.types import InlineKeyboardMarkup
from aiogram.types import Message

BOT_TOKEN = "8903826339:AAEDpnCWipEUwkvx_N9KLuLn-yyYZB18EMA"
DGIS_KEY = "4f107268-001b-41d1-a84c-345fcded5ecb"
ALLOWED = {6984430179}
DB_PATH = "leads.db"

API_URL = "https://catalog.api.2gis.com/3.0/items"
FIELDS = (
    "items.contact_groups,items.address_name,"
    "items.rubrics,items.full_address_name"
)
SOCIAL_KINDS = (
    "vkontakte", "telegram", "instagram",
    "whatsapp", "viber", "facebook", "ok",
)
NOT_OWN_SITE = {
    "vk.com", "vk.ru", "m.vk.com", "t.me", "telegram.me",
    "instagram.com", "facebook.com", "ok.ru", "youtube.com",
    "wa.me", "api.whatsapp.com", "linktr.ee", "taplink.cc",
    "2gis.ru", "yandex.ru", "avito.ru", "profi.ru", "flamp.ru",
}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("leadbot")


@dataclass
class Lead:
    firm_id: str
    name: str
    address: str
    phones: list = field(default_factory=list)
    socials: list = field(default_factory=list)
    emails: list = field(default_factory=list)
    rubric: str = ""

    @property
    def link_2gis(self):
        return "https://2gis.ru/firm/" + self.firm_id


class ApiError(Exception):
    pass


def get_domain(url):
    url = (url or "").strip()
    if not url:
        return ""
    if "//" not in url:
        url = "//" + url
    host = (urlparse(url).netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def is_social(url):
    d = get_domain(url)
    for s in NOT_OWN_SITE:
        if d == s or d.endswith("." + s):
            return True
    return False


def parse_item(item):
    contacts = []
    for group in item.get("contact_groups") or []:
        contacts.extend(group.get("contacts") or [])

    phones, socials, emails = [], [], []
    has_own_site = False
    
    for c in contacts:
        kind = c.get("type")
        value = str(c.get("value") or c.get("text") or "").strip()
        if not value:
            continue
            
        # Ищем сайты (Любые ссылки, которые не соцсети)
        if kind in ("website", "url", "site"):
            if not is_social(value):
                has_own_site = True
            else:
                socials.append(value)
                
        elif kind == "phone":
            phones.append(value)
                
        elif kind == "email":
            emails.append(value)
        elif kind in SOCIAL_KINDS:
            socials.append(value)

    # Если есть реальный сайт — ЖЕСТКО ВЫКИДЫВАЕМ
    if has_own_site:
        return None

    rubrics = item.get("rubrics") or []
    rubric = rubrics[0].get("name", "") if rubrics else ""
    address = item.get("address_name")
    address = address or item.get("full_address_name") or ""

    # Сохраняем, если есть хоть что-то (телефон, соцсеть, почта или адрес)
    if not (phones or socials or emails or address):
        return None

    return Lead(
        firm_id=str(item.get("id", "")).split("_")[0],
        name=item.get("name", "Без названия"),
        address=address,
        phones=list(dict.fromkeys(phones)),
        socials=list(dict.fromkeys(socials)),
        emails=list(dict.fromkeys(emails)),
        rubric=rubric,
    )


async def fetch_page(session, query, page):
    params = {
        "q": query,
        "key": DGIS_KEY,
        "page": page,
        "page_size": 10,
        "locale": "ru_RU",
        "type": "branch",
        "fields": FIELDS,
    }
    timeout = aiohttp.ClientTimeout(total=40)
    async with session.get(API_URL, params=params, timeout=timeout) as r:
        data = await r.json(content_type=None)

    meta = data.get("meta", {})
    code = meta.get("code", r.status)
    if code == 404:
        return []
    if code != 200:
        err = meta.get("error") or {}
        text = err.get("message") or "code " + str(code)
        raise ApiError(text)
    return data.get("result", {}).get("items", [])


async def find_leads(session, query, start_page):
    leads = []
    page = start_page
    # Пролистываем до 5 страниц
    for _ in range(5):
        items = await fetch_page(session, query, page)
        
        # ДИАГНОСТИКА (в консоль)
        print(f"\n=== ПОЛУЧЕНО СТРАНИЦ: {len(items)} ===")
        for it in items:
            print(it.get("name"), "| Сайт:", it.get("contact_groups"))
        
        if not items:
            return leads, page, True
        
        for it in items:
            lead = parse_item(it)
            if lead:
                leads.append(lead)
        
        page += 1
        if len(leads) >= 10:
            return leads, page, False
            
        await asyncio.sleep(0.3)
    return leads, page, True


db = sqlite3.connect(DB_PATH)
db.execute(
    "CREATE TABLE IF NOT EXISTS leads("
    "user_id INTEGER, firm_id TEXT, name TEXT, rubric TEXT, "
    "address TEXT, phones TEXT, socials TEXT, emails TEXT, "
    "link TEXT, query TEXT, PRIMARY KEY(user_id, firm_id))"
)
db.commit()

sessions = {}
locks = {}
dp = Dispatcher()


def allowed(user_id):
    return (not ALLOWED) or (user_id in ALLOWED)


def is_new(user_id, firm_id):
    row = db.execute(
        "SELECT 1 FROM leads WHERE user_id=? AND firm_id=?",
        (user_id, firm_id),
    ).fetchone()
    return row is None


def save(user_id, lead, query):
    db.execute(
        "INSERT OR IGNORE INTO leads VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            user_id, lead.firm_id, lead.name, lead.rubric,
            lead.address, "; ".join(lead.phones),
            "; ".join(lead.socials), "; ".join(lead.emails),
            lead.link_2gis, query,
        ),
    )
    db.commit()


def render(lead):
    lines = ["<b>" + escape(lead.name) + "</b>"]
    if lead.rubric:
        lines.append("<i>" + escape(lead.rubric) + "</i>")
    if lead.address:
        lines.append("\U0001F4CD " + escape(lead.address))
    if lead.phones:
        phones = ", ".join(escape(p) for p in lead.phones)
        lines.append("\U0001F4DE " + phones)
    for s in lead.socials[:3]:
        lines.append("\U0001F517 " + escape(s))
    if lead.emails:
        mails = ", ".join(escape(e) for e in lead.emails)
        lines.append("\u2709\uFE0F " + mails)
    lines.append(
        '<a href="' + lead.link_2gis + '">Карточка в 2ГИС</a>'
    )
    return "\n".join(lines)


def keyboard(done):
    row = []
    if not done:
        row.append(InlineKeyboardButton(
            text="Ещё 10", callback_data="more"))
    row.append(InlineKeyboardButton(
        text="Скачать таблицей", callback_data="csv"))
    return InlineKeyboardMarkup(inline_keyboard=[row])


async def send_chunks(bot, chat_id, blocks):
    buf = ""
    for b in blocks:
        if buf and len(buf) + len(b) + 2 > 3500:
            await bot.send_message(
                chat_id, buf, disable_web_page_preview=True)
            buf = ""
            await asyncio.sleep(0.3)
        buf += ("\n\n" if buf else "") + b
    if buf:
        await bot.send_message(
            chat_id, buf, disable_web_page_preview=True)


async def run_search(bot, chat_id, user_id):
    st = sessions.get(user_id)
    if not st:
        await bot.send_message(
            chat_id,
            "Сначала отправьте запрос: <code>барбершоп, Казань</code>",
        )
        return
    lock = locks.setdefault(user_id, asyncio.Lock())
    if lock.locked():
        return
    async with lock:
        wait = await bot.send_message(
            chat_id, "Ищу, подождите немного...")
        try:
            timeout = aiohttp.ClientTimeout(total=40)
            async with aiohttp.ClientSession(timeout=timeout) as http:
                res = await find_leads(http, st["q"], st["page"])
            leads, st["page"], st["done"] = res
        except ApiError as e:
            await wait.edit_text("Ошибка 2ГИС: " + escape(str(e)))
            return
        except Exception as e:
            log.exception("search failed")
            await wait.edit_text(
                "Ошибка поиска: " + escape(str(e)))
            return

        fresh = [x for x in leads if is_new(user_id, x.firm_id)]
        for x in fresh:
            save(user_id, x, st["q"])
        await wait.delete()

        if not fresh:
            if st["done"]:
                text = "Больше новых бизнесов без сайта нет."
            else:
                text = "Тут все уже показаны. Нажмите «Ещё 10»."
            await bot.send_message(
                chat_id, text, reply_markup=keyboard(st["done"]))
            return
        await send_chunks(bot, chat_id, [render(x) for x in fresh])
        await bot.send_message(
            chat_id, "Нашёл: " + str(len(fresh)),
            reply_markup=keyboard(st["done"]))


HELLO = (
    "Я ищу малый бизнес <b>без своего сайта</b> "
    "и показываю контакты.\n\n"
    "Напишите категорию и город через запятую:\n"
    "<code>барбершоп, Казань</code>\n"
    "<code>автосервис, Самара</code>\n\n"
    "/csv - выгрузка таблицей\n"
    "/clear - очистить найденное"
)


@dp.message(CommandStart())
async def start(m: Message):
    if not allowed(m.from_user.id):
        return await m.answer("Бот закрытый.")
    await m.answer(HELLO)


@dp.message(Command("csv"))
async def cmd_csv(m: Message):
    await send_csv(m.bot, m.chat.id, m.from_user.id)


@dp.message(Command("clear"))
async def cmd_clear(m: Message):
    if not allowed(m.from_user.id):
        return
    db.execute("DELETE FROM leads WHERE user_id=?",
               (m.from_user.id,))
    db.commit()
    sessions.pop(m.from_user.id, None)
    await m.answer("Список очищен.")


@dp.message(F.text & ~F.text.startswith("/"))
async def on_query(m: Message):
    if not allowed(m.from_user.id):
        return await m.answer("Бот закрытый.")
    text = m.text.strip()
    if "," not in text:
        return await m.answer(
            "Напишите: <code>барбершоп, Казань</code>")
    category, city = [p.strip() for p in text.rsplit(",", 1)]
    if not category or not city:
        return await m.answer(
            "Нужны категория и город: <code>барбершоп, Казань</code>")
    sessions[m.from_user.id] = {
        "q": category + " " + city, "page": 1, "done": False}
    await run_search(m.bot, m.chat.id, m.from_user.id)


@dp.callback_query(F.data == "more")
async def on_more(c: CallbackQuery):
    await c.answer()
    if allowed(c.from_user.id):
        await run_search(
            c.bot, c.message.chat.id, c.from_user.id)


@dp.callback_query(F.data == "csv")
async def on_csv(c: CallbackQuery):
    await c.answer()
    await send_csv(c.bot, c.message.chat.id, c.from_user.id)


async def send_csv(bot, chat_id, user_id):
    if not allowed(user_id):
        return
    rows = db.execute(
        "SELECT name, rubric, address, phones, socials, emails, "
        "link, query FROM leads WHERE user_id=?",
        (user_id,),
    ).fetchall()
    if not rows:
        await bot.send_message(chat_id, "Пока ничего не найдено.")
        return
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Название", "Категория", "Адрес", "Телефоны",
                "Соцсети", "Почта", "2ГИС", "Запрос"])
    w.writerows(rows)
    data = ("\ufeff" + buf.getvalue()).encode("utf-8")
    await bot.send_document(
        chat_id, BufferedInputFile(data, "leads.csv"),
        caption="Всего: " + str(len(rows)))


async def main():
    bot = Bot(
        BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
