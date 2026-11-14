"""Телеграм-бот: ищет малый бизнес без сайта и показывает контакты. Один файл."""

import asyncio

import csv

import io

import logging

import os

import sqlite3

from dataclasses import dataclass, field

from html import escape

from urllib.parse import urlparse



import aiohttp

from aiogram import Bot, Dispatcher, F

from aiogram.client.default import DefaultBotProperties

from aiogram.enums import ParseMode

from aiogram.filters import Command, CommandStart

from aiogram.types import (BufferedInputFile, CallbackQuery, InlineKeyboardButton,

                           InlineKeyboardMarkup, Message)



# ---------- поиск через API 2ГИС ----------

API_URL = "https://catalog.api.2gis.com/3.0/items"



# Соцсети и агрегаторы не считаются «своим сайтом»

NOT_OWN_SITE = {

    "vk.com", "vk.ru", "m.vk.com", "t.me", "telegram.me", "instagram.com", "facebook.com",

    "ok.ru", "youtube.com", "wa.me", "api.whatsapp.com", "linktr.ee", "taplink.cc",

    "2gis.ru", "yandex.ru", "avito.ru", "profi.ru", "flamp.ru",

}





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

    def link_2gis(self) -> str:

        return f"https://2gis.ru/firm/{self.firm_id}"





class ApiError(Exception):

    pass





def _domain(url: str) -> str:

    url = (url or "").strip()

    if not url:

        return ""

    if "//" not in url:

        url = "//" + url

    host = (urlparse(url).netloc or "").lower()

    return host[4:] if host.startswith("www.") else host





def _is_social(url: str) -> bool:

    d = _domain(url)

    return any(d == s or d.endswith("." + s) for s in NOT_OWN_SITE)





def parse_item(item: dict):

    """Lead, если своего сайта нет и есть чем связаться, иначе None."""

    contacts = []

    for group in item.get("contact_groups") or []:

        contacts.extend(group.get("contacts") or [])



    phones, socials, emails, has_own_site = [], [], [], False

    for c in contacts:

        kind = c.get("type")

        value = (c.get("value") or c.get("text") or "").strip()

        if not value:

            continue

        if kind == "website":

            if _is_social(value):

                socials.append(value)

            else:

                has_own_site = True

        elif kind == "phone":

            phones.append(c.get("print_text") or c.get("text") or value)

        elif kind == "email":

            emails.append(value)

        elif kind in ("vkontakte", "telegram", "instagram", "whatsapp", "viber", "facebook", "ok"):

            socials.append(value)



    if has_own_site:

        return None

    if not (phones or socials or emails):

        return None



    rubrics = item.get("rubrics") or []

    return Lead(

        firm_id=str(item.get("id", "")).split("_")[0],

        name=item.get("name", "Без названия"),

        address=item.get("address_name") or item.get("full_address_name") or "",

        phones=list(dict.fromkeys(phones)),

        socials=list(dict.fromkeys(socials)),

        emails=list(dict.fromkeys(emails)),

        rubric=rubrics[0].get("name", "") if rubrics else "",

    )





async def fetch_page(session, key, query, page, page_size=10):

    params = {

        "q": query, "key": key, "page": page, "page_size": page_size,

        "locale": "ru_RU", "type": "branch",

        "fields": "items.contact_groups,items.address_name,items.rubrics,items.full_address_name",

    }

    async with session.get(API_URL, params=params, timeout=aiohttp.ClientTimeout(total=20)) as r:

        data = await r.json(content_type=None)



    meta = data.get("meta", {})

    code = meta.get("code", r.status)

    if code == 404:                 # результатов больше нет

        return [], 0

    if code != 200:

        msg = (meta.get("error") or {}).get("message") or f"ко
01:46
д {code}"

        raise ApiError(msg)

    result = data.get("result", {})

    return result.get("items", []), result.get("total", 0)





async def find_leads(session, key, query, start_page, want=10, max_pages=12, delay=0.3):

    """Листает выдачу, пока не наберёт want бизнесов без сайта. -> (leads, next_page, finished)"""
