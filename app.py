import socket
import sqlite3
import json
import random
import os
from flask import Flask, render_template_string, url_for, request, jsonify, send_from_directory, redirect
from datetime import datetime
import re
from pywebpush import webpush, WebPushException
from werkzeug.utils import secure_filename

app = Flask(__name__)
UPLOAD_FOLDER = 'static/images'

# Анбор барои нигоҳдории кодҳои тасдиқ (Phone: Code)
verification_codes = {}

# VAPID Keys (Барои амният лозим аст)
# ДИҚҚАТ: Ин калидҳоро иваз накунед, онҳо бо sw.js мувофиқанд
VAPID_PUBLIC_KEY = "BCX7B8_p9v7Z-S-l1M0W4Y1Z2X3C4V5B6N7M8L9K0J1I2H3G4F5E6D7C8B9A0S1D2F3G4H5J6K7L8"
VAPID_PRIVATE_KEY = "m1N2B3V4C5X6Z7A8S9D0F1G2H3J4K5L6m1N2B3V4C5X"
VAPID_CLAIMS = {"sub": "mailto:admin@tfc-kulob.tj"}

# Рӯйхати рақамҳо барои гардиш ҳангоми Доставка
PAYMENT_PHONE_NUMBERS = ["944975050", "754169090"]

def get_setting(key, default_value=None):
    """Гирифтани танзимот аз база"""
    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = cur.fetchone()
    conn.close()
    return result[0] if result else default_value

def set_setting(key, value):
    """Захира кардани танзимот дар база"""
    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def get_next_payment_phone_for_rotation():
    """Интихоби рақами навбатӣ барои пардохт"""
    last_index_str = get_setting("last_payment_phone_index", "0")
    last_index = int(last_index_str) if last_index_str.isdigit() else 0
    next_index = (last_index + 1) % len(PAYMENT_PHONE_NUMBERS)
    set_setting("last_payment_phone_index", str(next_index))
    return PAYMENT_PHONE_NUMBERS[next_index]

# Rohi mutlaq baroi muvofiqat bo bilol.py
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tfc_admin.db")

def init_db() -> None:
    conn = sqlite3.connect(DB_PATH, timeout=20) # Ensure timeout is applied here
    cur = conn.cursor()
    
    # 1. Аввал ҷадвалҳоро месозем
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer TEXT NOT NULL,
            customer_id TEXT NOT NULL DEFAULT '',
            food TEXT NOT NULL,
            price TEXT NOT NULL,
            phone TEXT NOT NULL DEFAULT '',
            delivery_type TEXT NOT NULL DEFAULT '',
            tip TEXT NOT NULL DEFAULT '',
            qabyl INTEGER NOT NULL DEFAULT 0,
            omoda INTEGER NOT NULL DEFAULT 0,
            dostavka INTEGER NOT NULL DEFAULT 0,
            out_of_stock INTEGER NOT NULL DEFAULT 0,
            estimated_time INTEGER DEFAULT 0,
            created TEXT NOT NULL
        )
        """
    )
    cur.execute("CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, text TEXT NOT NULL, stars INTEGER NOT NULL, image_url TEXT, created TEXT NOT NULL)")
    cur.execute("CREATE TABLE IF NOT EXISTS foods (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, price TEXT NOT NULL, category TEXT NOT NULL, image_url TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', created TEXT NOT NULL)")
    cur.execute("CREATE TABLE IF NOT EXISTS push_subscriptions (id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id TEXT UNIQUE, subscription_json TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS aktsii (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, price TEXT NOT NULL DEFAULT '', description TEXT, image_url TEXT, created TEXT NOT NULL)")
    cur.execute("PRAGMA table_info(aktsii)")
    a_cols = [r[1] for r in cur.fetchall()]
    if "price" not in a_cols:
        cur.execute("ALTER TABLE aktsii ADD COLUMN price TEXT NOT NULL DEFAULT ''")

    cur.execute("CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL, customer_id TEXT UNIQUE NOT NULL, created TEXT NOT NULL)")

    # Ҷадвали махсус барои нигоҳдории доимии даромад (History)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS revenue_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            day TEXT NOT NULL,
            customer_id TEXT DEFAULT ''
        )
        """
    )
    cur.execute("PRAGMA table_info(revenue_history)")
    rev_cols = [r[1] for r in cur.fetchall()]
    if "customer_id" not in rev_cols:
        cur.execute("ALTER TABLE revenue_history ADD COLUMN customer_id TEXT DEFAULT ''")

    # Ҷадвали таърихи пурраи заказҳо (Архив)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS full_order_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            food TEXT NOT NULL,
            price TEXT NOT NULL,
            phone TEXT NOT NULL,
            delivery_type TEXT NOT NULL,
            tip TEXT NOT NULL DEFAULT '',
            created TEXT NOT NULL
        )
        """
    )

    # 2. Баъд сутунҳоро тафтиш ва илова мекунем
    cur.execute("PRAGMA table_info(orders)")
    cols = [r[1] for r in cur.fetchall()]
    if "customer_id" not in cols: cur.execute("ALTER TABLE orders ADD COLUMN customer_id TEXT NOT NULL DEFAULT ''")
    if "qabyl" not in cols: cur.execute("ALTER TABLE orders ADD COLUMN qabyl INTEGER NOT NULL DEFAULT 0")
    if "omoda" not in cols: cur.execute("ALTER TABLE orders ADD COLUMN omoda INTEGER NOT NULL DEFAULT 0")
    if "phone" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN phone TEXT NOT NULL DEFAULT ''")
    if "delivery_type" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN delivery_type TEXT NOT NULL DEFAULT ''")
    if "dostavka" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN dostavka INTEGER NOT NULL DEFAULT 0")
    if "out_of_stock" not in cols: cur.execute("ALTER TABLE orders ADD COLUMN out_of_stock INTEGER NOT NULL DEFAULT 0")
    if "delivery_latitude" not in cols: cur.execute("ALTER TABLE orders ADD COLUMN delivery_latitude TEXT DEFAULT ''")
    if "delivery_longitude" not in cols: cur.execute("ALTER TABLE orders ADD COLUMN delivery_longitude TEXT DEFAULT ''")
    if "delivery_address" not in cols: cur.execute("ALTER TABLE orders ADD COLUMN delivery_address TEXT DEFAULT ''")
    if "tip" not in cols: cur.execute("ALTER TABLE orders ADD COLUMN tip TEXT NOT NULL DEFAULT ''")
    if "refund" not in cols: cur.execute("ALTER TABLE orders ADD COLUMN refund REAL DEFAULT 0")
    if "estimated_time" not in cols: cur.execute("ALTER TABLE orders ADD COLUMN estimated_time INTEGER DEFAULT 0")
    if "payment_method" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT DEFAULT 'online'")

    # Ҷадвал барои танзимоти динамикӣ
    cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")

    cur.execute("PRAGMA table_info(foods)")
    f_cols = [r[1] for r in cur.fetchall()]
    if "description" not in f_cols: cur.execute("ALTER TABLE foods ADD COLUMN description TEXT NOT NULL DEFAULT ''")
    if "subcategory" not in f_cols:
        cur.execute("ALTER TABLE foods ADD COLUMN subcategory TEXT NOT NULL DEFAULT ''")
    
    cur.execute("PRAGMA table_info(reviews)")
    r_cols = [r[1] for r in cur.fetchall()]
    if "image_url" not in r_cols: cur.execute("ALTER TABLE reviews ADD COLUMN image_url TEXT")

    cur.execute("PRAGMA table_info(full_order_history)")
    foh_cols = [r[1] for r in cur.fetchall()]
    if "tip" not in foh_cols: cur.execute("ALTER TABLE full_order_history ADD COLUMN tip TEXT NOT NULL DEFAULT ''")
    if "payment_method" not in foh_cols:
        cur.execute("ALTER TABLE full_order_history ADD COLUMN payment_method TEXT DEFAULT 'online'")

    # 3. Илова кардани додаҳои намунавӣ (Sync with bilol.py)
    sample_foods = [
        # ЛЕТНЕЕ МЕНЮ
        ("СМУЗИ БАНАН + КИВИ", "26", "Летнее меню", "d1.png", "Смузи", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СМУЗИ БАНАН + МАЛИНА", "26", "Летнее меню", "d3.png", "Смузи", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ОКРОШКА (350МЛ)", "16", "Летнее меню", "d7.png", "Холодок", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("АЙРАН (500МЛ)", "6", "Летнее меню", "d8.png", "Холодок", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МОХИТО LIME", "19", "Летнее меню", "e1.png", "Мохито", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МОХИТО CLASSIC", "16", "Летнее меню", "e2.png", "Мохито", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МОХИТО BLUE LAGOON", "19", "Летнее меню", "e6.png", "Мохито", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МОХИТО KIWI", "19", "Летнее меню", "e8.png", "Мохито", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),

        # МЕНЮ (ПАСТА, САЛАТҲО, ШӮРБОҲО ва ғ.)
        ("ПАСТА БОЛОНЕЗА", "31", "Меню", "b1.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПАСТА ФИТУЧИНИ", "35", "Меню", "b2.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПАСТА ПЕНЕ", "32", "Меню", "b3.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПАСТА СОБА", "23", "Меню", "b4.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ГНЁЗДА С ГОВЯДИНОЙ", "27", "Меню", "b5.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("САЛАТ ТАЙСКИЙ", "34", "Меню", "b6.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("САЛАТ TFC", "35", "Меню", "b7.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ХРУСТЯЩИЙ БАКЛАЖАН", "17", "Меню", "b8.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("САЛАТ ЦЕЗАРЬ", "25", "Меню", "b9.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("САЛАТ ЗЕЛЁНАЯ ЛУЖАЙКА", "15", "Меню", "b10.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ГРЕЧЕСКИЙ САЛАТ", "34", "Меню", "b11.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУП МЕРДЖИМЕК", "15", "Меню", "b12.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("БОРЩ", "25", "Меню", "b13.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ГРИБНОЙ СУП", "26", "Меню", "b14.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЛАГМАН", "21", "Меню", "b15.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУП TFC", "28", "Меню", "b16.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЧАХОВ БИЛИ", "26", "Меню", "b17.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("БИФШ СТЕКС", "25/35", "Меню", "b18.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КОТЛЕТ ПО-КИЕВСКИЙ", "28/38", "Меню", "b19.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КАЗАН КАБОБ", "40", "Меню", "b21.jpg", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЖАРОВНЯ ТФС (БАРАНИНА/ГОВЯДИНА)", "50", "Меню", "b22.jpg", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СТЕЙК ИЗ ФОРЕЛИ", "25", "Меню", "b23.jpg", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТАБАКА", "58", "Меню", "b24.jpg", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КОРЕЙКА БАРАНИНА", "50", "Меню", "b25.jpg", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СТЕЙК ИЗ ГОВЯДИНЫ", "50", "Меню", "b26.jpg", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЧИЗКЕЙК", "12", "Меню", "b27.jpg", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("РАФАЭЛЛО", "12", "Меню", "b28.jpg", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("НАПОЛЕОН", "10", "Меню", "b29.jpg", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТИРАМИСУ", "12", "Меню", "b30.jpg", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ФРУКТОВАЯ НАРЕЗКА (Большая)", "75", "Меню", "b31.jpg", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ФРУКТОВАЯ НАРЕЗКА (Средняя)", "50", "Меню", "b32.jpg", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КЕШЬЮ", "45", "Меню", "b33.jpg", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ФИСТАШКИ", "45", "Меню", "b34.jpg", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ФИСТАШКИ", "45", "Меню", "b34.jpg", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("АМЕРИКАНО", "15", "Меню", "b35.jpg", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КАПУЧИНO", "18", "Меню", "b36.jpg", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЛАТТЕ", "18", "Меню", "b37.jpg", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЭСПРЕССО", "12", "Меню", "b38.jpg", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЧАЙ (Зелёный / черный)", "5", "Меню", "b39.jpg", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПАСТА БОЛОНЕЗА", "31", "Меню", "b1.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПАСТА ФИТУЧИНИ", "35", "Меню", "b2.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПАСТА ПЕНЕ", "32", "Меню", "b3.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПАСТА СОБА", "23", "Меню", "b4.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ГНЁЗДА С ГОВЯДИНОЙ", "27", "Меню", "b5.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("САЛАТ ТАЙСКИЙ", "34", "Меню", "b6.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("САЛАТ TFC", "35", "Меню", "b7.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ХРУСТЯЩИЙ БАКЛАЖАН", "17", "Меню", "b8.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("САЛАТ ЦЕЗАРЬ", "25", "Меню", "b9.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("САЛАТ ЗЕЛЁНАЯ ЛУЖАЙКА", "15", "Меню", "b10.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ГРЕЧЕСКИЙ САЛАТ", "34", "Меню", "b11.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУП МЕРДЖИМЕК", "15", "Меню", "b12.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("БОРЩ", "25", "Меню", "b13.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ГРИБНОЙ СУП", "26", "Меню", "b14.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЛАГМАН", "21", "Меню", "b15.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУП TFC", "28", "Меню", "b16.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЧАХОВ БИЛИ", "26", "Меню", "b17.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("БИФШ СТЕКС", "25/35", "Меню", "b18.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КОТЛЕТ ПО-КИЕВСКИЙ", "28/38", "Меню", "b19.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КАЗАН КАБОБ", "40", "Меню", "b21.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЖАРОВНЯ ТФС (БАРАНИНА/ГОВЯДИНА)", "50", "Меню", "b22.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СТЕЙК ИЗ ФОРЕЛИ", "25", "Меню", "b23.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТАБАКА", "58", "Меню", "b24.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КОРЕЙКА БАРАНИНА", "50", "Меню", "b25.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СТЕЙК ИЗ ГОВЯДИНЫ", "50", "Меню", "b26.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЧИЗКЕЙК", "12", "Меню", "b27.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("РАФАЭЛЛО", "12", "Меню", "b28.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("НАПОЛЕОН", "10", "Меню", "b29.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТИРАМИСУ", "12", "Меню", "b30.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ФРУКТОВАЯ НАРЕЗКА (Большая)", "75", "Меню", "b31.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ФРУКТОВАЯ НАРЕЗКА (Средняя)", "50", "Меню", "b32.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КЕШЬЮ", "45", "Меню", "b33.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ФИСТАШКИ", "45", "Меню", "b34.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ФИСТАШКИ", "45", "Меню", "b34.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("АМЕРИКАНО", "15", "Меню", "b35.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КАПУЧИНO", "18", "Меню", "b36.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЛАТТЕ", "18", "Меню", "b37.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЭСПРЕССО", "12", "Меню", "b38.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЧАЙ (Зелёный / черный)", "5", "Меню", "b39.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),

        # ПИЦЦА
        ("ПИЦЦА ГОВЯДИНА", "65/87", "Пицца", "a1.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПИЦЦА АССОРТИ", "68/88", "Пицца", "a2.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПИЦЦА ЧЕТЫРЕ СЫРА", "61/78", "Пицца", "a3.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПИЦЦА ЧЕРНАЯ МЕТКА", "62/79", "Пицца", "a4.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПИЦЦА ТОНИ МОНТАНА", "73/90", "Пицца", "a5.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПИЦЦА TFC", "68/90", "Пицца", "a6.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПИЦЦА ПЕППЕРОНИ", "63/75", "Пицца", "a7.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПИЦЦА КУРИНАЯ", "65/84", "Пицца", "a8.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ХАЧАПУРИ ПО-АДЖАРСКИ", "35", "Пицца", "a9.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ХАЧАПУРИ МЕГРЕЛЬСКИЙ", "40", "Пицца", "a10.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),

        # СУШИ
        ("МИНИ РОЛЛЫ С СЫРОМ", "25/35", "Суши", "a.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СИЯКИ МАКИ", "24/34", "Суши", "b.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МИНИ РОЛЛЫ ФИЛАДЕЛЬФИЯ", "26/36", "Суши", "c.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("УНАГИ КАПА МАКИ", "27/37", "Суши", "d.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЗАПЕЧЕНЫЙ САМУРАЙ", "51", "Суши", "e.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЗАПЕЧЕНЫЙ УНАГИ", "61", "Суши", "f.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЗАПЕЧЕННАЯ КАЛИФОРНИЯ С КРЕВЕТКОЙ", "59/69", "Суши", "g.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЗАПЕЧЕНЫЙ СЯКЕ", "54/64", "Суши", "h.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТЕМПУРА КРАЙЗИ", "44", "Суши", "i.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТЕМПУРА СНЕЖНЫЙ КРАБ", "45", "Суши", "j.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ОВОЩНАЯ ТЕМПУРА", "35", "Суши", "k.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТЕМПУРА ЦЕЗАРЬ", "38", "Суши", "l.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("РОЛЛ КАНАДА TFC", "60", "Суши", "m.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("РОЛЛ САНСИ", "58", "Суши", "n.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КАЛИФОРНИЯ СНЕЖНЫЙ КРАБ", "51", "Суши", "o.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("РОЛЛ ФИЛАДЕЛЬФИЯ", "58", "Суши", "p.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУШИ С КРЕВЕТКОЙ", "13", "Суши", "q.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУШИ С УГЛЕМ", "13", "Суши", "r.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУШИ С ЛОСОСЬЮ", "17", "Суши", "s.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУШИ ЗАПЕЧЕНЫЙ ЛОСОСЬ", "17", "Суши", "t.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУШИ ОСТРЫЕ С ТУНЦОМ", "12", "Суши", "u.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУШИ С УГРЕМ", "13", "Суши", "v.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СЕТ ТЕМПУРА", "135", "Суши", "w.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СЕТ КАНАДА TFC", "160", "Суши", "x.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СЕТ ЗАПЕЧЁННЫЙ", "146", "Суши", "y.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),

        # ФАСТ ФУД
        ("НОН-ДОГ", "5/7", "Фастфуд", "1.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("БУЛОЧКА", "6/8", "Фастфуд", "2.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("М-ДОГ", "10", "Фастфуд", "3.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("TFC-ДОГ", "18/30", "Фастфуд", "4.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЧИКЕН-ДОГ", "12/24", "Фастфуд", "5.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("НАЧО-ДОГ", "14/26", "Фастфуд", "6.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЧИКЕНЧИЗ-ДОГ", "16/28", "Фастфуд", "7.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ШЕФ-ДОГ", "17/29", "Фастфуд", "8.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("АМЕРИКАНО-ДОГ", "16/25", "Фастфуд", "9.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ИТАЛИ-ДОГ", "12/20", "Фастфуд", "10.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("БИФ-ДОГ", "41", "Фастфуд", "11.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КЛАССИК БУРГЕР", "23", "Фастфуд", "12.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КЛАССИК ЧИЗБУРГЕР", "27", "Фастфуд", "13.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ДАБЛ ЧИЗБУРГЕР", "43", "Фастфуд", "14.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ДАБЛ БУРГЕР", "37", "Фастфуд", "15.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("TFC БУРГЕР", "48", "Фастфуд", "16.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ШЕФ БУРГЕР", "51", "Фастфуд", "17.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТОРТИЛЬЯ С КУРИЦЕЙ И СЫРОМ", "23", "Фастфуд", "18.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТОРТИЛЬЯ С КУРИЦЕЙ", "15", "Фастфуд", "19.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТОРТИЛЬЯ МИКС", "26", "Фастфуд", "20.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТОРТИЛЬЯ TFC", "40", "Фастфуд", "21.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТОРТИЛЬЯ ГОВЯДИНА", "32", "Фастфуд", "22.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТОРТИЛЬЯ В ТЕМПУРЕ", "28", "Фастфуд", "23.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СЭНДВИЧ SIMPLE", "19", "Фастфуд", "24.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СЭНДВИЧ С СЫРОМ", "23", "Фастфуд", "25.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КАРТОШКА ФРИ", "12/17", "Фастфуд", "28.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КАРТОФЕЛЬ ПО-ДЕРЕВЕНСКИ", "13/18", "Фастфуд", "29.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КАРТОФЕЛЬНЫЕ ШАРИКИ", "14/19", "Фастфуд", "30.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("НАГГЕТСЫ", "17/27", "Фастфуд", "31.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ОСТРЫЕ КРЫЛЫШКИ", "35/45", "Фастфуд", "32.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СЛАДКИЕ КРЫЛЫШКИ", "36/46", "Фастфуд", "33.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КУРИНЫЕ НОЖКИ", "69/109", "Фастфуд", "34.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СЫРНЫЕ ПАЛОЧКИ", "28", "Фастфуд", "35.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("БАСКЕТ", "130", "Фастфуд", "36.png", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    ]

    # Танҳо агар ҷадвали хӯрокҳо холӣ бошад, маълумоти намунавиро илова мекунем
    cur.execute("SELECT COUNT(*) FROM foods")
    if cur.fetchone()[0] == 0:
        for f in sample_foods:
            name, price, cat, img = f[0], f[1], f[2], f[3]
            # Агар дарозии элемент 6 бошад, пас индекси 4 subcategory аст
            sub = f[4] if len(f) == 6 else ""
            created = f[-1]
            
            cur.execute("""
                INSERT OR IGNORE INTO foods (name, price, category, subcategory, image_url, created)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, price, cat, sub, img, created))

    # Тоза кардани расмҳои гумшуда барои пешгирӣ аз хатогии 404
    cur.execute("UPDATE foods SET image_url = '' WHERE image_url IN ('d9.png', 'd10.png', 'd11.png')")

    conn.commit()
    conn.close()

init_db()

ADMIN_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Панель Администратора | TFC</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        body { font-family: system-ui, sans-serif; background: #0f0f0f; color: #e0e0e0; }
        .header-bar { background: linear-gradient(135deg, #1a0a0c 0%, #c8102e 100%); padding: 20px; }
        .stat-card { background: rgba(255,255,255,0.08); padding: 15px; border-radius: 12px; text-align: center; }
        .excel-table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        .excel-table th { background: #c8102e; color: white; padding: 12px; text-align: left; }
        .excel-table td { padding: 12px; border-bottom: 1px solid #333; }
        .status-btn { padding: 8px; border-radius: 8px; cursor: pointer; }
    </style>
</head>
<body>
    <header class="header-bar text-white flex justify-between items-center">
        <h1 class="text-2xl font-bold">Панель управления TFC</h1>
        <div class="flex gap-4">
            <div class="stat-card">Всего: <span id="total-count">0</span></div>
            <a href="/" class="bg-white/10 px-4 py-2 rounded-lg">На сайт</a>
        </div>
    </header>
    <main class="p-8">
        <div class="bg-gray-900 rounded-xl p-4 overflow-x-auto">
            <table class="excel-table">
                <thead>
                    <tr><th>ID</th><th>Имя</th><th>Телефон</th><th>Тип</th><th>Блюдо</th><th>Цена</th><th>Принят</th><th>Готов</th></tr>
                </thead>
                <tbody id="orders-table"></tbody>
            </table>
        </div>
    </main>
    <script>
        async function loadOrders() {
            const res = await fetch('/api/orders/since?last_id=0');
            const data = await res.json();
            const tbody = document.getElementById('orders-table');
            tbody.innerHTML = '';
            data.orders.reverse().forEach(o => {
                tbody.innerHTML += `
                    <tr>
                        <td>${o.id}</td>
                        <td>${o.customer}</td>
                        <td>${o.phone}</td>
                        <td>${o.delivery_type === 'delivery' ? '🚀 Доставка' : '🛍️ Самовывоз'}</td>
                        <td>${o.food}</td>
                        <td>${o.price}с</td>
                        <td><button onclick="updateStatus(${o.id}, 'qabyl', ${!o.qabyl})" class="${o.qabyl ? 'text-green-500':'text-red-500'} text-xl">${o.qabyl ? '✅':'⏳'}</button></td>
                        <td><button onclick="updateStatus(${o.id}, 'omoda', ${!o.omoda})" class="${o.omoda ? 'text-green-500':'text-yellow-500'}">${o.omoda ? '✅':'🔥'}</button></td>
                    </tr>`;
            });
            document.getElementById('total-count').textContent = data.orders.length;
        }
        async function updateStatus(id, field, val) {
            const body = {id, field, value:val};
            await fetch('/api/orders/update-status', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
            loadOrders();
        }
        setInterval(loadOrders, 3000); loadOrders();
    </script>
</body></html>"""

FOOD_DETAIL_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#ff0000">
    <title>{{ food.name }} | TFC</title>
    <link rel="icon" type="image/jpeg" href="{{ url_for('static', filename='images/TFC.jpg') }}">
    <link rel="manifest" href="/manifest.json">
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;900&display=swap');
        :root { --tfc-red: #ff0000; --tfc-dark: #c8102e; }
        body { font-family: 'Montserrat', sans-serif; background: #0a0a0a; color: #e0e0e0; }
        .header-gradient { background: linear-gradient(135deg, var(--tfc-red) 0%, var(--tfc-dark) 100%); }
        .detail-card { background: rgba(255,255,255,0.05); backdrop-filter: blur(8px); border: 1px solid rgba(255,0,0,0.2); }
        .price-display { font-size: 1.5rem; color: var(--tfc-red); font-weight: 900; }
        .description-text { line-height: 1.6; color: #d0d0d0; white-space: pre-wrap; }
        .media-container { border-radius: 20px; overflow: hidden; background: #1a1a1a; height: 220px; }
        .media-container img, .media-container video { width: 100%; height: auto; display: block; }
    </style>
</head>
<body class="pb-20">
    <div class="header-gradient py-6 px-4 text-white shadow-2xl">
        <div class="max-w-3xl mx-auto flex items-center justify-between">
            <a href="/" class="flex items-center gap-2 hover:opacity-80 transition">
                <i class="fas fa-arrow-left"></i>
                <span>Назад</span>
            </a>
            <div class="text-center">
                <h1 class="text-3xl font-black">TFC</h1>
                <p class="text-sm text-white/70">Tajik Fried Fish & Chicken</p>
            </div>
            <div class="w-12"></div>
        </div>
    </div>

    <main class="max-w-md mx-auto p-4 sm:p-6">
        <div class="detail-card rounded-3xl overflow-hidden shadow-2xl">
            <!-- Media Section -->
            <div class="media-container">
                {% if food.is_video %}
                    <video controls autoplay muted loop class="w-full h-full object-contain">
                        <source src="{{ food.image_path }}" type="video/mp4">
                        Ваш браузер не поддерживает видео.
                    </video>
                {% elif food.image_path %}
                    <img src="{{ food.image_path }}" alt="{{ food.name }}" class="w-full h-full object-contain mx-auto p-2">
                {% else %}
                    <div class="w-full h-full bg-gradient-to-br from-red-600 to-red-900 flex items-center justify-center">
                        <i class="fas fa-utensils text-white text-6xl opacity-30"></i>
                    </div>
                {% endif %}
            </div>

            <!-- Details Section -->
            <div class="p-4 sm:p-6">
                <!-- Title and Category -->
                <div class="mb-4">
                    <p class="text-[10px] text-red-400 font-bold uppercase tracking-wider mb-1">{{ food.category }}</p>
                    <h1 class="text-2xl sm:text-3xl font-black mb-1">{{ food.name }}</h1>
                </div>

                <!-- Price -->
                <div class="mb-6 pb-4 border-b border-gray-700">
                    <p class="text-xs text-gray-400 uppercase tracking-wide mb-1">Цена</p>
                    <div class="price-display">{{ food.price }} сом</div>
                </div>

                <!-- Description -->
                {% if food.description %}
                <div class="mb-6">
                    <h2 class="text-sm font-bold mb-2 flex items-center gap-2">
                        <i class="fas fa-info-circle text-red-500"></i>
                        Подробная информация
                    </h2>
                    <div class="description-text text-sm bg-black/20 p-4 rounded-xl border-l-2 border-red-500">
                        {{ food.description }}
                    </div>
                </div>
                {% endif %}

                <!-- Action Buttons -->
                <div class="flex gap-3 mt-6">
                    <button onclick="window.location.href='/'" class="flex-1 bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800 text-white font-bold py-3 px-4 rounded-xl transition-all active:scale-95 shadow-lg shadow-red-500/30 flex items-center justify-center gap-2 text-xs">
                        <i class="fas fa-arrow-left"></i>
                        На главную
                    </button>
                    <button onclick="shareFood()" class="flex-1 bg-white/10 hover:bg-white/20 border border-white/20 text-white font-bold py-3 px-4 rounded-xl transition-all active:scale-95 flex items-center justify-center gap-2 text-xs">
                        <i class="fas fa-share-alt"></i>
                        Поделиться
                    </button>
                </div>

                <!-- Metadata -->
                <div class="mt-8 pt-6 border-t border-gray-700 text-xs text-gray-500">
                    <p>ID: {{ food.id }} • Добавлено: {{ food.created }}</p>
                </div>
            </div>
        </div>
    </main>

    <script>
        function shareFood() {
            if (navigator.share) {
                navigator.share({
                    title: '{{ food.name }}',
                    text: 'Посмотри это блюдо в ТФС!',
                    url: window.location.href
                }).catch(err => console.log('Share failed:', err));
            } else {
                alert('URL скопирован: ' + window.location.href);
                navigator.clipboard.writeText(window.location.href);
            }
        }
    </script>
</body>
</html>
"""

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/jpeg" href="{{ url_for('static', filename='images/TFC.jpg') }}">
    <title>TFC | Tajik Fried Fish & Chicken</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/gsap.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Fira+Sans+Extra+Condensed:ital,wght@1,900&family=Montserrat:wght@400;700;900&display=swap');
        
        :root {
            --tfc-red: #ff0000;
            --tfc-white: #ffffff;
        }

        body, html { margin:0; padding:0; overflow-x:hidden; font-family:'Montserrat',sans-serif; background:#000; height: 100%; }
        
        .auth-gradient-bg {
            background: radial-gradient(circle at center, #ff0000 0%, #990000 45%, #220000 85%, #000 100%) !important;
            background-size: 150% 150%;
            animation: pulseBG 10s ease-in-out infinite alternate;
        }

        /* CSS Variables for theming */
        :root {
            --tfc-red: #ff0000;
            --tfc-gold: #ffd700;
            --bg-body: #000; /* Main background for dark mode */
            --text-body: #fff; /* Main text color for dark mode */
            --card-bg: rgba(255, 255, 255, 0.05);
            --card-border: rgba(255, 255, 255, 0.12);
            --img-bg: #111;
            --back-btn-bg: var(--tfc-red);
            --back-btn-color: white;
            --back-btn-hover-bg: var(--tfc-gold);
            --back-btn-hover-color: black;
            --review-form-bg: rgba(255, 255, 255, 0.05);
            --review-form-border: rgba(255, 255, 255, 0.1);
            --review-input-bg: rgba(255,255,255,0.05);
            --review-input-border: rgba(255,255,255,0.1);
            --notif-item-bg: rgba(255, 255, 255, 0.05);
            --notif-item-border-left: var(--tfc-gold);
            --text-muted: rgba(255, 255, 255, 0.7);
            --modal-bg-gradient-from: #180202;
            --modal-bg-gradient-mid: #310909;
            --modal-bg-gradient-to: #120202;
            --modal-border: rgba(255, 255, 255, 0.15);
            --modal-header-border: rgba(255, 255, 255, 0.1);
            --modal-text-color: #fff;
            --modal-text-muted: rgba(255,255,255,0.7);
            --modal-qty-bg: rgba(255,255,255,0.05);
            --modal-qty-border: rgba(255,255,255,0.1);
            --modal-qty-btn-bg: rgba(255,255,255,0.1);
            --modal-qty-btn-color: white;
            --modal-footer-bg: rgba(0,0,0,0.2);
            --modal-cancel-btn-bg: rgba(255,255,255,0.1);
            --modal-cancel-btn-hover-bg: rgba(255,255,255,0.2);
            --modal-confirm-btn-bg: #ffcc00;
            --modal-confirm-btn-color: black;
            --modal-confirm-btn-hover-bg: #ffc107;
            --live-status-chip-bg: #ffffff;
            --live-status-chip-color: #1a1a1a;
            --live-status-chip-border-left: #ffd700;
            --live-status-chip-icon-bg-ok: #22c55e;
            --live-status-chip-icon-color-ok: #fff;
            --live-status-chip-icon-bg-pending: #ffc107;
            --live-status-chip-icon-color-pending: #fff;
            --live-status-chip-text-muted: rgba(0,0,0,0.4);
            --live-status-chip-text-main: #333;
            --customer-id-badge-bg: rgba(0, 0, 0, 0.5);
            --customer-id-badge-border: rgba(255, 255, 255, 0.1);
            --customer-id-badge-color: white;
            --top-btn-bg: rgba(255,255,255,0.1);
            --top-btn-border: rgba(255,255,255,0.14);
            --top-btn-color: white;
            --top-btn-hover-bg: rgba(255,255,255,0.16);
            --top-btn-hover-border: rgba(255,215,0,0.45);
            --top-btn-active-bg: rgba(255, 215, 0, 0.15);
            --top-btn-active-border: var(--tfc-gold);
            --shadow-dark-card: 0 15px 35px rgba(0,0,0,0.3);
            --shadow-dark-card-hover: 0 25px 50px rgba(255, 215, 0, 0.15);
        }

        /* Танзимоти махсус барои Акция ва Вакансия: намоиши пурраи матн */
        #aktsii-section .product-card, #vakansii-section .product-card {
            height: auto !important;
            min-height: auto !important;
        }
        #aktsii-section .product-info p, #vakansii-section .product-info .text-sm {
            display: block !important;
            -webkit-line-clamp: unset !important;
            overflow: visible !important;
        }

        body { background-color: var(--bg-body); color: var(--text-body); }

        /* Эффектҳои синамоӣ барои Dark Mode (Default) */
        body:not(.light-active)::before {
            content: "";
            position: fixed;
            inset: 0;
            z-index: -1;
            background-image: 
                linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
            background-size: 50px 50px;
            pointer-events: none;
        }

        body:not(.light-active)::after {
            content: "";
            position: fixed;
            top: -10%;
            left: -10%;
            width: 120%;
            height: 120%;
            z-index: -2;
            background: 
                radial-gradient(circle at 20% 30%, rgba(228, 0, 43, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 80% 70%, rgba(228, 0, 43, 0.05) 0%, transparent 40%),
                linear-gradient(135deg, #0a0a0a 0%, #150202 50%, #000 100%);
            pointer-events: none;
        }

        /* Фигураҳои замина барои режими рӯшноӣ */
        body.light-active::before {
            content: "";
            position: fixed;
            inset: 0;
            z-index: -1;
            background-image: 
                linear-gradient(rgba(0,0,0,0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0,0,0,0.03) 1px, transparent 1px);
            background-size: 50px 50px;
            pointer-events: none;
        }

        body.light-active::after {
            content: "";
            position: fixed;
            top: -10%;
            left: -10%;
            width: 120%;
            height: 120%;
            z-index: -2;
            background: 
                radial-gradient(circle at 20% 30%, rgba(0,0,0,0.05) 0%, transparent 40%),
                radial-gradient(circle at 80% 70%, rgba(0,0,0,0.05) 0%, transparent 40%),
                linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 50%, #d1d5db 100%);
            pointer-events: none;
        }

        /* Стили навиштаҷот дар режими рӯшноӣ */
        body.light-active .tfc-main-title {
            background: linear-gradient(to right, #000 20%, #333 40%, #000 60%);
            -webkit-background-clip: text;
        }

        /* Existing animations and styles, adapted to use variables where appropriate */
        .kulob-tag-mini {
            font-size: 0.8rem;
            letter-spacing: 8px;
            text-transform: uppercase;
            color: rgba(255,255,255,0.7);
            margin-top: -5px;
            opacity: 0;
            animation: trackingIn 1s 0.4s ease forwards;
        }

        @keyframes trackingIn {
            from { letter-spacing: 15px; opacity: 0; }
            to { letter-spacing: 8px; opacity: 1; }
            from { letter-spacing: 10px; opacity: 0; }
            to { letter-spacing: 0px; opacity: 1; }
        }

        .glass-panel {
            background: rgba(139, 0, 0, 0.25);
            backdrop-filter: blur(30px);
            -webkit-backdrop-filter: blur(25px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            padding: 2rem;
            border-radius: 2rem;
            width: 95%;
            max-width: 380px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.6), inset 0 0 20px rgba(255,0,0,0.1);
            opacity: 0;
            transform: scale(0.95);
            animation: panelIn 0.8s 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        /* Auth section specific styles - remains dark */
        @keyframes panelIn {
            to { opacity: 1; transform: scale(1); }
        }

        #sign-out-btn { 
            position:fixed; top:20px; right:20px; z-index: 10000; color:white; width:48px; height:48px; 
            border-radius:50%; display:none; justify-content:center; align-items:center; 
            cursor:pointer; background: rgba(255,255,255,0.1); backdrop-filter: blur(12px);
            background: rgba(0, 0, 0, 0.5); backdrop-filter: blur(12px);
            border: 1px solid rgba(255,255,255,0.1);
            box-shadow: 0 4px 20px rgba(0,0,0,0.35);
            transition: background 0.25s ease, border-color 0.25s ease, transform 0.2s ease;
        }
        #sign-out-btn:hover {
            background: rgba(255,255,255,0.16);
            border-color: rgba(255,215,0,0.45);
            transform: scale(1.05);
        }
        #notif-bell-btn { 
            position:fixed; top:80px; right:20px; z-index: 10000; color:white; width:48px; height:48px; 
            border-radius:50%; display:none; justify-content:center; align-items:center; 
            cursor:pointer; background: rgba(255,255,255,0.1); backdrop-filter: blur(12px);
            background: rgba(0, 0, 0, 0.5); backdrop-filter: blur(12px);
            border: 1px solid rgba(255,255,255,0.1);
            box-shadow: 0 4px 20px rgba(0,0,0,0.35);
            transition: background 0.25s ease, border-color 0.25s ease, transform 0.2s ease;
        }
        #notif-bell-btn:hover {
            background: rgba(255,255,255,0.16);
            border-color: rgba(255,215,0,0.45);
            transform: scale(1.05);
        }
        #theme-toggle-btn {
            position:fixed; top:140px; right:20px; z-index: 10000; color:white; width:48px; height:48px;
            border-radius:50%; display:none; justify-content:center; align-items:center;
            cursor:pointer; background: rgba(255,255,255,0.1); backdrop-filter: blur(12px);
            background: rgba(0, 0, 0, 0.5); backdrop-filter: blur(12px);
            border: 1px solid rgba(255,255,255,0.1);
            box-shadow: 0 4px 20px rgba(0,0,0,0.35);
            transition: all 0.25s ease;
        }
        #theme-toggle-btn:hover {
            background: rgba(255,255,255,0.16);
            border-color: rgba(255,215,0,0.45);
            transform: scale(1.05);
        }
        #lang-toggle-btn {
            position:fixed; top:200px; right:20px; z-index: 10000; color:white; width:48px; height:48px;
            border-radius:50%; display:none; justify-content:center; align-items:center;
            cursor:pointer; background: rgba(255,255,255,0.1); backdrop-filter: blur(12px);
            background: rgba(0, 0, 0, 0.5); backdrop-filter: blur(12px);
            border: 1px solid rgba(255,255,255,0.1);
            box-shadow: 0 4px 20px rgba(0,0,0,0.35);
            transition: all 0.25s ease;
        }
        #lang-toggle-btn:hover {
            background: rgba(255,255,255,0.16);
            border-color: rgba(255,215,0,0.45);
            transform: scale(1.05);
        }
        /* Стили махсус барои ID Badge: шаффофи дарк */
        #customer-id-badge {
            background: var(--customer-id-badge-bg) !important;
            border-color: var(--customer-id-badge-border) !important;
            color: var(--customer-id-badge-color) !important;
        }

        /* Match sign-in widget to same glass / pill language as sign-out & back buttons */
        .auth-google-wrap {
            width: 100%;
            max-width: 300px;
            margin: 0 auto;
            padding: 6px;
            border-radius: 9999px;
            background: rgba(255,255,255,0.08);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255,255,255,0.14);
            box-shadow: 0 4px 24px rgba(0,0,0,0.35);
            transition: background 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
        }
        .auth-google-wrap:hover {
            background: rgba(255,255,255,0.12);
            border-color: rgba(255,215,0,0.4);
            box-shadow: 0 6px 28px rgba(255,0,0,0.15);
        }
        .auth-google-wrap .g_id_signin {
            display: flex !important;
            justify-content: center;
            width: 100%;
        }
        .auth-google-wrap .g_id_signin > div {
            border-radius: 9999px !important;
            overflow: hidden;
        }
        .phone-signin-btn {
            margin-top: 12px;
            width: 100%;
            max-width: 300px;
            border: 1px solid rgba(255,255,255,0.2);
            background: rgba(255,255,255,0.1);
            color: #fff;
            padding: 12px 18px;
            border-radius: 9999px;
            font-weight: 700;
            cursor: pointer;
            transition: 0.25s ease;
        }
        .phone-signin-btn:hover {
            background: rgba(255,255,255,0.18);
            border-color: rgba(255,215,0,0.45);
        }
    </style>
    <style> /* Light mode styles */
        body.light-active {
            --bg-body: silver;
            --bg-body: radial-gradient(circle at 50% 50%, #ffffff 0%, #d1d5db 100%);
            --text-body: #000000;
            --card-bg: #ffffff;
            --card-border: #e0e0e0;
            --img-bg: #ffffff;
            --back-btn-bg: #e4002b;
            --back-btn-color: white;
            --back-btn-hover-bg: #c8102e;
            --back-btn-hover-color: white;
            --review-form-bg: #ffffff;
            --review-form-border: #e0e0e0;
            --review-input-bg: #f9f9f9;
            --review-input-border: #e0e0e0;
            --notif-item-bg: #ffffff;
            --notif-item-border-left: #e4002b;
            --modal-bg-gradient-from: #f5f5f5;
            --modal-bg-gradient-mid: #ffffff;
            --modal-bg-gradient-to: #e8e8e8;
            --modal-border: #e0e0e0;
            --modal-header-border: #f0f0f0;
            --modal-text-color: #000000;
            --modal-text-muted: #333;
            --modal-qty-bg: #f0f0f0;
            --modal-qty-border: #e0e0e0;
            --modal-qty-btn-bg: #e0e0e0;
            --modal-qty-btn-color: #000;
            --modal-footer-bg: #f9f9f9;
            --modal-cancel-btn-bg: #e0e0e0;
            --modal-cancel-btn-hover-bg: #d0d0d0;
            --modal-confirm-btn-bg: #e4002b;
            --modal-confirm-btn-color: white;
            --modal-confirm-btn-hover-bg: #c8102e;
            --live-status-chip-bg: #ffffff;
            --live-status-chip-color: #000000;
            --live-status-chip-border-left: #e4002b;
            --live-status-chip-icon-bg-ok: #28a745;
            --live-status-chip-icon-color-ok: #fff;
            --live-status-chip-icon-bg-pending: #ffc107;
            --live-status-chip-icon-color-pending: #fff;
            --live-status-chip-text-muted: rgba(0,0,0,0.6);
            --live-status-chip-text-main: #000;
            --customer-id-badge-bg: rgba(0, 0, 0, 0.5);
            --customer-id-badge-border: #e0e0e0;
            --customer-id-badge-color: #ffffff;
            --top-btn-bg: #ffffff;
            --top-btn-border: #e0e0e0;
            --top-btn-color: #000;
            --top-btn-hover-bg: #f0f0f0;
            --top-btn-hover-border: #e4002b;
            --top-btn-active-bg: rgba(228, 0, 43, 0.15);
            --top-btn-active-border: #e4002b;
            --shadow-light-card: 0 8px 20px rgba(0,0,0,0.08);
            --shadow-light-card-hover: 0 15px 30px rgba(0,0,0,0.12);
            --text-muted: rgba(0, 0, 0, 0.6);
        }

        /* Ислоҳи рангҳои матн барои режими рӯшноӣ */
        body.light-active #adres-section,
        body.light-active #vakansii-section,
        body.light-active #aktsii-section,
        body.light-active #otziv-section,
        body.light-active #notifications-section {
            color: #000 !important;
        }
        body.light-active #adres-section h4, body.light-active #adres-section p, body.light-active #adres-section a,
        body.light-active #vakansii-section p, body.light-active #vakansii-section div,
        body.light-active #aktsii-section p, body.light-active #aktsii-section div,
        body.light-active #otziv-section p, body.light-active #otziv-section span, body.light-active #otziv-section div,
        body.light-active #notifications-section p, body.light-active #notifications-section div {
            color: #000 !important;
        }
        body.light-active .text-white { color: #000 !important; }
        body.light-active .glass-panel {
            background: rgba(255, 255, 255, 0.9) !important;
            border-color: rgba(0, 0, 0, 0.1) !important;
        }

        /* Ранги сурхи зебо барои иконкаҳои категория ва чаҳорчӯбаи онҳо дар режими рӯшноӣ */
        body.light-active .category-card {
            border: 1px solid rgba(228, 0, 43, 0.15) !important;
            box-shadow: 0 10px 30px rgba(228, 0, 43, 0.15) !important;
        }
        body.light-active .category-card i {
            color: #e4002b !important;
            filter: drop-shadow(0 0 10px rgba(228, 0, 43, 0.5)) !important;
        }

        /* Тугмаҳои поёнӣ (сабад ва занг) дар режими рӯшноӣ: замина сурх ва иконкаҳо зард */
        body.light-active #cart-btn,
        body.light-active #phone-order-btn {
            background-color: #e4002b !important;
            color: #ffd700 !important;
        }

        /* Тугмаҳои болоӣ (баромад, хабарҳо, мавзӯъ) дар режими рӯшноӣ: сиёҳ мисли ID */
        body.light-active #sign-out-btn,
        body.light-active #notif-bell-btn,
        body.light-active #theme-toggle-btn {
            background-color: rgba(0, 0, 0, 0.5) !important;
            color: #e4002b !important;
        }

        /* Танзимоти матн ва хатҳо дар модалҳо барои режими рӯшноӣ */
        body.light-active .order-modal h2,
        body.light-active .order-modal h3,
        body.light-active .order-modal h4,
        body.light-active .order-modal p,
        body.light-active .order-modal label,
        body.light-active .order-modal span:not(.text-yellow-400):not(.text-red-500):not(.text-emerald-400) {
            color: #000000 !important;
        }
        body.light-active .order-modal .text-white\/40,
        body.light-active .order-modal .text-white\/60,
        body.light-active .order-modal .text-white\/70 {
            color: rgba(0, 0, 0, 0.5) !important;
        }
        body.light-active .order-modal .border-white\/10 {
            border-color: rgba(0, 0, 0, 0.08) !important;
        }

        /* Танзимоти махсус барои модалҳои динамикӣ (Внимание, Доставка, Оплата) дар режими рӯшноӣ */
        body.light-active .bg-zinc-900 {
            background-color: #ffffff !important;
            background-image: linear-gradient(160deg, #f5f5f5 0%, #ffffff 50%, #e8e8e8 100%) !important;
            border-color: rgba(0, 0, 0, 0.1) !important;
            box-shadow: 0 25px 50px rgba(0,0,0,0.1) !important;
        }
        body.light-active .bg-zinc-900 h2,
        body.light-active .bg-zinc-900 p,
        body.light-active .bg-zinc-900 span:not(.text-yellow-400):not(.text-red-500),
        body.light-active .bg-zinc-900 label {
            color: #000000 !important;
        }
        body.light-active .bg-zinc-900 .text-white\/60,
        body.light-active .bg-zinc-900 .text-white\/40 {
            color: rgba(0, 0, 0, 0.6) !important;
        }
        body.light-active .bg-zinc-900 .bg-white\/5,
        body.light-active .bg-zinc-900 .bg-black\/20 {
            background-color: rgba(0, 0, 0, 0.05) !important;
            border-color: rgba(0, 0, 0, 0.1) !important;
        }
        body.light-active .bg-zinc-900 textarea {
            background-color: #f9f9f9 !important;
            color: #000000 !important;
            border-color: rgba(0, 0, 0, 0.1) !important;
        }
        /* Ранги паси модалҳо дар режими рӯшноӣ (Backdrop) */
        body.light-active .bg-black\/80,
        body.light-active .bg-black\/90 {
            background-color: rgba(255, 255, 255, 0.6) !important;
        }

        /* Intro Section - remains dark */
        #intro-section {
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            /* Заминаи ниҳоят равшан ва синамоӣ */
            background: radial-gradient(circle at center, #ff3333 0%, #990000 40%, #220000 80%, #000 100%);
            position: relative;
            /* --- MINI PREMIUM ANIMATIONS --- */
            background-size: 110% 110%;
            animation: pulseBG 15s ease-in-out infinite alternate;
        }
        @keyframes pulseBG {
            0%, 100% { background-position: 50% 50%; }
            50% { background-position: 52% 52%; }
        }
        #intro-section .tfc-main-title {
            font-family: "Times New Roman", Times, serif !important;
            font-size: clamp(7rem, 24vw, 16rem); /* Андозаи мувофиқ */
            font-style: italic;
            font-weight: 900; /* Хеле ғафс */
            letter-spacing: 2px; /* Ҳарфҳо каме наздиктар барои намуди яклухт */
            color: white;
            /* Фикс кардани баландии сатр барои пешгирӣ аз ҷаҳиш */
            line-height: 1.3; /* Боз ҳам зиёдтар шуд, то ягон қисми ҳарф бурида нашавад */
            margin: 0;
            display: block;
            opacity: 0;
            /* Истифодаи маводи градиентӣ барои дурахши тиллоӣ */
            background: linear-gradient(to right, #fff 20%, #ffd700 40%, #ffd700 60%, #fff 80%);
            background-size: 200% auto;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            
            transform: translate3d(0, 15px, 0) scale(0.95);
            animation: 
                clearReveal 1.5s cubic-bezier(0.2, 1, 0.2, 1) forwards,
                shinyGold 4s linear infinite 1.5s;
            
            will-change: transform, opacity, background-position;
            backface-visibility: hidden;
            -webkit-font-smoothing: antialiased;
            text-rendering: optimizeLegibility;
        }
        @keyframes clearReveal {
            to { 
                opacity: 1; 
                transform: translate3d(0, 0, 1px) scale(1); 
            }
        }
        @keyframes shinyGold {
            to { background-position: 200% center; }
        }
        .tfc-divider {
            height: 1px; /* Хати бориктар барои намуди премиум */
            width: 260px;
            background: linear-gradient(90deg, transparent, #ffd700, #fff, #ffd700, transparent); /* Silver-Gold */
            margin: 10px auto;
            transform: scaleX(0);
            animation: lineExpand 2.2s 1.2s cubic-bezier(0.2, 1, 0.2, 1) forwards;
            box-shadow: 0 0 15px rgba(255, 215, 0, 0.4);
        }
        @keyframes lineExpand {
            to { transform: scaleX(1); }
        }
        .kulob-tag {
            font-family: "Times New Roman", Times, serif !important;
            font-size: clamp(1rem, 2.5vw, 1.8rem); /* Каме хурдтар барои ҷойгиршавӣ */
            font-size: clamp(0.9rem, 2vw, 1.4rem); /* Андозаи мувофиқ барои як сатр */
            font-size: clamp(1.1rem, 2.5vw, 1.8rem); /* Каме калонтар барои хоно будан */
            font-style: italic;
            font-weight: 700;
            font-weight: 900; /* Ғафс ба монанди TFC */
            color: #ffd700 !important; /* Ранги тиллоӣ */
            text-align: center;
            margin-top: 5px;
            letter-spacing: -0.5px; /* Наздик кардани ҳарфҳо */
            letter-spacing: 1px; /* Фосилаи муқаррарӣ, то ҳарфҳо озод бошанд */
            letter-spacing: -1.5px; /* Ҳарфҳо ниҳоят наздик карда шуданд */
            letter-spacing: 0px; /* Ислоҳ шуд: Фосилаи муқаррарӣ (0) барои хоно будан */
            white-space: nowrap; /* Маҷбур кардан ба як сатр */
            opacity: 0;
            animation: trackingIn 2.5s 1.8s ease forwards;
        }
        .content-section {
            background-color: var(--bg-body);
            color: var(--text-body);
            padding: 100px 20px;
        }
        .category-card {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 24px;
            padding: 50px 20px; /* Default padding */
            text-align: center; /* Default text alignment */
            transition: transform 0.4s cubic-bezier(0.2, 1, 0.2, 1), opacity 0.4s ease;
            cursor: pointer;
            position: relative;
            will-change: transform;
            transform: translateZ(0);
            box-shadow: var(--shadow-dark-card);
            touch-action: manipulation;
        }
        @media (hover: hover) {
            .category-card:hover {
                transform: translateY(-8px);
                border-color: var(--tfc-gold);
                background: var(--card-bg); /* Use variable */
                box-shadow: var(--shadow-dark-card-hover);
            }
        }
        /* Эффект барои пахш дар телефон */
        /* Эффекти пахш барои категорияҳо нест карда шуд, чунки дар поён универсалӣ шуд */
        .category-card i {
            font-size: 3.5rem;
            color: var(--tfc-gold);
            margin-bottom: 20px;
        }
        .category-card h3 {
            font-size: 1.5rem;
            font-weight: 900;
            margin-bottom: 0;
        }
        .product-grid {
            grid-template-columns: repeat(2, 1fr);
            gap: 1rem;
        }
        @media (max-width: 767px) {
            .content-section {
                padding: 20px 2px !important; /* Фосилаи ниҳоят хурд дар канорҳо */
            }
            .product-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 2px !important; /* Фосилаи хурд (2px) дар байни карточкаҳо */
            }
            #vakansii-section .product-grid {
                grid-template-columns: 1fr !important;
                gap: 12px !important;
                padding: 0 10px !important;
            }
            .product-card {
                border-radius: 4px; /* Гӯшаҳои каме мулоим барои намуди зебо */
                border: 0.2px solid rgba(255,255,255,0.1); /* Хати ҷудокунандаи ниҳоят борик */
                background: var(--card-bg); /* Use variable */
                box-shadow: var(--shadow-dark-card);
                min-height: auto; /* Баландии зиёдатиро нест кардем */
            }
            .product-card img {
                width: 100%;
                aspect-ratio: 1 / 1;
                object-fit: cover;
                padding: 0;
                background: #0a0a0a;
            }
            .product-info {
                padding: 4px 4px 28px; /* Паддинги мутавозин */
                text-align: left;
            }
            .product-info h3 {
                font-size: 0.62rem;
                line-height: 1.05;
                margin-bottom: 2px;
                min-height: 1.8em;
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
                overflow: hidden;
                letter-spacing: 0;
            }
            .product-info p {
                font-size: 0.56rem;
                line-height: 1.1;
                margin-bottom: 4px;
                opacity: 0.62;
                min-height: 1.25em;
                display: -webkit-box;
                -webkit-line-clamp: 1;
                -webkit-box-orient: vertical;
                overflow: hidden;
            }
            .price-tag {
                display: inline-block;
                font-size: 0.69rem;
                font-weight: 900;
                padding: 2px 6px;
                border-radius: 999px;
                background: rgba(255, 215, 0, 0.1);
                border: 1px solid rgba(255, 215, 0, 0.24);
            }
            .order-btn {
                bottom: 6px;
                opacity: 1;
                left: 6px;
                right: 6px;
                width: calc(100% - 12px);
                justify-content: center;
                transform: none;
                border-radius: 6px;
                padding: 6px 0;
                height: 34px; /* Баландии зиёдшуда барои мобил */
                display: flex;
                align-items: center;
                gap: 4px;
                font-size: 0.55rem; /* Ҳарфҳо каме калонтар ва равшантар */
                letter-spacing: 0;
                box-shadow: 0 5px 15px rgba(255, 215, 0, 0.3);
                animation: mobileSlideUp 0.6s cubic-bezier(0.2, 1, 0.2, 1) forwards;
            }
            .order-btn i { display: inline-block !important; font-size: 0.9rem; } /* Иконка дар мобил калон карда шуд */
            
            /* Аниматсияи нав барои мобил: вақте зер мекунед, сурат калон мешавад */
            .product-card:active img { transform: scale(1.1); }
            .product-card:active { transform: scale(0.97); transition: 0.1s ease; }

            .product-card:hover .order-btn {
                bottom: 8px;
                transform: none;
            }

            @keyframes mobileSlideUp {
                from { transform: translateY(20px); opacity: 0; }
                to { transform: translateY(0); opacity: 1; }
            }
        }
        @media (min-width: 768px) {
            .product-grid { grid-template-columns: repeat(4, 1fr); }
        }
        @media (min-width: 1024px) {
            .product-grid { grid-template-columns: repeat(5, 1fr); }
        }
        @media (min-width: 1280px) {
            .product-grid { grid-template-columns: repeat(6, 1fr); }
        }
        .product-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 20px;
            overflow: hidden;
            transition: transform 0.4s cubic-bezier(0.2, 1, 0.2, 1);
            box-shadow: var(--shadow-dark-card);
            position: relative;
            will-change: transform;
            transform: translateZ(0);
            cursor: pointer;
        }
        .product-card:hover {
            transform: translateY(-6px) translateZ(0);
            border-color: var(--tfc-gold);
        }
        .product-card.food-card .food-info-sign {
            position: absolute;
            top: 12px;
            right: 12px;
            width: 34px;
            height: 34px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            background: rgba(0, 0, 0, 0.56);
            color: #fff;
            font-weight: 800;
            font-size: 0.95rem;
            border: 1px solid rgba(255, 255, 255, 0.18);
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.25);
            pointer-events: auto;
            cursor: pointer;
            z-index: 10;
            transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
        }
        .product-card.food-card .food-info-sign:active {
            animation: buttonPop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
        }
        @keyframes buttonPop {
            0% { transform: scale(1); background: rgba(0, 0, 0, 0.56); }
            50% { transform: scale(1.3); background: rgba(255, 215, 0, 0.4); }
            100% { transform: scale(1); background: rgba(0, 0, 0, 0.56); }
        }
        .product-card.food-card .food-info-sign:hover {
            background: rgba(255, 255, 255, 0.12);
            border-color: rgba(255, 215, 0, 0.45);
        }
        /* Эффекти зум барои сурат ҳангоми наздик бурдани муш дар компютер */
        .product-card:hover img {
            transform: scale(1.1);
        }
        .product-card img {
            width: 100%;
            aspect-ratio: 1 / 1;
            object-fit: cover;
            background: var(--img-bg);
            padding: 0;
            transition: transform 0.6s cubic-bezier(0.2, 1, 0.2, 1);
        }
        .product-info {
            padding: 12px;
            text-align: center;
            padding-bottom: 60px;
        }
        .product-info h3 { font-size: 1rem; font-weight: 800; margin-bottom: 4px; line-height: 1.2; }
        .product-info p { font-size: 0.8rem; opacity: 0.7; margin-bottom: 8px; line-height: 1.3; }
        .price-tag { font-size: 1.1rem; font-weight: 900; color: var(--tfc-gold); }
        .order-btn {
            position: absolute;
            bottom: -50px;
            left: 50%;
            transform: translateX(-50%);
            background: linear-gradient(90deg, var(--tfc-gold), #ffcc00);
            color: #000;
            padding: 14px 32px; /* Зиёд кардани ғафсӣ дар десктоп */
            border-radius: 50px;
            font-weight: 800;
            font-size: 0.85rem;
            letter-spacing: 0.5px;
            display: inline-flex;
            align-items: center;
            gap: 10px;
            white-space: nowrap;
            opacity: 0;
            box-shadow: var(--shadow-dark-card);
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }
        .product-card:hover .order-btn, .product-card.show-order .order-btn {
            bottom: 15px;
            opacity: 1;
            transform: translateX(-50%) scale(1.06);
        }
        .order-btn { 
            font-family: 'Montserrat', sans-serif; 
            animation: pulseGoldButton 2s infinite;
            transition: all 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }
        .order-btn i { 
            font-size: 1.2rem; /* Иконка дар десктоп калон карда шуд */
            transition: transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1); 
        }
        .product-card:hover .order-btn i {
            transform: rotate(360deg) scale(1.2);
        }
        @keyframes pulseGoldButton {
            0% { box-shadow: 0 0 0 0 rgba(255, 215, 0, 0.6); }
            70% { box-shadow: 0 0 0 10px rgba(255, 215, 0, 0); }
            100% { box-shadow: 0 0 0 0 rgba(255, 215, 0, 0); }
        }
        #theme-toggle {
            /* This was an old theme toggle, now replaced by #theme-toggle-btn */
            display: none;
        }
        .back-btn {
            background: var(--back-btn-bg);
            color: white;
            /* Default color is white, but can be changed by var */
            padding: 12px 30px;
            border-radius: 50px;
            font-weight: 900;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            transition: 0.3s;
        }
        .back-btn:hover {
            background: var(--back-btn-hover-bg);
            color: var(--back-btn-hover-color);
            transform: scale(1.05);
        }
        /* Эффекти пахши back-btn дар блоки универсалӣ танзим мешавад */
        .order-modal-overlay {
            position: fixed;
            inset: 0;
            z-index: 11000;
            background: rgba(0, 0, 0, 0.75);
            backdrop-filter: blur(8px);
            display: none; /* Controlled by JS */
            align-items: center; /* Controlled by JS */
            justify-content: center; /* Controlled by JS */
            padding: 16px; /* Default padding */
            opacity: 0;
            transition: opacity 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
        }
        .order-modal-overlay.active { 
            display: flex;
            opacity: 1;
            animation: backdropFadeIn 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
        }
        @keyframes backdropFadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        .order-modal {
            width: 100%;
            max-width: 520px;
            border-radius: 22px;
            border: 1px solid var(--modal-border);
            background: linear-gradient(160deg, #180202 0%, #310909 50%, #120202 100%);
            color: var(--modal-text-color);
            box-shadow: 0 30px 70px rgba(0, 0, 0, 0.55);
            overflow: hidden;
            /* Аниматсияи ибтидоӣ барои пайдоиши мулоим */
            transform: translateY(60px) scale(0.88);
            opacity: 0;
            background: linear-gradient(160deg, var(--modal-bg-gradient-from) 0%, var(--modal-bg-gradient-mid) 50%, var(--modal-bg-gradient-to) 100%);
            transition: all 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
            will-change: transform, opacity;
        }
        .order-modal-overlay.active .order-modal {
            animation: modalSlideUp 0.7s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
        }
        @keyframes modalSlideUp {
            0% { 
                transform: translateY(60px) scale(0.88); 
                opacity: 0; 
            }
            50% {
                transform: translateY(-5px) scale(1.02);
            }
            100% { 
                transform: translateY(0) scale(1); 
                opacity: 1; 
            }
        }
        .size-btn {
            border: 1px solid var(--modal-qty-border);
            background: var(--modal-qty-bg);
            border-radius: 14px;
            padding: 10px 12px;
            font-weight: 700;
            transition: 0.2s ease;
        }
        .size-btn.active {
            border-color: var(--tfc-gold);
            background: rgba(255, 215, 0, 0.2);
            color: var(--tfc-gold);
        }
        .live-status-chip {
            position: fixed; top: 24px; left: 24px; z-index: 10900;
            background: var(--live-status-chip-bg);
            color: var(--live-status-chip-color); /* Use variable for color */
            border-left: 4px solid var(--live-status-chip-border-left);
            border-radius: 12px;
            padding: 8px 12px;
            font-size: 12px;
            max-width: 250px;
            display: none;
            box-shadow: 0 8px 25px rgba(0,0,0,0.25);
            animation: slideInNotif 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
        }
        @keyframes slideOutNotif {
            from { transform: translateY(0) scale(1); opacity: 1; }
            to { transform: translateY(-20px) scale(0.9); opacity: 0; }
        }
        @keyframes slideInNotif { from { transform: translateY(-100px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
        .live-status-chip.ok { border-left-color: #22c55e; }
        .live-status-chip b { color: #ff0000; font-weight: 800; }

        /* Стили таърихи хабарҳо */
        .notif-item {
            background: var(--notif-item-bg);
            border-left: 4px solid var(--notif-item-border-left);
            margin-bottom: 10px;
        }

        /* ====================== ЭФФЕКТИ УНИВЕРСАЛИИ ПАХШ (GOLD GLOW) ====================== */
        button:active, 
        .order-btn:active, 
        .back-btn:active, 
        #sign-out-btn:active, 
        .phone-signin-btn:active,
        .category-card:active,
        .size-btn:active,
        #notif-bell-btn:active,
        #theme-toggle-btn:active {
            transform: scale(0.92) !important;
            background: rgba(255, 215, 0, 0.15) !important;
            box-shadow: 0 4px 15px rgba(255, 215, 0, 0.2) !important;
            transition: all 0.1s ease !important;
            border-color: var(--tfc-gold) !important;
        }
        
        /* Пешгирӣ аз интихоби матн ва чаҳорчӯбаи кабуд дар телефон */
        button, .category-card, .order-btn, .back-btn, #sign-out-btn, .phone-signin-btn { 
            user-select: none; 
            -webkit-tap-highlight-color: transparent; 
        }

        /* ====================== АНИМАТСИЯИ ГУЗАРИШИ САҲИФАҲО ====================== */
        .page-transition {
            animation: pageIn 0.5s cubic-bezier(0.2, 1, 0.2, 1) forwards;
            will-change: transform, opacity;
        }

        @keyframes pageIn {
            from { opacity: 0; transform: translate3d(0, 20px, 0); }
            to { opacity: 1; transform: translate3d(0, 0, 0); }
        }
        
        /* Аниматсияи дуди шӯрбо (Steam effect) */
        @keyframes steamActive {
            0% { transform: translateY(0) scaleX(1) opacity: 0.5; filter: blur(1px); }
            50% { transform: translateY(-8px) scaleX(1.1) opacity: 0.8; filter: blur(2px); }
            100% { transform: translateY(-15px) scaleX(1.2) opacity: 0; filter: blur(4px); }
        }
        .steam-smoke {
            animation: steamActive 2s infinite linear;
            display: inline-block;
            position: relative;
        }
        
        /* Тӯлонитар кардани карточкаҳо махсус барои бахши тобистона (барои нӯшокиҳо) */
        #summer-menu-section .product-card img {
            aspect-ratio: 3 / 4.5;
            object-fit: cover;
        }
        #summer-menu-section .product-card { min-height: 320px; }

        /* Хурд кардани карточкаи категорияи Отзыв дар мобилӣ */
        @media (max-width: 767px) {
            .category-grid-mobile {
                display: flex !important;
                flex-wrap: wrap !important;
                justify-content: flex-start !important;
                gap: 10px !important;
            }
            .category-card { width: 100% !important; }
            .category-grid-mobile > .category-card { width: 100% !important; }
            /* Ислоҳи паҳнои кортҳо барои дар як сатр истодан */
            #menu .category-card { width: 100% !important; }
            .category-card.otziv-mini, .category-card.aktsii-mini, .category-card.adres-mini, .category-card.vakansii-mini {
                width: calc(50% - 5px) !important;
                padding: 30px 10px !important;
                display: flex !important;
                flex-direction: column !important;
                align-items: center !important;
                margin: 0 !important;
            }
            .category-card.otziv-mini i, .category-card.aktsii-mini i, .category-card.adres-mini i, .category-card.vakansii-mini i { font-size: 2.5rem !important; }
            .category-card.otziv-mini h3, .category-card.aktsii-mini h3, .category-card.adres-mini h3, .category-card.vakansii-mini h3 { font-size: 1.2rem !important; }
            
            /* Small categories grid - 2 per line on all screens */
            #menu > div > div:last-child {
                display: flex !important;
                flex-wrap: wrap !important;
                gap: 1rem;
            }
            #menu > div > div:last-child > div {
                flex: 0 0 calc(50% - 0.5rem) !important;
                width: calc(50% - 0.5rem) !important;
            }
        }

        /* Танзимот барои бахши Отзыв: Паймон ва муосир (2-то дар як сатр) */
        #otziv-section .product-card {
            grid-column: span 1; 
            min-height: 200px;
        }
        #otziv-section .text-review-card {
            min-height: 150px;
            background: linear-gradient(145deg, rgba(255, 255, 255, 0.06) 0%, rgba(255, 255, 255, 0.01) 100%);
            border: 1px dashed rgba(255, 215, 0, 0.2);
        }
        #otziv-section .product-card img {
            aspect-ratio: 1 / 1;
            object-fit: cover;
            background: #000;
        }
        @media (min-width: 768px) { #otziv-section .product-card { min-height: 280px; } }

        /* Стили барои формаи отзыв */
        .review-form {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--review-form-border); /* Use variable for border */
            border-radius: 24px;
            padding: 24px;
            margin-bottom: 40px; /* Default margin */
        }
        .star-rating { display: flex; flex-direction: row-reverse; justify-content: center; gap: 10px; }
        .star-rating input { display: none; }
        .star-rating label { font-size: 2.5rem; color: #333; cursor: pointer; transition: 0.3s; }
        .star-rating input:checked ~ label,
        .star-rating label:hover,
        .star-rating label:hover ~ label { color: var(--tfc-gold); }
        .review-input { background: var(--review-input-bg); border: 1px solid var(--review-input-border); color: var(--text-body); border-radius: 12px; padding: 12px; width: 100%; outline: none; } /* Use variables for background, border, and color */
        .review-input:focus { border-color: var(--tfc-gold); }

        @keyframes buttonPulse {
            0% { box-shadow: 0 0 0 0 rgba(228, 0, 43, 0.4); }
            70% { box-shadow: 0 0 0 10px rgba(228, 0, 43, 0); }
            100% { box-shadow: 0 0 0 0 rgba(228, 0, 43, 0); }
        }

    </style>
</head>
<body>
    <div id="sign-out-btn" onclick="signOut()" title="Выйти из аккаунта">
        <i class="fa-solid fa-right-from-bracket text-base" aria-hidden="true"></i>
        <span class="sr-only">Выйти</span>
    </div>
    <div id="notif-bell-btn" onclick="showNotifications()" title="Уведомления">
        <i class="fa-solid fa-bell text-base" aria-hidden="true"></i>
        <span id="notif-count" class="absolute -top-1 -right-1 bg-yellow-400 text-black text-[10px] font-black min-w-[18px] h-[18px] rounded-full flex items-center justify-center border-2 border-black hidden">0</span>
        <span class="sr-only">Уведомления</span>
    </div>
    <!-- Theme Toggle Button -->
    <div id="theme-toggle-btn" onclick="toggleTheme()" title="Сменить тему">
        <i id="theme-icon" class="fas fa-moon"></i>
        <span class="sr-only">Сменить тему</span>
    </div>

    <div id="customer-id-badge" class="hidden fixed top-5 left-4 z-[10000] px-4 py-2 rounded-full border text-sm font-bold backdrop-blur-md"></div>

    <div id="live-status-chip" class="live-status-chip"></div>

    <div id="cart-btn" onclick="showCart()" class="fixed bottom-5 left-4 z-[10000] bg-red-600 text-white w-14 h-14 rounded-full flex items-center justify-center shadow-2xl border-2 border-white/20 active:scale-90 transition-all cursor-pointer">
        <i class="fa-solid fa-cart-shopping text-xl"></i>
        <span id="cart-count" class="absolute -top-1 -right-1 bg-yellow-400 text-black text-[10px] font-black min-w-[24px] h-6 px-1 rounded-full flex items-center justify-center border-2 border-red-600 hidden">0</span>
    </div>
    <!-- NEW PHONE ORDER BUTTON -->
    <div id="phone-order-btn" onclick="showPhoneOrderModal()" class="fixed bottom-24 left-4 z-[10000] bg-blue-600 text-white w-14 h-14 rounded-full flex items-center justify-center shadow-2xl border-2 border-white/20 active:scale-90 transition-all cursor-pointer">
        <i class="fa-solid fa-phone text-xl"></i>
    </div>

    <!-- CART MODAL OVERLAY -->
    <div id="cart-modal-overlay" class="order-modal-overlay">
        <div class="order-modal">
            <div class="px-6 py-5 border-b border-white/10 flex items-start justify-between">
                <div>
                    <p class="text-xs uppercase tracking-[3px] text-white/40">Ваш Сабад</p>
                    <h3 class="text-2xl font-black mt-1">Список заказов</h3>
                </div>
                <button onclick="closeCartModal()" class="w-10 h-10 rounded-full transition" style="background: var(--modal-qty-btn-bg); color: var(--modal-qty-btn-color);">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
            <div class="px-6 py-4 border-b border-white/10 bg-white/5">
                <label class="block text-[10px] font-black uppercase tracking-widest mb-2" style="color: var(--tfc-gold);">Номер телефона (для связи и оплаты):</label>
                <input id="cart-customer-phone" type="tel" placeholder="+992 _________" 
                       class="w-full px-4 py-3 rounded-xl border border-white/10 bg-black/20 text-white focus:ring-2 focus:ring-yellow-400 outline-none transition font-bold text-lg"
                       maxlength="9">
                <span id="cart-phone-error" class="text-red-500 text-xs mt-1 hidden">Пожалуйста, введите 9 цифр.</span>
            </div>
            <div class="px-6 py-5 max-h-[40vh] overflow-y-auto" id="cart-items-list">
                <!-- Cart items will be injected here --> 
            </div>
            <div class="px-6 py-4 border-t border-white/10">
                <div class="flex justify-between items-center mb-4">
                    <span class="text-white/60">Общая сумма:</span>
                    <span id="cart-total-price" class="text-2xl font-black text-yellow-400">0 сомони</span>
                </div>
                <button onclick="confirmFullCartOrder(event)" class="w-full py-4 rounded-xl font-black text-lg shadow-lg active:scale-95 transition" style="background: var(--modal-confirm-btn-bg); color: var(--modal-confirm-btn-color);">
                    ОФОРМИТЬ ЗАКАЗ
                </button>
            </div>
        </div>
    </div>

    <!-- PHONE ORDER MODAL OVERLAY -->
    <div id="phone-order-modal-overlay" class="order-modal-overlay">
        <div class="order-modal">
            <div class="px-6 py-5 border-b border-white/10 flex items-start justify-between">
                <div>
                    <p class="text-xs uppercase tracking-[3px] text-white/40">Связь с нами</p>
                    <h3 class="text-2xl font-black mt-1">Заказ по телефону</h3>
                </div>
                <button onclick="closePhoneOrderModal()" class="w-10 h-10 rounded-full transition" style="background: var(--modal-qty-btn-bg); color: var(--modal-qty-btn-color);">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
            <div class="px-6 py-5 text-center">
                <div class="w-20 h-20 bg-blue-600/20 text-blue-400 rounded-full flex items-center justify-center mx-auto mb-6 text-4xl shadow-[0_0_30px_rgba(59,130,246,0.2)]">
                    <i class="fa-solid fa-phone-volume"></i>
                </div>
                <p class="text-white/60 text-sm mb-6 leading-relaxed">
                    Для оформления заказа или получения консультации, пожалуйста, позвоните нам.
                </p>
                <a href="tel:754169090" class="w-full py-4 bg-blue-600 text-white font-black rounded-2xl active:scale-95 transition shadow-lg shadow-blue-500/20 uppercase tracking-widest text-xs flex items-center justify-center gap-2">
                    <i class="fas fa-phone"></i> ЗВОНИТЬ И ЗАКАЗАТЬ
                </a>
            </div>
        </div>
    </div>

    <!-- МОДАЛИ ТАСДИҚИ НЕСТ КАРДАНИ ХАБАРҲО -->
    <div id="notif-clear-modal-overlay" class="order-modal-overlay">
        <div class="order-modal">
            <div class="px-6 py-8 text-center">
                <div class="w-20 h-20 bg-red-600/20 text-red-600 rounded-full flex items-center justify-center mx-auto mb-6 text-4xl shadow-[0_0_30px_rgba(228,0,43,0.2)]">
                    <i class="fa-solid fa-trash-can"></i>
                </div>
                <h2 class="text-xl font-black mb-2 uppercase tracking-tight">ОЧИСТИТЬ ИСТОРИЮ?</h2>
                <p class="text-sm opacity-60 mb-8 leading-relaxed">
                    Вы действительно хотите удалить все уведомления? Это действие нельзя отменить.
                </p>
                <div class="flex flex-col gap-3">
                    <button onclick="executeClearNotifications()" class="w-full py-4 bg-red-600 text-white font-black rounded-2xl active:scale-95 transition shadow-lg shadow-red-500/20 uppercase tracking-widest text-xs">
                        УДАЛИТЬ СРАЗУ
                    </button>
                    <button onclick="closeNotifClearModal()" class="w-full py-4 bg-white/10 text-white/60 font-black rounded-2xl active:scale-95 transition uppercase tracking-widest text-xs">
                        ОТМЕНА
                    </button>
                </div>
            </div>
        </div>
    </div>

    <div id="food-info-overlay" class="order-modal-overlay">
        <div class="order-modal">
            <div class="px-6 py-5 border-b border-white/10 flex items-start justify-between gap-4">
                <div>
                    <p class="text-xs uppercase tracking-[3px] text-white/40">Полная информация</p>
                    <h3 id="info-food-title" class="text-2xl font-black mt-1">Блюдо</h3>
                </div>
                <button onclick="closeFoodInfoOverlay()" class="w-10 h-10 rounded-full transition" style="background: var(--modal-qty-btn-bg); color: var(--modal-qty-btn-color);">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
            <div class="px-6 py-4 space-y-4 max-h-[75vh] overflow-y-auto">
                <img id="info-food-image" src="" alt="" class="w-full max-h-64 object-contain rounded-2xl border border-white/10 bg-black/10 mx-auto" style="height: auto;">
                <div class="p-3 rounded-2xl bg-white/5 border border-white/10">
                    <div id="info-food-description" class="text-xs leading-relaxed whitespace-pre-wrap" style="color: var(--modal-text-muted);"></div>
                </div>
                <div class="p-3 rounded-2xl bg-white/5 border border-white/10 flex justify-between items-center">
                    <h4 class="text-sm font-black uppercase tracking-widest opacity-60">Цена</h4>
                    <p id="info-food-price" class="text-xl font-black text-yellow-400"></p>
                </div>
            </div>
        </div>
    </div>

    <div id="order-modal-overlay" class="order-modal-overlay">
        <div class="order-modal">
            <div class="px-6 py-5 border-b border-white/10 flex items-start justify-between gap-4">
                <div>
                    <p class="text-xs uppercase tracking-[3px] text-white/40">Страница заказа</p>
                    <h3 id="modal-food-title" class="text-2xl font-black mt-1">Блюдо</h3>
                </div>
                <button onclick="closeOrderModal()" class="w-10 h-10 rounded-full transition" style="background: var(--modal-qty-btn-bg); color: var(--modal-qty-btn-color);">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
            <div class="px-6 py-5">
                <div class="mb-4">
                    <label class="block text-sm mb-2 font-bold" style="color: var(--tfc-gold);">Введите ваш номер телефона:</label>
                    <input id="modal-customer-phone" name="user_ph_no_fill" type="tel" placeholder="+992 _________" autocomplete="new-password" 
                           class="w-full px-4 py-3 rounded-xl border border-white/10 bg-white/5 text-white focus:ring-2 focus:ring-yellow-400 outline-none transition"
                           maxlength="9">
                    <span id="modal-phone-error" class="text-red-500 text-xs mt-1 hidden">Пожалуйста, введите 9 цифр.</span>
                </div>
                <p class="text-sm mb-3" style="color: var(--modal-text-muted);">Пожалуйста, выберите:</p>
                <div id="size-options" class="grid grid-cols-2 gap-3 mb-4"></div>
                <div class="mb-4">
                    <label class="block text-sm mb-2" style="color: var(--modal-text-muted);">Сколько штук хотите?</label>
                    <div class="flex items-center justify-between p-1 rounded-2xl max-w-[160px] mx-auto" style="background: var(--modal-qty-bg); border: 1px solid var(--modal-qty-border);">
                        <button onclick="changeQty(-1)" class="w-10 h-10 shrink-0 rounded-xl flex items-center justify-center active:scale-90 transition" style="background: var(--modal-qty-btn-bg); color: var(--modal-qty-btn-color);">
                            <i class="fa-solid fa-minus text-sm"></i>
                        </button>
                        <input id="modal-qty" type="number" min="1" value="1" readonly class="w-12 bg-transparent text-center text-xl font-black outline-none" style="color: var(--modal-text-color);">
                        <button onclick="changeQty(1)" class="w-10 h-10 shrink-0 rounded-xl flex items-center justify-center active:scale-90 transition" style="background: var(--modal-confirm-btn-bg); color: var(--modal-confirm-btn-color);">
                            <i class="fa-solid fa-plus text-sm"></i>
                        </button>
                    </div>
                </div>
                <p class="text-sm" style="color: var(--modal-text-muted);">Итого: <span id="modal-total" class="font-black text-lg" style="color: var(--tfc-gold);">0 сомони</span></p>
            </div>
            <div class="px-6 py-4 flex gap-3" style="background: var(--modal-footer-bg);">
                <button onclick="addToCart()" class="flex-1 py-3 rounded-xl font-bold text-xs" style="background: var(--modal-cancel-btn-bg); color: var(--modal-qty-btn-color);">В КОРЗИНУ</button>
                <button onclick="confirmOrderFromModal(event)" class="flex-1 py-3 rounded-xl font-black text-xs" style="background: var(--modal-confirm-btn-bg); color: var(--modal-confirm-btn-color);">ЗАКАЗАТЬ</button>
            </div>
        </div>
    </div>

    <section id="auth-section" class="fixed inset-0 auth-gradient-bg z-[9999] flex flex-col items-center justify-center">
        <div class="text-center mb-6">
            <h1 class="tfc-main-title">TFC</h1>
            <div class="kulob-tag-mini">Tajik Fried Fish & Chicken</div> 
        </div>

        <div class="glass-panel text-center">
            <h2 class="text-white text-2xl font-black mb-1 uppercase tracking-tight">Вход в систему</h2>
            <p class="text-white/70 text-[10px] uppercase tracking-[3px] mb-8">Введите ваше имя и фамилию</p>
            
            <div id="login-container">
                <input id="auth-name-input" type="text" placeholder="Имя и Фамилия" 
                       class="w-full px-4 py-4 rounded-2xl border border-white/20 bg-white/10 text-white mb-6 focus:ring-2 focus:ring-yellow-400 outline-none text-center text-xl font-bold transition-all"
                       maxlength="100">
                <button id="login-btn" class="w-full py-4 bg-yellow-400 text-black font-black rounded-2xl active:scale-95 transition-all shadow-lg shadow-yellow-400/20 uppercase text-xs tracking-widest" onclick="handleSimpleLogin()">
                    Войти в меню
                </button>
            </div>

            <div class="mt-10 pt-6 border-t border-white/10">
                <p class="text-[9px] text-white/30 uppercase tracking-[5px] font-bold">Tajik Fried Chicken</p>
            </div>
        </div>
    </section>
    <main id="main-content" class="hidden">
    <!-- Intro Section -->
    <section id="intro-section">
        <div class="text-center -mt-32" style="color: var(--text-body);">
            <h1 class="tfc-main-title">TFC</h1>
            <div class="tfc-divider"></div>
            <div class="kulob-tag">Tajik Fried Fish & Chicken</div>
        </div>
    </section>

    <!-- Main Menu -->
    <section class="content-section" id="menu">
        <div class="max-w-7xl mx-auto" style="color: var(--text-body);">
            <!-- Main Categories -->
            <div class="category-grid-mobile grid grid-cols-2 md:grid-cols-2 lg:grid-cols-2 gap-4 md:gap-8 mb-8">
                <div class="category-card" onclick="showMenu()">
                    <i class="fa-solid fa-utensils"></i>
                    <h3>Меню</h3>
                </div>

                <div class="category-card" onclick="showPizza()">
                    <i class="fa-solid fa-pizza-slice"></i>
                    <h3>Пицца</h3>
                </div>
                <div class="category-card" onclick="showSushi()">
                    <i class="fa-solid fa-shrimp"></i>
                    <h3>Суши</h3>
                </div>
                <div class="category-card" onclick="showFastFood()">
                    <i class="fa-solid fa-burger"></i>
                    <h3>Фастфуд</h3>
                </div>
                <div class="category-card" onclick="showSummerMenu()">
                    <i class="fa-solid fa-lemon"></i>
                    <h3>Летнее меню</h3>
                </div>
                <div class="category-card" onclick="showCombo()">
                    <i class="fa-solid fa-fire-flame-curved"></i>
                    <h3>Комбо</h3>
                </div>
            </div>

            <!-- Small Categories -->
            <div class="category-grid-mobile grid grid-cols-2 md:grid-cols-2 lg:grid-cols-2 gap-4 md:gap-8 mb-12">
                <div class="category-card otziv-mini text-sm" onclick="showOtziv()">
                    <i class="fa-solid fa-star text-2xl"></i>
                    <h3 class="text-sm">Отзывы</h3>
                </div>
                <div class="category-card aktsii-mini text-sm" onclick="showAktsii()">
                    <i class="fa-solid fa-tags text-2xl"></i>
                    <h3 class="text-sm">Акции</h3>
                </div>
                <div class="category-card adres-mini text-sm" onclick="showAdres()">
                    <i class="fa-solid fa-location-dot text-2xl"></i>
                    <h3 class="text-sm">Адрес</h3>
                </div>
                <div class="category-card vakansii-mini text-sm" onclick="showVakansii()">
                    <i class="fa-solid fa-briefcase text-2xl"></i>
                    <h3 class="text-sm">Вакансии</h3>
                </div>
            </div>
        </div>
    </section>
    <!-- ====================== МЕНЮИ КОМИЛ ====================== -->
    <section id="menu-section" class="content-section" style="display: none;">
        <div class="max-w-7xl mx-auto">
            <div class="flex justify-center mb-10" style="color: var(--text-body);">
                <button id="main-back-btn" onclick="hideMenu()" class="back-btn">
                    <i class="fa-solid fa-arrow-left"></i> <span>В ГЛАВНОЕ МЕНЮ</span>
                </button>
                <button id="category-back-btn" onclick="showMenu()" class="back-btn" style="display: none;">
                    <i class="fa-solid fa-rotate-left"></i> <span>К КАТЕГОРИЯМ</span>
                </button>
            </div>
            <h2 class="text-5xl font-black text-center mb-8 tracking-widest" style="color: var(--tfc-gold);">МЕНЮ</h2>
            
            <!-- Sub-category cards for "Меню" -->
            <div id="menu-subcategories" class="grid grid-cols-2 gap-4 md:gap-8 mb-12 page-transition" style="display: none;">
                <!-- Row 1: Pasta & Salads -->
                <div class="category-card hover:shadow-[0_0_20px_rgba(255,215,0,0.3)] transition-all" onclick="filterMenu('Паста')">
                    <span class="text-6xl mb-2 block">🍝</span>
                    <h3>Паста</h3>
                </div>
                <div class="category-card hover:shadow-[0_0_20px_rgba(255,215,0,0.3)] transition-all" onclick="filterMenu('Салаты')">
                    <span class="text-6xl mb-2 block">🥗</span>
                    <h3>Салаты</h3>
                </div>

                <!-- Row 2: Soups (Full Width) -->
                <div class="category-card col-span-2 hover:shadow-[0_0_20px_rgba(255,165,0,0.3)] transition-all" onclick="filterMenu('Супы')">
                    <span class="text-7xl mb-2 block">🥣</span>
                    <h3>Супы</h3>
                </div>

                <!-- Row 3: Hot Dishes & Desserts -->
                <div class="category-card hover:shadow-[0_0_20px_rgba(255,215,0,0.3)] transition-all" onclick="filterMenu('Горячие блюда')">
                    <span class="text-6xl mb-2 block">🍖</span>
                    <h3>Горячие блюда</h3>
                </div>
                <div class="category-card hover:shadow-[0_0_20px_rgba(255,215,0,0.3)] transition-all" onclick="filterMenu('Десерты')">
                    <span class="text-6xl mb-2 block">🍰</span>
                    <h3>Десерты</h3>
                </div>

                <!-- Row 4: Drinks (Full Width) -->
                <div class="category-card col-span-2 hover:shadow-[0_0_20px_rgba(0,191,255,0.3)] transition-all" onclick="filterMenu('Напитки')">
                    <span class="text-6xl mb-2 block">☕</span>
                    <h3>Напитки</h3>
                </div>
            </div>
            <div id="filtered-product-grid" class="grid product-grid gap-8">
                {% for food in categories.get('Меню', []) %}
                <div class="product-card food-card" data-food-id="{{ food.id }}" data-name="{{ food.name }}" data-subcategory="{{ food.subcategory|default('') }}" data-description="{{ food.description|e }}">
                    <img src="{{ url_for('static', filename='images/' + food.image_url) if food.image_url else '' }}" alt="{{ food.name }}">
                    <div class="food-description hidden">{{ food.description }}</div>
                    <div class="food-info-sign" title="Полная информация о блюде">...</div>
                    <div class="product-info">
                        <h3>{{ food.name }}</h3>
                        <div class="price-tag">{{ food.price }}с</div>
                    </div>
                    <div class="order-btn"><span>ЗАКАЗАТЬ</span> <i class="fa-solid fa-cart-shopping"></i></div>
                </div>
                {% endfor %}
            </div>
        </div>
    </section>
    <!-- ====================== ФАСТФУД ====================== -->
    <section id="fastfood-section" class="content-section" style="display: none;">
        <div class="max-w-7xl mx-auto">
            <div class="flex justify-center mb-10" style="color: var(--text-body);">
                <button id="fastfood-main-back-btn" onclick="hideFastFood()" class="back-btn">
                    <i class="fa-solid fa-arrow-left"></i> <span>В ГЛАВНОЕ МЕНЮ</span>
                </button>
                <button id="fastfood-category-back-btn" onclick="showFastFood()" class="back-btn" style="display: none;">
                    <i class="fa-solid fa-rotate-left"></i> <span>К КАТЕГОРИЯМ</span>
                </button>
            </div>
            <h2 class="text-5xl font-black text-center mb-8 tracking-widest" style="color: var(--tfc-gold);">ФАСТФУД</h2>
            
            <!-- Sub-category cards for "Фастфуд" -->
            <div id="fastfood-subcategories" class="grid grid-cols-2 gap-4 md:gap-8 mb-12 page-transition" style="display: none;">
                <div class="category-card hover:shadow-[0_0_20px_rgba(255,215,0,0.3)] transition-all" onclick="filterFastFood('Хот-доги')">
                    <span class="text-6xl mb-2 block">🌭</span>
                    <h3>Хот-доги</h3>
                </div>
                <div class="category-card hover:shadow-[0_0_20px_rgba(255,215,0,0.3)] transition-all" onclick="filterFastFood('Бургеры')">
                    <span class="text-6xl mb-2 block">🍔</span>
                    <h3>Бургеры</h3>
                </div>
                <div class="category-card hover:shadow-[0_0_20px_rgba(255,215,0,0.3)] transition-all" onclick="filterFastFood('Тортильи')">
                    <span class="text-6xl mb-2 block">🌯</span>
                    <h3>Тортильи</h3>
                </div>
                <div class="category-card hover:shadow-[0_0_20px_rgba(255,215,0,0.3)] transition-all" onclick="filterFastFood('Сэндвичи')">
                    <span class="text-6xl mb-2 block">🥪</span>
                    <h3>Сэндвичи</h3>
                </div>
                <div class="category-card col-span-2 hover:shadow-[0_0_20px_rgba(255,215,0,0.3)] transition-all" onclick="filterFastFood('Гарниры')">
                    <span class="text-6xl mb-2 block">🍟</span>
                    <h3>Гарниры</h3>
                </div>
            </div>

            <div id="fastfood-filtered-product-grid" class="grid product-grid gap-8">
                {% for food in categories.get('Фастфуд', []) %}
                <div class="product-card food-card" data-food-id="{{ food.id }}" data-name="{{ food.name }}" data-subcategory="{{ food.subcategory|default('') }}" data-description="{{ food.description|e }}">
                    <img src="{{ url_for('static', filename='images/' + food.image_url) if food.image_url else '' }}" alt="{{ food.name }}">
                    <div class="food-description hidden">{{ food.description }}</div>
                    <div class="food-info-sign" title="Полная информация о блюде">...</div>
                    <div class="product-info">
                        <h3>{{ food.name }}</h3>
                        <div class="price-tag">{{ food.price }}с</div>
                    </div>
                    <div class="order-btn"><span>ЗАКАЗАТЬ</span> <i class="fa-solid fa-cart-shopping"></i></div>
                </div>
                {% endfor %}
            </div>
        </div>
    </section>
    <!-- ====================== СУШИ ВА РОЛЛҲО ====================== -->
    <section id="sushi-section" class="content-section" style="display: none;">
        <div class="max-w-7xl mx-auto">
            <div class="flex justify-center mb-10" style="color: var(--text-body);">
                <button id="sushi-main-back-btn" onclick="hideSushi()" class="back-btn">
                    <i class="fa-solid fa-arrow-left"></i> <span>В ГЛАВНОЕ МЕНЮ</span>
                </button>
                <button id="sushi-category-back-btn" onclick="showSushi()" class="back-btn" style="display: none;">
                    <i class="fa-solid fa-rotate-left"></i> <span>К КАТЕГОРИЯМ</span>
                </button>
            </div>
            <h2 class="text-5xl font-black text-center mb-8 tracking-widest" style="color: var(--tfc-gold);">СУШИ И РОЛЛЫ</h2>

            <!-- Sub-category cards for "Суши" -->
            <div id="sushi-subcategories" class="grid grid-cols-2 gap-4 md:gap-8 mb-12 page-transition" style="display: none;">
                <div class="category-card hover:shadow-[0_0_20px_rgba(255,215,0,0.3)] transition-all" onclick="filterSushi('Суши')">
                    <span class="text-6xl mb-2 block">🍣</span>
                    <h3 class="text-xl font-bold">Суши</h3>
                </div>
                <div class="category-card hover:shadow-[0_0_20px_rgba(255,215,0,0.3)] transition-all" onclick="filterSushi('Роллы')">
                    <span class="text-6xl mb-2 block">🍱</span>
                    <h3 class="text-xl font-bold">Роллы</h3>
                </div>
            </div>

            <div id="sushi-filtered-product-grid" class="grid product-grid gap-8">
                {% for food in categories.get('Суши', []) %}
                <div class="product-card food-card" data-food-id="{{ food.id }}" data-name="{{ food.name }}" data-subcategory="{{ food.subcategory|default('') }}" data-description="{{ food.description|e }}">
                    <img src="{{ url_for('static', filename='images/' + food.image_url) if food.image_url else '' }}" alt="{{ food.name }}">
                    <div class="food-description hidden">{{ food.description }}</div>
                    <div class="food-info-sign" title="Полная информация о блюде">...</div>
                    <div class="product-info">
                        <h3>{{ food.name }}</h3>
                        <div class="price-tag">{{ food.price }}с</div>
                    </div>
                    <div class="order-btn"><span>ЗАКАЗАТЬ</span> <i class="fa-solid fa-cart-shopping"></i></div>
                </div>
                {% endfor %}
            </div>
        </div>
    </section>
    <!-- ====================== ПИЦЦА ====================== -->
    <section id="pizza-section" class="content-section" style="display: none;">
        <div class="max-w-7xl mx-auto">
            <div class="flex justify-center mb-10" style="color: var(--text-body);">
                <button id="pizza-main-back-btn" onclick="hidePizza()" class="back-btn">
                    <i class="fa-solid fa-arrow-left"></i> <span>В ГЛАВНОЕ МЕНЮ</span>
                </button>
                <button id="pizza-category-back-btn" onclick="showPizza()" class="back-btn" style="display: none;">
                    <i class="fa-solid fa-rotate-left"></i> <span>К КАТЕГОРИЯМ</span>
                </button>
            </div>
            <h2 class="text-5xl font-black text-center mb-8 tracking-widest" style="color: var(--tfc-gold);">ПИЦЦА</h2>
            
            <!-- Sub-category cards for "Пицца" -->
            <div id="pizza-subcategories" class="grid grid-cols-2 gap-4 md:gap-8 mb-12 page-transition" style="display: none;">
                <div class="category-card hover:shadow-[0_0_20px_rgba(255,215,0,0.3)] transition-all" onclick="filterPizza('Пицца')">
                    <span class="text-6xl mb-2 block">🍕</span>
                    <h3>Пицца</h3>
                </div>
                <div class="category-card hover:shadow-[0_0_20px_rgba(255,215,0,0.3)] transition-all" onclick="filterPizza('Хачапури')">
                    <span class="text-6xl mb-2 block">🧀</span>
                    <h3>Хачапури</h3>
                </div>
            </div>

            <div id="pizza-filtered-product-grid" class="grid product-grid gap-8">
                {% for food in categories.get('Пицца', []) %}
                <div class="product-card food-card" data-food-id="{{ food.id }}" data-name="{{ food.name }}" data-subcategory="{{ food.subcategory|default('') }}" data-description="{{ food.description|e }}">
                    <img src="{{ url_for('static', filename='images/' + food.image_url) if food.image_url else '' }}" alt="{{ food.name }}">
                    <div class="food-description hidden">{{ food.description }}</div>
                    <div class="food-info-sign" title="Полная информация о блюде">...</div>
                    <div class="product-info">
                        <h3>{{ food.name }}</h3>
                        <div class="price-tag">{{ food.price }}с</div>
                    </div>
                    <div class="order-btn"><span>ЗАКАЗАТЬ</span> <i class="fa-solid fa-cart-shopping"></i></div>
                </div>
                {% endfor %}
            </div>
        </div>
    </section>

    <!-- ====================== ЛЕТНЕЕ МЕНЮ ====================== -->
    <section id="summer-menu-section" class="content-section" style="display: none;">
        <div class="max-w-7xl mx-auto">
            <div class="flex justify-center mb-10" style="color: var(--text-body);">
                <button id="summer-main-back-btn" onclick="hideSummerMenu()" class="back-btn">
                    <i class="fa-solid fa-arrow-left"></i> <span>В ГЛАВНОЕ МЕНЮ</span>
                </button>
                <button id="summer-category-back-btn" onclick="showSummerMenu()" class="back-btn" style="display: none;">
                    <i class="fa-solid fa-rotate-left"></i> <span>К КАТЕГОРИЯМ</span>
                </button>
            </div>
            <h2 class="text-5xl font-black text-center mb-8 tracking-widest" style="color: var(--tfc-gold);">ЛЕТНЕЕ МЕНЮ</h2>
            
            <!-- Sub-category cards for "Летнее меню" -->
            <div id="summer-menu-subcategories" class="grid grid-cols-2 gap-4 md:gap-8 mb-12 page-transition" style="display: none;">
                <!-- Row 1: Smoothies & Cocktails -->
                <div class="category-card hover:shadow-[0_0_20px_rgba(255,215,0,0.3)] transition-all" onclick="filterSummerMenu('Смузи')">
                    <span class="text-6xl mb-2 block">🍹</span>
                    <h3>Смузи</h3>
                </div>
                <div class="category-card hover:shadow-[0_0_20px_rgba(255,215,0,0.3)] transition-all" onclick="filterSummerMenu('Мохито')">
                    <span class="text-6xl mb-2 block">🍸</span>
                    <h3>Мохито</h3>
                </div>

                <!-- Row 2: Refreshing Drinks (Full Width) -->
                <div class="category-card col-span-2 hover:shadow-[0_0_20px_rgba(0,191,255,0.3)] transition-all" onclick="filterSummerMenu('Холодок')">
                    <span class="text-6xl mb-2 block">❄️</span>
                    <h3 class="text-sm">Холодок</h3>
                </div>
            </div>

            <div id="summer-menu-filtered-product-grid" class="grid product-grid gap-8">
                {% for food in categories.get('Летнее меню', []) %}
                <div class="product-card food-card" data-food-id="{{ food.id }}" data-name="{{ food.name }}" data-subcategory="{{ food.subcategory|default('') }}" data-description="{{ food.description|e }}">
                    <img src="{{ url_for('static', filename='images/' + food.image_url) if food.image_url else '' }}" alt="{{ food.name }}">
                    <div class="food-description hidden">{{ food.description }}</div>
                    <div class="food-info-sign" title="Полная информация о блюде">...</div>
                    <div class="product-info">
                        <h3>{{ food.name }}</h3>
                        <div class="price-tag">{{ food.price }}с</div>
                    </div>
                    <div class="order-btn"><span>ЗАКАЗАТЬ</span> <i class="fa-solid fa-cart-shopping"></i></div>
                </div>
                {% endfor %}
            </div>
        </div>
    </section>

    <!-- ====================== КОМБО ====================== -->
    <section id="combo-section" class="content-section" style="display: none;">
        <div class="max-w-7xl mx-auto">
            <div class="flex justify-center mb-10" style="color: var(--text-body);">
                <button onclick="hideCombo()" class="back-btn">
                    <i class="fa-solid fa-arrow-left"></i> <span>В ГЛАВНОЕ МЕНЮ</span>
                </button>
            </div>
            <h2 class="text-5xl font-black text-center mb-12 tracking-widest" style="color: var(--tfc-gold);">КОМБО</h2>
            <div class="grid product-grid gap-8">
                {% for food in categories.get('Комбо', []) %}
                <div class="product-card food-card" data-food-id="{{ food.id }}" data-name="{{ food.name }}" data-subcategory="{{ food.subcategory|default('') }}" data-description="{{ food.description|e }}">
                    <img src="{{ url_for('static', filename='images/' + food.image_url) if food.image_url else '' }}" alt="{{ food.name }}">
                    <div class="food-description hidden">{{ food.description }}</div>
                    <div class="food-info-sign" title="Полная информация о блюде">...</div>
                    <div class="product-info">
                        <h3>{{ food.name }}</h3>
                        <div class="price-tag">{{ food.price }}с</div>
                    </div>
                    <div class="order-btn"><span>ЗАКАЗАТЬ</span> <i class="fa-solid fa-cart-shopping"></i></div>
                </div>
                {% endfor %}
            </div>
        </div>
    </section>

    <!-- ====================== ОТЗЫВЫ ====================== -->
    <section id="otziv-section" class="content-section" style="display: none;">
        <div class="max-w-7xl mx-auto">
            <div class="flex justify-center mb-10" style="color: var(--text-body);">
                <button onclick="hideOtziv()" class="back-btn">
                    <i class="fa-solid fa-arrow-left"></i> <span>В ГЛАВНОЕ МЕНЮ</span>
                </button>
            </div>
            <h2 class="text-5xl font-black text-center mb-4 tracking-widest" style="color: var(--tfc-gold);">ОТЗЫВЫ</h2> <!-- Use variable for color -->
            <p class="text-center text-xl opacity-70 mb-12">Отзывы наших клиентов</p>
            
            <!-- Формаи навиштани отзыв -->
            <div class="max-w-xl mx-auto review-form">
                <h4 class="text-center font-bold mb-4">Напишите свой отзыв</h4>
                <div class="star-rating mb-4">
                    <input type="radio" name="rating" id="star5" value="5"><label for="star5">★</label>
                    <input type="radio" name="rating" id="star4" value="4"><label for="star4">★</label>
                    <input type="radio" name="rating" id="star3" value="3"><label for="star3">★</label>
                    <input type="radio" name="rating" id="star2" value="2"><label for="star2">★</label>
                    <input type="radio" name="rating" id="star1" value="1"><label for="star1">★</label>
                </div>
                <textarea id="rev-text" class="review-input mb-4" rows="3" placeholder="Ваше мнение о TFC..." style="color: var(--text-body);"></textarea>
                <div class="mb-4">
                    <label class="block text-[10px] font-bold mb-2 opacity-40 uppercase tracking-widest">Прикрепить фото (по желанию)</label>
                    <input type="file" id="rev-image" accept="image/*" 
                           class="w-full text-[10px] text-white/50 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-[10px] file:font-bold file:bg-white/10 file:text-white hover:file:bg-white/20 cursor-pointer">
                </div>
                <button onclick="submitReview()" class="w-full py-4 rounded-xl font-black active:scale-95 transition" style="background: var(--modal-confirm-btn-bg); color: var(--modal-confirm-btn-color);">ОТПРАВИТЬ</button>
            </div>

            <!-- Бахши отзывҳо: Матнӣ ва Суратдор дар як grid -->
            <div class="grid product-grid gap-8">
                <!-- 1. Отзывҳои матнӣ -->
                {% for rev in text_reviews %}
                <div class="product-card text-review-card flex flex-col justify-between p-4" style="background: var(--card-bg); border: 1px dashed var(--notif-item-border-left);">
                    <div class="flex flex-col">
                        {% if rev.image_url %}
                        <img src="{{ url_for('static', filename='images/' + rev.image_url) }}" class="w-full aspect-square object-cover rounded-xl mb-3 shadow-lg">
                        {% endif %}
                        <div class="flex justify-between items-start mb-2">
                            <h5 class="font-bold text-[10px] uppercase" style="color: var(--tfc-gold);">{{ rev.name }}</h5>
                            <div class="text-[9px]" style="color: var(--tfc-gold);">
                                {% for i in range(rev.stars|int) %}
                                ★
                                {% endfor %}
                            </div>
                        </div>
                        <p class="text-base sm:text-xl opacity-95 italic font-medium leading-relaxed" style="letter-spacing: -0.01em;">"{{ rev.text }}"</p>
                    </div>
                    <div class="flex justify-between items-end mt-4">
                        <div class="text-[10px] opacity-30 uppercase tracking-widest">{{ rev.created }}</div>
                        <button onclick="deleteReview({{ rev.id }})" class="text-red-600/50 hover:text-red-600 transition-colors p-1" title="Удалить отзыв">
                            <i class="fas fa-trash-alt text-[10px]"></i>
                        </button>
                    </div>
                </div>
                {% endfor %}

                <!-- 2. Отзывҳои суратдор -->
                {% for food in [] %}
                <div class="product-card">
                    <img src="{{ url_for('static', filename='images/' + food.image_url) if food.image_url else '' }}" alt="{{ food.name }}">
                    <div class="product-info">
                        <h3>{{ food.name }}</h3>
                        <div class="price-tag">{{ food.price }}с</div>
                    </div>
                    <div class="order-btn"><span>ЗАКАЗАТЬ</span> <i class="fa-solid fa-cart-shopping"></i></div>
                </div>
                {% endfor %}
            </div>
        </div>
    </section>

    <!-- ====================== АКЦИИ ====================== -->
    <section id="aktsii-section" class="content-section" style="display: none;">
        <div class="max-w-7xl mx-auto">
            <div class="flex justify-center mb-10" style="color: var(--text-body);">
                <button onclick="hideAktsii()" class="back-btn">
                    <i class="fa-solid fa-arrow-left"></i> <span>В ГЛАВНОЕ МЕНЮ</span>
                </button>
            </div>
            <h2 class="text-5xl font-black text-center mb-4 tracking-widest" style="color: var(--tfc-gold);">АКЦИИ</h2> <!-- Use variable for color -->
            <p class="text-center text-xl opacity-70 mb-12">Специальные предложения и скидки</p>

            <div class="grid grid-cols-1 xl:grid-cols-2 gap-8 mb-12">
                {% for item in aktsii %}
                <div class="product-card overflow-hidden border border-white/10 shadow-xl" style="background: rgba(10, 10, 10, 0.92);">
                    {% if item.image_url %}
                        {% if item.is_video %}
                        <div class="relative overflow-hidden bg-black cursor-pointer" onclick="togglePlay('promo-media-{{ loop.index0 }}', this)">
                            <video id="promo-media-{{ loop.index0 }}" class="w-full h-auto max-h-[75vh] block" preload="metadata" playsinline loop>
                                <source src="{{ url_for('static', filename='images/' + item.image_url) }}" type="video/mp4">
                                Your browser does not support the video tag.
                            </video>
                            <div class="play-overlay absolute inset-0 flex items-center justify-center bg-black/30 transition-opacity duration-300">
                                <div class="w-16 h-16 rounded-full bg-red-600 flex items-center justify-center text-white text-2xl shadow-[0_0_20px_rgba(228,0,43,0.5)]">
                                    <i class="fa-solid fa-play"></i>
                                </div>
                            </div>
                        </div>
                        {% else %}
                        <img src="{{ url_for('static', filename='images/' + item.image_url) }}" alt="{{ item.title }}" class="w-full aspect-video object-cover block">
                        {% endif %}
                    {% endif %}
                    <div class="product-info p-6">
                        <div class="mb-5">
                            <h3 class="text-3xl sm:text-4xl font-black leading-tight" style="color: var(--tfc-gold);">{{ item.title }}</h3>
                        </div>
                        <p class="text-lg leading-relaxed whitespace-pre-wrap mb-6" style="color: var(--text-body);">{{ item.description }}</p>
                        <div class="flex items-center justify-between gap-4">
                            <div class="text-[10px] uppercase tracking-widest opacity-40">{{ item.created }}</div>
                            {% if item.price %}
                            <div class="price-tag text-sm font-semibold text-yellow-300 uppercase tracking-widest bg-white/5 rounded-full px-3 py-1">
                                {{ item.price }} сомони
                            </div>
                            {% endif %}
                        </div>
                    </div>
                    <div class="order-btn"><span>ЗАКАЗАТЬ</span> <i class="fa-solid fa-cart-shopping"></i></div>
                </div>
                {% endfor %}
            </div>
        </div>
    </section>

    <!-- ====================== АДРЕС ====================== -->
    <section id="adres-section" class="content-section flex flex-col items-center justify-center min-h-screen !p-0" style="display: none;">
        <div class="w-full max-w-2xl px-2 py-10">
            <div class="flex justify-center mb-12" style="color: var(--text-body);">
                <button onclick="hideAdres()" class="back-btn group">
                    <i class="fa-solid fa-arrow-left transition-transform group-hover:-translate-x-1"></i> <span>В ГЛАВНОЕ МЕНЮ</span>
                </button>
            </div>
            
            <div class="glass-panel !w-full !max-w-full !opacity-100 !transform-none !p-0 overflow-hidden border-white/10 shadow-[0_30px_100px_rgba(0,0,0,0.6)] flex flex-col items-center">
                <div class="p-8 flex flex-col items-center justify-center text-center w-full" style="background: linear-gradient(to bottom right, rgba(255,255,255,0.03), transparent);">
                    <h2 class="text-2xl sm:text-3xl md:text-4xl font-black mb-1 tracking-tighter" style="color: var(--tfc-gold);">НАШЕ МЕСТОПОЛОЖЕНИЕ</h2> <!-- Use variable for color -->
                    <p class="uppercase tracking-widest text-[9px] mb-8 font-bold opacity-40">Tajik Fried Fish & Chicken</p>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
                        <!-- Филиал 1: Базар Сомони -->
                        <div class="p-5 rounded-3xl bg-white/5 border border-white/10 text-center flex flex-col items-center">
                            <div class="w-12 h-12 rounded-2xl flex items-center justify-center border mb-4" style="background: rgba(255,215,0,0.1); color: var(--tfc-gold); border-color: rgba(255,215,0,0.2);">
                                <i class="fa-solid fa-location-dot text-xl"></i>
                            </div>
                            <h4 class="font-bold text-lg mb-2" style="color: var(--text-body);">Базар Сомони</h4>
                            <p class="text-[11px] opacity-70 mb-3">📍 г. Куляб, базар Сомони</p>
                            <div class="flex flex-col items-center gap-2 mb-4">
                                <div class="flex items-center gap-2 text-sm font-bold text-emerald-500">
                                    <i class="fa-solid fa-phone"></i>
                                    <a href="tel:944975050">944975050</a>
                                </div>
                                <div class="px-3 py-1 rounded-full bg-white/5 border border-white/5 text-[9px] uppercase tracking-widest opacity-50">
                                    <i class="fa-solid fa-clock mr-1"></i> Работаем: 8:00 — 01:00
                                </div>
                            </div>
                        </div>

                        <!-- Филиал 2: Дом Адолат -->
                        <div class="p-5 rounded-3xl bg-white/5 border border-white/10 text-center flex flex-col items-center">
                            <div class="w-12 h-12 rounded-2xl flex items-center justify-center border mb-4" style="background: rgba(255,215,0,0.1); color: var(--tfc-gold); border-color: rgba(255,215,0,0.2);">
                                <i class="fa-solid fa-location-dot text-xl"></i>
                            </div>
                            <h4 class="font-bold text-lg mb-2" style="color: var(--text-body);">Дом АДОЛАТ «TFC»</h4>
                            <p class="text-[11px] opacity-70 mb-3">📍 г. Куляб, дом АДОЛАТ «TFC»</p>
                            <div class="flex flex-col items-center gap-2 mb-4">
                                <div class="flex items-center gap-2 text-sm font-bold text-emerald-500">
                                    <i class="fa-solid fa-phone"></i>
                                    <a href="tel:754169090">754169090</a>
                                </div>
                                <div class="px-3 py-1 rounded-full bg-white/5 border border-white/5 text-[9px] uppercase tracking-widest opacity-50">
                                    <i class="fa-solid fa-clock mr-1"></i> Работаем: 10:00 — 23:00
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="h-[250px] w-full relative border-t border-white/5">
                    <iframe src="https://www.google.com/maps?q=37.91936836538492,69.78745179867099&hl=ru&z=16&output=embed" width="100%" height="100%" style="border:0;" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
                    <div class="absolute inset-0 pointer-events-none shadow-[inset_0_0_60px_rgba(0,0,0,0.4)]"></div>
                    <a href="https://www.google.com/maps/dir/?api=1&destination=37.91936836538492,69.78745179867099" target="_blank" class="absolute bottom-4 right-4 backdrop-blur-md px-4 py-2 rounded-xl text-[9px] font-black border transition-all flex items-center gap-2 pointer-events-auto uppercase tracking-widest" style="background: rgba(0,0,0,0.8); color: var(--text-body); border-color: rgba(255,255,255,0.2); hover:background: rgba(255,215,0,0.1); hover:color: var(--tfc-gold); hover:border-color: var(--tfc-gold);">
                            <i class="fa-solid fa-diamond-turn-right text-base"></i> <span>ОТКРЫТЬ В GPS</span>
                         </a>
                </div>
            </div>
        </div>
    </section>

    <!-- ====================== ВАКАНСИИ ====================== -->
    <section id="vakansii-section" class="content-section" style="display: none;">
        <div class="max-w-6xl mx-auto">
            <div class="flex justify-center mb-8" style="color: var(--text-body);">
                <button onclick="hideVakansii()" class="back-btn">
                    <i class="fa-solid fa-arrow-left"></i> <span>В ГЛАВНОЕ МЕНЮ</span>
                </button>
            </div>
            <h2 class="text-4xl md:text-5xl font-black text-center mb-2 tracking-tight" style="color: var(--tfc-gold);">Вакансии</h2>
            <p class="text-center text-base md:text-lg opacity-70 mb-10">Тихий и стильный раздел поиска работы в TFC.</p>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                {% for food in categories.get('Вакансии', []) %}
                <div class="product-card !h-auto text-left transition-all hover:-translate-y-0.5" style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); box-shadow: 0 10px 24px rgba(0,0,0,0.14);">
                    {% if food.image_url %}
                        {% if food.is_video %}
                        <div class="relative overflow-hidden bg-black cursor-pointer" onclick="togglePlay('v-media-{{ loop.index0 }}', this)">
                            <video id="v-media-{{ loop.index0 }}" class="w-full h-auto max-h-[60vh] block" preload="metadata" playsinline loop>
                                <source src="{{ url_for('static', filename='images/' + food.image_url) }}">
                            </video>
                            <div class="play-overlay absolute inset-0 flex items-center justify-center bg-black/30 transition-opacity duration-300">
                                <div class="w-12 h-12 rounded-full bg-red-600 flex items-center justify-center text-white text-xl shadow-[0_0_15px_rgba(228,0,43,0.5)]"><i class="fa-solid fa-play"></i></div>
                            </div>
                        </div>
                        {% else %}
                        <img src="{{ url_for('static', filename='images/' + food.image_url) }}" alt="{{ food.name }}" class="h-44 w-full object-cover">
                        {% endif %}
                    {% endif %}
                    <div class="product-info !pb-6 px-5 !text-left">
                        <h3 class="text-2xl font-bold mb-2" style="color: var(--tfc-gold);">{{ food.name }}</h3>
                        <div class="text-sm whitespace-pre-wrap mb-4 leading-relaxed" style="color: var(--text-muted);">{{ food.description }}</div>
                        <div class="flex items-center justify-between gap-3 pt-3 border-t" style="border-color: rgba(255,255,255,0.08);">
                            <div class="text-[10px] uppercase tracking-widest opacity-50">Вакансия</div>
                            <div class="text-sm font-semibold text-yellow-300 uppercase tracking-widest bg-white/5 rounded-full px-3 py-1">{{ food.price }} сом</div>
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
            
            <!-- Сообщение для связи через WhatsApp -->
            <div class="mt-16 p-8 rounded-[32px] text-center border border-dashed border-white/20 bg-white/5">
                <p class="text-lg md:text-xl font-bold mb-4" style="color: var(--tfc-gold);">Хотите работать у нас?</p>
                <a href="https://wa.me/992754169090" target="_blank" class="inline-flex items-center gap-3 px-8 py-4 bg-[#25D366] text-white rounded-2xl font-black transition-transform hover:scale-105 active:scale-95 shadow-xl shadow-green-500/20">
                    <i class="fa-brands fa-whatsapp text-2xl"></i>
                    <span>Напишите нам в WhatsApp: +992 754 16 9090</span>
                </a>
                <p class="mt-4 text-xs opacity-40 uppercase tracking-widest">Мы ждем ваше сообщение!</p>
            </div>
        </div>
    </section>
    <!-- ====================== БАХШИ ХАБАРҲО ====================== -->
    <section id="notifications-section" class="content-section" style="display: none;">
        <div class="max-w-3xl mx-auto">
            <div class="flex flex-col sm:flex-row justify-center items-center gap-4 mb-10" style="color: var(--text-body);">
                <button onclick="hideNotifications()" class="back-btn">
                    <i class="fa-solid fa-arrow-left"></i> <span>В ГЛАВНОЕ МЕНЮ</span>
                </button>
                <button onclick="clearNotifications()" class="back-btn !bg-zinc-800 hover:!bg-red-600 transition-colors">
                    <i class="fa-solid fa-trash-can"></i> <span>ОЧИСТИТЬ ВСЁ</span>
                </button>
            </div>
            <h2 class="text-4xl font-black text-center mb-8 tracking-widest" style="color: var(--tfc-gold);">ИСТОРИЯ УВЕДОМЛЕНИЙ</h2> <!-- Use variable for color -->
            <div id="notifications-history-list" class="space-y-4">
                <p class="text-center opacity-50">Уведомлений пока нет.</p>
            </div>
        </div>
    </section>
    </main>
    <script>
        document.addEventListener("DOMContentLoaded", () => {
            if (localStorage.getItem("tfc_session")) showApp();
            else {
                const auth = document.getElementById('auth-section');
                if (auth) auth.classList.remove('hidden');
            }
        });

        // Пайваст кардани Fullscreen ба тамоми экран ва экрани боркунӣ
        async function triggerFullScreen() {
            // Агар аллакай дар режими пурра бошад, ягон кор намекунем
            if (document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement || document.msFullscreenElement) {
                cleanFullScreenEvents();
                return;
            }

            const docEl = document.documentElement;
            const requestFs = docEl.requestFullscreen || docEl.mozRequestFullScreen || docEl.webkitRequestFullscreen || docEl.msRequestFullscreen;

            if (requestFs) {
                try {
                    await requestFs.call(docEl);
                    cleanFullScreenEvents();
                } catch (err) {
                    // Игнори хатогӣ, агар браузер иҷозат надиҳад
                }
            }
        }

        function cleanFullScreenEvents() {
            document.removeEventListener('click', triggerFullScreen);
            document.removeEventListener('touchstart', triggerFullScreen);
            const mainContent = document.getElementById('main-content');
            if (mainContent) {
                mainContent.removeEventListener('click', triggerFullScreen);
                mainContent.removeEventListener('touchstart', triggerFullScreen);
            }
            const authSection = document.getElementById('auth-section');
            if (authSection) {
                authSection.removeEventListener('click', triggerFullScreen);
                authSection.removeEventListener('touchstart', triggerFullScreen);
            }
        }

        function handleSimpleLogin() {
            const nameInput = document.getElementById('auth-name-input');
            const fullName = nameInput.value.trim();
            const words = fullName.split(/\s+/).filter(w => w.length > 0);

            // 1. Тафтиши мавҷудияти Ном ва Насаб (на кам аз 2 калима)
            if (words.length < 2) { // Changed from fullName.length < 3 to words.length < 2
                alert("Лутфан ҳам Ном ва ҳам Насабро ворид кунед.");
                return;
            }

            // 2. Тафтиши ҳарфҳои англисӣ (танҳо кириллица иҷозат аст)
            if (/[a-zA-Z]/.test(fullName)) {
                alert("Лутфан танҳо бо ҳарфҳои кириллӣ (русӣ/тоҷикӣ) нависед. Ҳарфҳои англисӣ манъ аст."); // Changed error message
                return;
            }

            // 3. Тафтиши ҳарфи аввали калон ва Caps Lock барои ҳар як калима
            for (const word of words) {
                if (word.length === 0) continue; // Skip empty strings from split

                if (word[0] !== word[0].toUpperCase()) {
                    alert(`Калимаи "${word}" бояд бо ҳарфи калон сар шавад.`);
                    return;
                }
                // Тафтиш мекунем, ки оё баъд аз ҳарфи аввал ягон ҳарфи калон ҳаст
                if (word.length > 1 && word.substring(1) !== word.substring(1).toLowerCase()) {
                    alert(`Лутфан танҳо ҳарфи аввали калимаро калон нависед: "${word}". Мисол: Баротов`);
                    return;
                }
            }

            // МАҲЗ ДАР ҲАМИН ҶО: вақте корбар тугмаро зер мекунад, 
            // мо Fullscreen-ро фаъол мекунем, то интерфейси браузер гум шавад.
            triggerFullScreen();

            // Эҷоди профили корбар ва захира дар localStorage
            const generatedId = "TFC-" + Math.floor(100000 + Math.random() * 900000);
            const profile = { fullName: fullName, id: generatedId };
            
            localStorage.setItem("tfc_customer_profile", JSON.stringify(profile));
            localStorage.setItem("tfc_session", fullName);

            // Регистрация пользователя на сервере
            fetch(adminApiBase() + '/api/customers/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ full_name: fullName, customer_id: generatedId })
            }).catch(e => console.error("Reg error:", e));

            showApp();
        }

        function handleGoogleLogin(response) {
            try {
                const base64Url = response.credential.split('.')[1];
                const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
                const jsonPayload = decodeURIComponent(window.atob(base64).split('').map(function(c) {
                    return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
                }).join(''));
                const user = JSON.parse(jsonPayload);
                
                // Агар аз Google гузашт, профилро автоматӣ месозем, то prompt() набарояд
                if (!localStorage.getItem("tfc_customer_profile")) {
                    const generatedId = "TFC-" + Math.floor(100000 + Math.random() * 900000);
                    const profile = { fullName: user.name || "Пользователь Google", id: generatedId };
                    localStorage.setItem("tfc_customer_profile", JSON.stringify(profile));
                }

                localStorage.setItem("tfc_session", user.name || user.email);
                showApp();
            } catch (e) {
                console.error("JWT Decode Error:", e);
                handlePhoneSignIn(); // Fallback if Google fails
            }
        }

        function handlePhoneSignIn() {
            const phoneOverlay = document.createElement('div');
            phoneOverlay.id = "phone-auth-overlay";
            phoneOverlay.className = "fixed inset-0 z-[10001] bg-black/80 backdrop-blur-md flex items-center justify-center p-6";
            phoneOverlay.innerHTML = `
                <div class="glass-panel text-center !opacity-100 !transform-none">
                    <h2 class="text-xl font-black text-white mb-2">Вход по номеру</h2>
                    <p class="text-white/60 text-xs mb-4">Введите ваш номер телефона</p>
                    <input id="auth-phone-input" type="tel" placeholder="+992 _________" 
                           class="w-full px-4 py-4 rounded-2xl border border-white/10 bg-white/5 text-white focus:ring-2 focus:ring-yellow-400 outline-none text-center text-lg font-bold"
                           maxlength="9">
                    <span id="auth-phone-error" class="text-red-500 text-xs mt-1 hidden">Пожалуйста, введите 9 цифр.</span>
                    <button id="send-sms-btn" class="phone-signin-btn !mt-4 !max-w-full">Получить код</button>
                    <button onclick="document.getElementById('phone-auth-overlay').remove()" class="text-white/30 text-[10px] mt-4 uppercase tracking-widest">Отмена</button>
                </div>
            `;
            document.body.appendChild(phoneOverlay);

            document.getElementById('send-sms-btn').onclick = async () => {
                const phone = document.getElementById('auth-phone-input').value.trim();
                if (!/^\d{9}$/.test(phone)) { // New validation for exactly 9 digits
                    const phoneError = document.getElementById("auth-phone-error");
                    phoneError.textContent = "Пожалуйста, введите 9 цифр.";
                    phoneError.classList.remove("hidden");
                    document.getElementById('auth-phone-input').focus();
                    return;
                }
                document.getElementById("auth-phone-error").classList.add("hidden");
                const btn = document.getElementById('send-sms-btn');
                btn.disabled = true;
                btn.textContent = "Отправка...";

                try {
                    const res = await fetch(adminApiBase() + '/api/auth/send-code', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ phone })
                    });
                    const data = await res.json();
                    if (data.ok) {
                        showCodeInputUI(phone);
                    } else {
                        alert("Ошибка отправки корт!");
                        btn.disabled = false;
                        btn.textContent = "Получить код";
                    }
                } catch (e) { alert("Ошибка!"); btn.disabled = false; btn.textContent = "Получить код"; }
            };
        }

        function showCodeInputUI(phone) {
            const overlay = document.getElementById('phone-auth-overlay');
            overlay.innerHTML = `
                <div class="glass-panel text-center !opacity-100 !transform-none">
                    <h2 class="text-xl font-black text-white mb-2">Код подтверждения</h2>
                    <p class="text-white/60 text-xs mb-6">Код отправлен на ${phone}</p>
                    <input id="auth-code-input" type="number" placeholder="____" 
                           class="w-full px-4 py-4 rounded-2xl border border-white/10 bg-white/5 text-white mb-4 focus:ring-2 focus:ring-yellow-400 outline-none text-center text-2xl font-black tracking-[10px]">
                    <button id="verify-sms-btn" class="phone-signin-btn !mt-0 !max-w-full">Войти</button>
                    <p class="text-white/20 text-[10px] mt-4">Код придет в консоль сервера (Python)</p>
                </div>
            `;

            document.getElementById('verify-sms-btn').onclick = async () => {
                const code = document.getElementById('auth-code-input').value.trim();
                if (code.length !== 4) return alert("Введите 4 цифры!");

                try {
                    const res = await fetch(adminApiBase() + '/api/auth/verify-code', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ phone, code })
                    });
                    const data = await res.json();
                    if (data.ok) {
                        overlay.remove();
                        // Эҷоди профил барои воридшавӣ бо телефон, агар он мавҷуд набошад
                        if (!localStorage.getItem("tfc_customer_profile")) {
                            const generatedId = "TFC-" + Math.floor(100000 + Math.random() * 900000);
                            const profile = { fullName: "Клиент " + phone, id: generatedId };
                            localStorage.setItem("tfc_customer_profile", JSON.stringify(profile));
                        }
                        localStorage.setItem("tfc_session", phone);
                        showApp();
                    } else {
                        alert("Неверный код!");
                    }
                } catch (e) { alert("Ошибка!"); }
            };
        }

        function getOrCreateCustomerProfile() {
            const existingProfile = localStorage.getItem("tfc_customer_profile");
            if (existingProfile) {
                return JSON.parse(existingProfile);
            }
            return null;
        }

        function toggleTheme(event) {
            const toggle = () => {
                document.body.classList.toggle('light-active');
                const isLight = document.body.classList.contains('light-active');
                const themeIcon = document.getElementById('theme-icon');
                if (themeIcon) themeIcon.className = isLight ? 'fas fa-sun' : 'fas fa-moon';
                localStorage.setItem('tfc_theme', isLight ? 'light' : 'dark');
            };

            if (!document.startViewTransition) {
                toggle();
                return;
            }

            const x = event ? event.clientX : window.innerWidth / 2;
            const y = event ? event.clientY : window.innerHeight / 2;
            const endRadius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));

            const transition = document.startViewTransition(toggle);

            transition.ready.then(() => {
                const clipPath = [
                    `circle(0px at ${x}px ${y}px)`,
                    `circle(${endRadius}px at ${x}px ${y}px)`,
                ];
                document.documentElement.animate(
                    {
                        clipPath: document.body.classList.contains('light-active') ? clipPath : [...clipPath].reverse(),
                    },
                    {
                        duration: 650,
                        easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
                        pseudoElement: document.body.classList.contains('light-active') ? '::view-transition-new(root)' : '::view-transition-old(root)',
                    }
                );
            });
        }

        function showCustomerIdBadge(profile) {
            const badge = document.getElementById("customer-id-badge");
            if (badge) {
                badge.textContent = "ID: " + profile.id;
                badge.classList.remove("hidden");
            }
        }

        function setTopControlsVisible(isVisible) {
            const signOutBtn = document.getElementById("sign-out-btn");
            const idBadge = document.getElementById("customer-id-badge");
            const notifBtn = document.getElementById("notif-bell-btn");
            const themeToggleBtn = document.getElementById("theme-toggle-btn");
            const phoneOrderBtn = document.getElementById("phone-order-btn");
            
            if (signOutBtn) signOutBtn.style.display = isVisible ? "flex" : "none";
            if (notifBtn) notifBtn.style.display = isVisible ? "flex" : "none";
            if (themeToggleBtn) themeToggleBtn.style.display = isVisible ? "flex" : "none";
            if (phoneOrderBtn) phoneOrderBtn.style.display = isVisible ? "flex" : "none";
            
            if (isVisible) {
                if (idBadge) idBadge.classList.remove("hidden");
            } else {
                if (idBadge) idBadge.classList.add("hidden");
            }
        }

        function isOnFirstPageTop() {
            const introSection = document.getElementById("intro-section");
            const menuSection = document.getElementById("menu");
            if (!introSection || !menuSection) return false;
            const introVisible = introSection.style.display !== "none";
            const menuVisible = menuSection.style.display !== "none";
            return introVisible && menuVisible && window.scrollY <= 40;
        }

        function updateTopControlsByScroll() {
            setTopControlsVisible(isOnFirstPageTop());
        }

        function showApp() {
            const profile = getOrCreateCustomerProfile();
            if (!profile) {
                localStorage.removeItem("tfc_session");
                return; // Don't proceed if no profile
            }

            // Apply saved theme on app load
            if (localStorage.getItem('tfc_theme') === 'light') {
                document.body.classList.add('light-active');
                const icon = document.getElementById('theme-icon');
                if (icon) icon.className = 'fas fa-sun';
            }
            
            const auth = document.getElementById('auth-section');
            auth.style.transition = "0s";
            auth.style.opacity = "0";
            auth.style.transform = "scale(1.1)";
            
            setTimeout(() => {
                auth.classList.add('hidden');
                document.getElementById('main-content').classList.remove('hidden');
                showCustomerIdBadge(profile);
                updateTopControlsByScroll();
                startCustomerStatusPolling();
                updateNotifBadge(); // Навсозии баҷ ҳангоми ворид шудан
                
                // Setup Push Notifications
                setupPushNotifications(profile.id);
            }, 0);
        }

        async function setupPushNotifications(customerId) {
            if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
            
            try {
                const registration = await navigator.serviceWorker.register('/sw.js');
                const permission = await Notification.requestPermission();
                if (permission !== 'granted') return;

                let subscription = await registration.pushManager.getSubscription();
                if (!subscription) {
                    subscription = await registration.pushManager.subscribe({
                        userVisibleOnly: true,
                        applicationServerKey: urlBase64ToUint8Array("{{ vapid_public_key }}")
                    });
                }

                await fetch(adminApiBase() + '/api/push/subscribe', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ customer_id: customerId, subscription: subscription })
                });
            } catch (e) { console.error("Push Error:", e); }
        }

        function urlBase64ToUint8Array(base64String) {
            const padding = '='.repeat((4 - base64String.length % 4) % 4);
            const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
            const rawData = window.atob(base64);
            const outputArray = new Uint8Array(rawData.length);
            for (let i = 0; i < rawData.length; ++i) {
                outputArray[i] = rawData.charCodeAt(i);
            }
            return outputArray;
        }
    </script>
    <script>
        function animateSection(id) {
            // Ensure the element exists before trying to animate
            const el = document.getElementById(id);
            if (!el) {
                console.warn(`Element with ID '${id}' not found for animation.`);
                return;
            }

            el.classList.remove('page-transition');
            void el.offsetWidth; // Trigger reflow
            el.classList.add('page-transition');
        }

        function showMenu() {
            setTimeout(() => {
                document.getElementById('intro-section').style.display = 'none';
                document.getElementById('menu').style.display = 'none';
                const menuSection = document.getElementById('menu-section');
                const subCategories = document.getElementById('menu-subcategories');
                const productGrid = document.getElementById('filtered-product-grid');

                menuSection.style.display = 'block';
                subCategories.style.display = 'grid';
                document.getElementById('category-back-btn').style.display = 'none'; // Hide sub-back
                document.getElementById('main-back-btn').style.display = 'inline-flex'; // Show main-back
                
                menuSection.querySelector('h2').innerHTML = 'МЕНЮ';
                // Пинҳон кардани хӯрокҳо то он даме, ки зергурӯҳ интихоб шавад
                productGrid.querySelectorAll('.product-card').forEach(c => c.style.display = 'none');

                if(typeof animateSection === 'function') animateSection('menu-section');
                setTopControlsVisible(false);
                // Танҳо пас аз иваз шудани контент ба боло меравем
                window.scrollTo(0, 0);
                document.documentElement.scrollTop = 0;
                document.body.scrollTop = 0;
            }, 150);
        }

        function filterMenu(subCategory) {
            const menuSection = document.getElementById('menu-section');
            const grid = document.getElementById('filtered-product-grid');
            const title = menuSection.querySelector('h2');

            // Таъхири кӯтоҳ барои эффекти синамоӣ
            setTimeout(() => {
                // Пинҳон кардани тугмаҳои зеркатегорияҳо барои намуди "саҳифаи нав"
                document.getElementById('menu-subcategories').style.display = 'none';
                document.getElementById('main-back-btn').style.display = 'none';
                document.getElementById('category-back-btn').style.display = 'inline-flex';
                
                title.innerHTML = subCategory.toUpperCase();

                const cards = grid.querySelectorAll('.product-card');
                cards.forEach(card => {
                    const cardSub = card.getAttribute('data-subcategory') || '';
                    const name = card.getAttribute('data-name').toUpperCase();
                    let show = false;
                    
                    if (cardSub === subCategory) {
                        show = true;
                    } else if (!cardSub) {
                        if (subCategory === 'Паста') show = name.includes('ПАСТА') || name.includes('ГНЁЗДА');
                        if (subCategory === 'Салаты') show = name.includes('САЛАТ') || name.includes('БАКЛАЖАН') || name.includes('ГРЕЧЕСКИЙ');
                        if (subCategory === 'Супы') show = name.includes('СУП') || name.includes('БОРЩ') || name.includes('ЛАГМАН') || name.includes('ЧАХОВ') || name.includes('МЕРДЖИМЕК');
                        if (subCategory === 'Горячие блюда') show = name.includes('СТЕКС') || name.includes('КОТЛЕТ') || name.includes('БАРАНИНА') || name.includes('КАБОБ') || name.includes('ЖАРОВНЯ') || name.includes('ТАБАКА') || name.includes('СТЕЙК') || name.includes('КОРЕЙКА');
                        if (subCategory === 'Десерты') show = name.includes('ЧИЗКЕЙК') || name.includes('РАФАЭЛЛО') || name.includes('НАПОЛЕОН') || name.includes('ТИРАМИСУ') || name.includes('ФРУКТОВАЯ') || name.includes('КЕШЬЮ');
                        if (subCategory === 'Напитки') show = name.includes('АМЕРИКАНО') || name.includes('КАПУЧИНO') || name.includes('ЛАТТЕ') || name.includes('ЭСПРЕССО') || name.includes('ЧАЙ') || name.includes('КОФЕ') || name.includes('АЙРАН') || name.includes('МОХИТО');
                    }
                    card.style.display = show ? 'block' : 'none';
                });

                // Scroll to top танҳо вақте ки хӯрокҳо иваз шуданд
                window.scrollTo(0, 0);
                document.documentElement.scrollTop = 0;
                document.body.scrollTop = 0;

                // Фаъол кардани аниматсияи Cinematic
                [title, grid].forEach(el => {
                    el.classList.remove('page-transition');
                    void el.offsetWidth; 
                    el.classList.add('page-transition');
                });
            }, 250);
        }

        function hideMenu() {
            setTimeout(() => {
            stopAllVideos();
            document.getElementById('menu-section').style.display = 'none';
            document.getElementById('menu').style.display = 'block';
            document.getElementById('menu-subcategories').style.display = 'none';
            document.getElementById('intro-section').style.display = 'flex';
            if(typeof animateSection === 'function') animateSection('menu');
            if(typeof animateSection === 'function') animateSection('intro-section');
            updateTopControlsByScroll();
            window.scrollTo(0, 0);
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
            }, 350);
        }
        function showPizza() {
            setTimeout(() => {
            document.getElementById('intro-section').style.display = 'none';
            document.getElementById('menu').style.display = 'none';
            document.getElementById('pizza-section').style.display = 'block';
            const pizzaSection = document.getElementById('pizza-section');
            const subCategories = document.getElementById('pizza-subcategories');
            const productGrid = document.getElementById('pizza-filtered-product-grid');

            pizzaSection.style.display = 'block';
            subCategories.style.display = 'grid';
            document.getElementById('pizza-category-back-btn').style.display = 'none';
            document.getElementById('pizza-main-back-btn').style.display = 'inline-flex';

            pizzaSection.querySelector('h2').innerHTML = 'ПИЦЦА';
            productGrid.querySelectorAll('.product-card').forEach(c => c.style.display = 'none');

            if(typeof animateSection === 'function') animateSection('pizza-section');
            setTopControlsVisible(false);
            window.scrollTo(0, 0);
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
            }, 350);
        }

        function filterPizza(subCategory) {
            const pizzaSection = document.getElementById('pizza-section');
            const grid = document.getElementById('pizza-filtered-product-grid');
            const title = pizzaSection.querySelector('h2');

            setTimeout(() => {
                document.getElementById('pizza-subcategories').style.display = 'none';
                document.getElementById('pizza-main-back-btn').style.display = 'none';
                document.getElementById('pizza-category-back-btn').style.display = 'inline-flex';
                
                title.innerHTML = subCategory.toUpperCase();

                const cards = grid.querySelectorAll('.product-card');
                cards.forEach(card => {
                    const cardSub = card.getAttribute('data-subcategory') || '';
                    card.style.display = (cardSub === subCategory) ? 'block' : 'none';
                });

                window.scrollTo(0, 0);
                [title, grid].forEach(el => {
                    el.classList.remove('page-transition');
                    void el.offsetWidth; 
                    el.classList.add('page-transition');
                });
            }, 250);
        }
        function hidePizza() {
            setTimeout(() => {
            stopAllVideos();
            document.getElementById('pizza-section').style.display = 'none';
            document.getElementById('menu').style.display = 'block';
            document.getElementById('pizza-subcategories').style.display = 'none';
            document.getElementById('intro-section').style.display = 'flex';
            animateSection('menu');
            animateSection('intro-section');
            updateTopControlsByScroll();
            window.scrollTo(0, 0);
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
            }, 350);
        }
        function showFastFood() {
            setTimeout(() => {
            document.getElementById('intro-section').style.display = 'none';
            document.getElementById('menu').style.display = 'none';
            document.getElementById('fastfood-section').style.display = 'block';
            const fastfoodSection = document.getElementById('fastfood-section');
            const subCategories = document.getElementById('fastfood-subcategories');
            const productGrid = document.getElementById('fastfood-filtered-product-grid');

            fastfoodSection.style.display = 'block';
            subCategories.style.display = 'grid'; 
            document.getElementById('fastfood-category-back-btn').style.display = 'none';
            document.getElementById('fastfood-main-back-btn').style.display = 'inline-flex';

            fastfoodSection.querySelector('h2').innerHTML = 'ФАСТФУД';
            // Пинҳон кардани хӯрокҳо то он даме, ки зергурӯҳ интихоб шавад
            productGrid.querySelectorAll('.product-card').forEach(c => c.style.display = 'none');

            if(typeof animateSection === 'function') animateSection('fastfood-section');
            setTopControlsVisible(false);
            window.scrollTo(0, 0);
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
            }, 350);
        }

        function filterFastFood(subCategory) {
            const fastfoodSection = document.getElementById('fastfood-section');
            const grid = document.getElementById('fastfood-filtered-product-grid');
            const title = fastfoodSection.querySelector('h2');

            setTimeout(() => {
                // Пинҳон кардани тугмаҳои зеркатегорияҳо
                document.getElementById('fastfood-subcategories').style.display = 'none';
                document.getElementById('fastfood-main-back-btn').style.display = 'none';
                document.getElementById('fastfood-category-back-btn').style.display = 'inline-flex';
                
                title.innerHTML = subCategory.toUpperCase();

                const cards = grid.querySelectorAll('.product-card');
                cards.forEach(card => {
                    const cardSub = card.getAttribute('data-subcategory') || '';
                    const name = card.getAttribute('data-name').toUpperCase();
                    let show = false;
                    
                    if (cardSub === subCategory) {
                        show = true;
                    } else if (!cardSub) {
                        if (subCategory === 'Хот-доги') show = name.includes('ДОГ') || name.includes('БУЛОЧКА');
                        if (subCategory === 'Бургеры') show = name.includes('БУРГЕР');
                        if (subCategory === 'Сэндвичи') show = name.includes('СЭНДВИЧ') || name.includes('ПАНИНИ');
                        if (subCategory === 'Тортильи') show = name.includes('ТОРТИЛЬЯ');
                        if (subCategory === 'Гарниры') show = name.includes('КАРТО') || name.includes('НАГГЕТС') || name.includes('КРЫЛЫШКИ') || name.includes('НОЖКИ') || name.includes('ПАЛОЧКИ') || name.includes('БАСКЕТ');
                    }
                    card.style.display = show ? 'block' : 'none';
                });

                window.scrollTo(0, 0);

                [title, grid].forEach(el => {
                    el.classList.remove('page-transition');
                    void el.offsetWidth; 
                    el.classList.add('page-transition');
                });
            }, 250);
        }

        function hideFastFood() {
            setTimeout(() => {
            stopAllVideos();
            document.getElementById('fastfood-section').style.display = 'none';
            document.getElementById('menu').style.display = 'block';
            document.getElementById('intro-section').style.display = 'flex';
            document.getElementById('fastfood-subcategories').style.display = 'none';
            animateSection('menu');
            animateSection('intro-section');
            updateTopControlsByScroll();
            window.scrollTo(0, 0);
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
            }, 350);
        }
        function showSummerMenu() {
            setTimeout(() => {
            document.getElementById('intro-section').style.display = 'none';
            document.getElementById('menu').style.display = 'none';
            document.getElementById('summer-menu-section').style.display = 'block';
            if(typeof animateSection === 'function') animateSection('summer-menu-section');
            setTopControlsVisible(false);
            window.scrollTo(0, 0);
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
                document.getElementById('intro-section').style.display = 'none';
                document.getElementById('menu').style.display = 'none';
                const summerSection = document.getElementById('summer-menu-section');
                const subCategories = document.getElementById('summer-menu-subcategories');
                const productGrid = document.getElementById('summer-menu-filtered-product-grid');

                summerSection.style.display = 'block';
                subCategories.style.display = 'grid'; 
                subCategories.style.display = 'flex'; 
                subCategories.style.display = 'grid';
                document.getElementById('summer-category-back-btn').style.display = 'none';
                document.getElementById('summer-main-back-btn').style.display = 'inline-flex';

                summerSection.querySelector('h2').innerHTML = 'ЛЕТНЕЕ МЕНЮ';
                productGrid.querySelectorAll('.product-card').forEach(c => c.style.display = 'none');

                if(typeof animateSection === 'function') animateSection('summer-menu-section');
                setTopControlsVisible(false);
                window.scrollTo(0, 0);
                document.documentElement.scrollTop = 0;
                document.body.scrollTop = 0;
            }, 350);
        }

        function filterSummerMenu(subCategory) {
            const summerSection = document.getElementById('summer-menu-section');
            const grid = document.getElementById('summer-menu-filtered-product-grid');
            const title = summerSection.querySelector('h2');

            setTimeout(() => {
                document.getElementById('summer-menu-subcategories').style.display = 'none';
                document.getElementById('summer-main-back-btn').style.display = 'none';
                document.getElementById('summer-category-back-btn').style.display = 'inline-flex';
                
                title.innerHTML = subCategory.toUpperCase();

                const cards = grid.querySelectorAll('.product-card');
                cards.forEach(card => {
                    const cardSub = card.getAttribute('data-subcategory') || '';
                    const name = card.getAttribute('data-name').toUpperCase();
                    let show = false;
                    
                    if (cardSub === subCategory) {
                        show = true;
                    } else if (!cardSub) {
                        if (subCategory === 'Смузи') show = name.includes('СМУЗИ');
                        if (subCategory === 'Мохито') show = name.includes('МОХИТО');
                        if (subCategory === 'Холодок') show = name.includes('АЙРАН') || name.includes('ОКРОШКА');
                    }
                    card.style.display = show ? 'block' : 'none';
                });

                window.scrollTo(0, 0);
                [title, grid].forEach(el => {
                    el.classList.remove('page-transition');
                    void el.offsetWidth; 
                    el.classList.add('page-transition');
                });
            }, 250);
        }

        function hideSummerMenu() {
            setTimeout(() => {
            stopAllVideos();
            document.getElementById('summer-menu-section').style.display = 'none';
            document.getElementById('menu').style.display = 'block';
            document.getElementById('intro-section').style.display = 'flex';
            animateSection('menu');
            animateSection('intro-section');
            updateTopControlsByScroll();
            window.scrollTo(0, 0);
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
                document.getElementById('summer-menu-section').style.display = 'none';
                document.getElementById('menu').style.display = 'block';
                document.getElementById('intro-section').style.display = 'flex';
                document.getElementById('summer-menu-subcategories').style.display = 'none';
                animateSection('menu');
                animateSection('intro-section');
                updateTopControlsByScroll();
                window.scrollTo(0, 0);
                document.documentElement.scrollTop = 0;
                document.body.scrollTop = 0;
            }, 350);
        }
        function showCombo() {
            setTimeout(() => {
            document.getElementById('intro-section').style.display = 'none';
            document.getElementById('menu').style.display = 'none';
            document.getElementById('combo-section').style.display = 'block';
            if(typeof animateSection === 'function') animateSection('combo-section');
            setTopControlsVisible(false);
            window.scrollTo(0, 0);
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
            }, 350);
        }
        function hideCombo() {
            setTimeout(() => {
            stopAllVideos();
            document.getElementById('combo-section').style.display = 'none';
            document.getElementById('menu').style.display = 'block';
            document.getElementById('intro-section').style.display = 'flex';
            animateSection('menu');
            animateSection('intro-section');
            updateTopControlsByScroll();
            window.scrollTo(0, 0);
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
            }, 350);
        }
        function showOtziv() {
            setTimeout(() => {
            document.getElementById('intro-section').style.display = 'none';
            document.getElementById('menu').style.display = 'none';
            document.getElementById('otziv-section').style.display = 'block';
            if(typeof animateSection === 'function') animateSection('otziv-section');
            setTopControlsVisible(false);
            window.scrollTo(0, 0);
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
            }, 200);
        }
        function showAktsii() {
            setTimeout(() => {
            document.getElementById('intro-section').style.display = 'none';
            document.getElementById('menu').style.display = 'none';
            document.getElementById('aktsii-section').style.display = 'block';
            if(typeof animateSection === 'function') animateSection('aktsii-section');
            setTopControlsVisible(false);
            window.scrollTo(0, 0);
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
            }, 350);
        }
        function hideAktsii() {
            setTimeout(() => {
            stopAllVideos();
            document.getElementById('aktsii-section').style.display = 'none';
            document.getElementById('menu').style.display = 'block';
            document.getElementById('intro-section').style.display = 'flex';
            animateSection('menu');
            animateSection('intro-section');
            updateTopControlsByScroll();
            window.scrollTo(0, 0);
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
            }, 350);
        }
        function showAdres() {
            setTimeout(() => {
            document.getElementById('intro-section').style.display = 'none';
            document.getElementById('menu').style.display = 'none';
            document.getElementById('adres-section').style.display = 'flex';
            if(typeof animateSection === 'function') animateSection('adres-section');
            setTopControlsVisible(false);
            window.scrollTo(0, 0);
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
            }, 250);
        }
        function hideAdres() {
            setTimeout(() => {
            document.getElementById('adres-section').style.display = 'none';
            document.getElementById('menu').style.display = 'block';
            document.getElementById('intro-section').style.display = 'flex';
            animateSection('menu');
            animateSection('intro-section');
            updateTopControlsByScroll();
            window.scrollTo(0, 0);
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
            }, 350);
        }
        // New functions for Vakansii
        function showVakansii() {
            setTimeout(() => {
            stopAllVideos();
            document.getElementById('intro-section').style.display = 'none';
            document.getElementById('menu').style.display = 'none';
            document.getElementById('vakansii-section').style.display = 'block';
            if(typeof animateSection === 'function') animateSection('vakansii-section');
            setTopControlsVisible(false);
            window.scrollTo(0, 0);
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
            }, 350);
        }
        function hideVakansii() {
            setTimeout(() => {
            stopAllVideos();
            document.getElementById('vakansii-section').style.display = 'none';
            document.getElementById('menu').style.display = 'block';
            document.getElementById('intro-section').style.display = 'flex';
            animateSection('menu');
            animateSection('intro-section');
            updateTopControlsByScroll();
            window.scrollTo(0, 0);
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
            }, 350);
        }
        function hideOtziv() {
            setTimeout(() => {
            document.getElementById('otziv-section').style.display = 'none';
            document.getElementById('menu').style.display = 'block';
            document.getElementById('intro-section').style.display = 'flex';
            animateSection('menu');
            animateSection('intro-section');
            updateTopControlsByScroll();
            window.scrollTo(0, 0);
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
            }, 200);
        }
        async function submitReview() {
            const text = document.getElementById('rev-text').value.trim();
            const ratingEl = document.querySelector('input[name="rating"]:checked');
            const fileInput = document.getElementById('rev-image');
            const sessionName = localStorage.getItem("tfc_session");

            if (!text || !ratingEl) {
                alert("Пожалуйста, напишите отзыв и выберите количество звезд.");
                return;
            }

            const formData = new FormData();
            formData.append('name', sessionName || "Гость");
            formData.append('text', text);
            formData.append('stars', parseInt(ratingEl.value));
            if (fileInput.files[0]) {
                formData.append('image', fileInput.files[0]);
            }

            const res = await fetch('/api/reviews/add', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (data.ok) {
                showLiveStatus("Спасибо! Ваш отзыв принят. ✅", true);
                document.getElementById('rev-text').value = '';
                ratingEl.checked = false;
                if (fileInput) fileInput.value = '';
            }
        }

        async function deleteReview(id) {
            const code = prompt("Введите код для удаления:");
            if (code === "anis1234") {
                const res = await fetch(adminApiBase() + `/api/reviews/delete/${id}`, { method: 'POST' });
                const data = await res.json();
                if (data.ok) {
                    location.reload();
                } else {
                    alert("Ошибка при удалении.");
                }
            } else if (code !== null) {
                alert("Неверный код!");
            }
        }
        // Бор кардани таърихи хабарҳо аз хотираи браузер ҳангоми оғоз
        let notificationsHistory = JSON.parse(localStorage.getItem("tfc_notifications_history") || "[]");
        let unreadNotifCount = parseInt(localStorage.getItem("tfc_unread_notif_count") || "0");

        // Автоматикӣ тоза кардани хабарҳои аз 12 соат кӯҳна
        const twelveHours = 12 * 60 * 60 * 1000;
        const now = Date.now();
        notificationsHistory = notificationsHistory.filter(n => !n.timestamp || (now - n.timestamp) < twelveHours);
        localStorage.setItem("tfc_notifications_history", JSON.stringify(notificationsHistory));
        unreadNotifCount = notificationsHistory.filter(n => n.isNew).length;
        localStorage.setItem("tfc_unread_notif_count", unreadNotifCount);

        function updateNotifBadge() {
            const badge = document.getElementById('notif-count');
            if (badge) {
                badge.textContent = unreadNotifCount;
                badge.classList.toggle('hidden', unreadNotifCount === 0);
            }
        }

        function showNotifications() {
            setTimeout(() => {
            document.getElementById('intro-section').style.display = 'none';
            document.getElementById('menu').style.display = 'none';
            document.getElementById('notifications-section').style.display = 'block';
            renderNotificationsList();
            // Ҳангоми кушодани хабарҳо, ҳисобкунакро тоза мекунем
            notificationsHistory.forEach(n => { n.isNew = false; });
            localStorage.setItem("tfc_notifications_history", JSON.stringify(notificationsHistory));

            unreadNotifCount = 0;
            localStorage.setItem("tfc_unread_notif_count", unreadNotifCount);
            updateNotifBadge();
            if(typeof animateSection === 'function') animateSection('notifications-section');
            setTopControlsVisible(false);
            window.scrollTo(0, 0);
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
            }, 350);
        }
        function hideNotifications() {
            setTimeout(() => {
            document.getElementById('notifications-section').style.display = 'none';
            document.getElementById('menu').style.display = 'block';
            document.getElementById('intro-section').style.display = 'flex';
            animateSection('menu');
            animateSection('intro-section');
            updateTopControlsByScroll();
            window.scrollTo(0, 0);
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
            }, 350);
        }

        // New Sushi Subcategory Logic
        function showSushi() {
            setTimeout(() => {
                document.getElementById('intro-section').style.display = 'none';
                document.getElementById('menu').style.display = 'none';
                const sushiSection = document.getElementById('sushi-section');
                const subCategories = document.getElementById('sushi-subcategories');
                const productGrid = document.getElementById('sushi-filtered-product-grid');

                sushiSection.style.display = 'block';
                subCategories.style.display = 'grid'; // Show subcategory cards
                document.getElementById('sushi-category-back-btn').style.display = 'none'; // Hide sub-back
                document.getElementById('sushi-main-back-btn').style.display = 'inline-flex'; // Show main-back

                sushiSection.querySelector('h2').innerHTML = 'СУШИ И РОЛЛЫ'; // Reset title
                // Пинҳон кардани хӯрокҳо то он даме, ки зергурӯҳ интихоб шавад
                productGrid.querySelectorAll('.product-card').forEach(c => c.style.display = 'none');

                if(typeof animateSection === 'function') animateSection('sushi-section');
                setTopControlsVisible(false);
                window.scrollTo(0, 0);
                document.documentElement.scrollTop = 0;
                document.body.scrollTop = 0;
            }, 350);
        }

        function filterSushi(subCategory) {
            const sushiSection = document.getElementById('sushi-section');
            const grid = document.getElementById('sushi-filtered-product-grid');
            const title = sushiSection.querySelector('h2');

            setTimeout(() => {
                document.getElementById('sushi-subcategories').style.display = 'none';
                document.getElementById('sushi-main-back-btn').style.display = 'none';
                document.getElementById('sushi-category-back-btn').style.display = 'inline-flex'; // Show sub-back

                title.innerHTML = subCategory.toUpperCase();

                const cards = grid.querySelectorAll('.product-card');
                cards.forEach(card => {
                    const cardSub = card.getAttribute('data-subcategory') || '';
                    const name = card.getAttribute('data-name').toUpperCase();
                    let show = false;
                    
                    if (cardSub === subCategory) {
                        show = true;
                    } else if (!cardSub) {
                        if (subCategory === 'Суши') {
                            show = name.includes('СУШИ') && !(name.includes('РОЛЛ') || name.includes('МАКИ') || name.includes('КАЛИФОРНИЯ') || name.includes('СЕТ') || name.includes('ТЕМПУРА'));
                        } else if (subCategory === 'Роллы') {
                            show = name.includes('РОЛЛ') || name.includes('МАКИ') || name.includes('КАЛИФОРНИЯ') || name.includes('ТЕМПУРА') || name.includes('СЕТ') || (name.includes('ЗАПЕЧЕН') && !name.includes('СУШИ'));
                        }
                    }
                    card.style.display = show ? 'block' : 'none';
                });

                window.scrollTo(0, 0);
                document.documentElement.scrollTop = 0;
                document.body.scrollTop = 0;

                [title, grid].forEach(el => {
                    el.classList.remove('page-transition');
                    void el.offsetWidth;
                    el.classList.add('page-transition');
                });
            }, 250);
        }

        function hideSushi() {
            setTimeout(() => {
                stopAllVideos();
                document.getElementById('sushi-section').style.display = 'none';
                document.getElementById('menu').style.display = 'block';
                document.getElementById('intro-section').style.display = 'flex';
                animateSection('menu');
                animateSection('intro-section');
                updateTopControlsByScroll();
                window.scrollTo(0, 0);
                document.documentElement.scrollTop = 0;
                document.body.scrollTop = 0;
            }, 350);
        }

        function clearNotifications() {
            document.getElementById('notif-clear-modal-overlay').classList.add('active');
        }

        function closeNotifClearModal() {
            document.getElementById('notif-clear-modal-overlay').classList.remove('active');
        }

        function executeClearNotifications() {
            notificationsHistory = [];
            localStorage.setItem("tfc_notifications_history", JSON.stringify(notificationsHistory));
            unreadNotifCount = 0;
            localStorage.setItem("tfc_unread_notif_count", "0");
            updateNotifBadge();
            renderNotificationsList();
            closeNotifClearModal();
        }

        function renderNotificationsList() {
            const list = document.getElementById('notifications-history-list');
            if (notificationsHistory.length === 0) {
                list.innerHTML = '<p class="text-center opacity-50 py-10">Уведомлений пока нет.</p>';
                return;
            }
            list.innerHTML = notificationsHistory.map(n => `
                <div class="notif-item p-4 rounded-xl relative">
                    ${n.isNew ? '<span class="absolute top-2 right-2 w-5 h-5 bg-red-600 text-white rounded-full flex items-center justify-center text-[10px] font-bold animate-pulse shadow-[0_0_10px_rgba(220,38,38,0.5)]">!</span>' : ''}
                    <div class="text-[10px] opacity-40 uppercase mb-1">${n.time}</div>
                    <div class="text-sm">${n.message}</div>
                </div>
            `).reverse().join('');
        }

        function signOut() {
            if(confirm("Вы действительно хотите выйти из аккаунта?")) {
                localStorage.removeItem("tfc_session");
                localStorage.removeItem("tfc_customer_profile");
                localStorage.removeItem("tfc_notifications_history");
                localStorage.removeItem("tfc_last_notified_status");
                window.location.reload();
            }
        }

        window.addEventListener("scroll", updateTopControlsByScroll);

        function adminApiBase() {
            return "https://tfc-admin-panel.onrender.com";
        }

        let selectedOrderPayload = null;
        let statusPollTimer = null;
        // Ибтидоӣ аз localStorage барои пешгирӣ аз такрор пас аз refresh
        let latestCustomerStatus = localStorage.getItem("tfc_last_notified_status") || "";
        let liveStatusTimeout = null; // Тағйироти нав: барои нигоҳ доштани ID-и setTimeout
        
        // Овози хабарнома аз папкаи static
        const notificationSound = new Audio("/static/music.mp3");

        function parsePriceOptions(rawPrice) {
            const clean = String(rawPrice || "").replace(/\\s+/g, "").replace(/[сc]$/, "");
            if (!clean.includes("/")) {
                const one = parseFloat(clean.replace(/[^0-9.,]/g, "").replace(",", "."));
                return isNaN(one) ? [] : [{ label: "Стандарт", value: one }];
            }
            const parts = clean.split("/").map(function (p) {
                return parseFloat(p.replace(/[^0-9.,]/g, "").replace(",", "."));
            }).filter(function (n) { return !isNaN(n); });
            if (parts.length < 2) return [];
            return [
                { label: "Маленький", value: parts[0] },
                { label: "Большой", value: parts[1] }
            ];
        }

        function openOrderModal(card) {
            const titleEl = card.querySelector(".product-info h3");
            const priceEl = card.querySelector(".price-tag");
            const food = titleEl ? titleEl.textContent.trim() : "";
            const subcat = card.getAttribute('data-subcategory') || "";
            const price = priceEl ? priceEl.textContent.trim() : "";
            const options = parsePriceOptions(price);

            const overlay = document.getElementById("order-modal-overlay");
            const titleNode = document.getElementById("modal-food-title");
            const optionsNode = document.getElementById("size-options");
            const totalNode = document.getElementById("modal-total");

            const qtyInput = document.getElementById("modal-qty");

            titleNode.textContent = food || "Блюдо";
            document.getElementById("modal-customer-phone").value = "";
            if (qtyInput) qtyInput.value = "1";
            optionsNode.innerHTML = "";

            selectedOrderPayload = {
                food: food || "Блюдо",
                priceText: price || "0",
                selectedLabel: options.length ? options[0].label : "Стандарт",
                selectedPrice: options.length ? options[0].value : parseFloat(String(price || "0").replace(/[^0-9.,]/g, "").replace(",", ".")) || 0,
                subcategory: subcat
            };

            const sourceOptions = options.length ? options : [{ label: "Стандарт", value: selectedOrderPayload.selectedPrice }];
            sourceOptions.forEach(function (opt, idx) {
                const b = document.createElement("button");
                b.type = "button";
                b.className = "size-btn" + (idx === 0 ? " active" : "");
                b.textContent = opt.label + " - " + opt.value + " сомони";
                b.onclick = function () {
                    selectedOrderPayload.selectedLabel = opt.label;
                    selectedOrderPayload.selectedPrice = opt.value;
                    Array.from(optionsNode.children).forEach(function (x) { x.classList.remove("active"); });
                    b.classList.add("active");
                    updateModalTotal();
                };
                optionsNode.appendChild(b);
            });

            updateModalTotal();
            overlay.classList.add("active");
        }

        function updateModalTotal() {
            if (!selectedOrderPayload) return;
            const totalNode = document.getElementById("modal-total");
            const qtyInput = document.getElementById("modal-qty");
            const qty = Math.max(1, parseInt(qtyInput.value || "1", 10) || 1);
            qtyInput.value = String(qty);
            const total = selectedOrderPayload.selectedPrice * qty;
            totalNode.textContent = total + " сомони";
        }

        function changeQty(delta) {
            const qtyNode = document.getElementById("modal-qty");
            let current = parseInt(qtyNode.value || "1", 10);
            qtyNode.value = String(Math.max(1, current + delta));
            updateModalTotal();
        }

        function closeOrderModal() {
            setTimeout(() => {
                const overlay = document.getElementById("order-modal-overlay");
                overlay.classList.remove("active");
                selectedOrderPayload = null;
            }, 150);
        }

        function submitOrderFromCard(orderData) {
            let profile = null;
            try {
                profile = JSON.parse(localStorage.getItem("tfc_customer_profile") || "null");
            } catch (e) {}

            if (!profile || !profile.fullName || !profile.id) {
                alert("Пожалуйста, сначала авторизуйтесь, чтобы сделать заказ.");
                return;
            }

            // Получаем адрес если это доставка
            let address = sessionStorage.getItem('delivery_address') || '';
            const lat = '';
            const lng = '';

            fetch(adminApiBase() + "/api/orders/new", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    customer: profile.fullName,
                    customer_id: profile.id,
                    food: orderData.food,
                    price: orderData.price,
                    phone: orderData.phone,
                    delivery_type: orderData.delivery_type,
                    tip: orderData.tip || "",
                    payment_method: orderData.payment_method || "online",
                    delivery_latitude: lat,
                    delivery_longitude: lng,
                    delivery_address: address
                }),
            })
                .then(function (r) {
                    return r.json();
                })
                .then(function (data) {
                    if (data && data.ok) {
                        const msg = "Ваш заказ <b>отправлен</b>! ✅";
                        latestCustomerStatus = data.order_id + "_pending";
                        localStorage.setItem("tfc_last_notified_status", latestCustomerStatus);
                        showLiveStatus(msg, false);

                        closeOrderModal();
                        // Очищаем адрес после использования
                        sessionStorage.removeItem('delivery_address');
                    } else {
                        alert("Не удалось отправить заказ.");
                    }
                })
                .catch(function (error) {
                    console.error("Error:", error);
                    alert("Ошибка подключения! Убедитесь, что сервер работает.");
                });
        }

        let cart = [];
        const subEmojiMap = {
            'Паста': '🍝', 'Салаты': '🥗', 'Супы': '🥣', 'Горячие блюда': '🍖', 'Десерты': '🍰', 'Напитки': '☕',
            'Хот-доги': '🌭', 'Бургеры': '🍔', 'Тортильи': '🌯', 'Сэндвичи': '🥪', 'Гарниры': '🍟',
            'Суши': '🍣', 'Роллы': '🍱', 'Смузи': '🍹', 'Мохито': '🍸', 'Холодок': '❄️'
        };

        function addToCart() {
            if (!selectedOrderPayload) return;
            const qtyInput = document.getElementById("modal-qty");
            const qty = parseInt(qtyInput.value || "1", 10);
            
            cart.push({
                ...selectedOrderPayload,
                qty: qty
            });
            
            updateCartBadge();
            animateToCart();
            closeOrderModal();
        }

        function showCart() {
            renderCart();
            const overlay = document.getElementById('cart-modal-overlay');
            overlay.classList.add('active');
        }

        function closeCartModal() {
            const overlay = document.getElementById('cart-modal-overlay');
            overlay.classList.remove('active');
        }

        function openFoodInfoOverlay(card) {
            const title = card.querySelector(".product-info h3")?.textContent.trim() || "Блюдо";
            const price = card.querySelector(".price-tag")?.textContent.trim() || "";
            const imgSrc = card.querySelector("img")?.src || "";
            const hiddenDesc = card.querySelector('.food-description')?.textContent.trim() || "";
            const description = hiddenDesc || card.dataset.description || "";
            const overlay = document.getElementById('food-info-overlay');
            const button = card.querySelector('.food-info-sign');

            // Button animation
            if (button) {
                button.style.animation = 'none';
                setTimeout(() => {
                    button.style.animation = '';
                }, 10);
            }

            document.getElementById('info-food-title').textContent = title;
            document.getElementById('info-food-price').textContent = price;
            document.getElementById('info-food-image').src = imgSrc;
            document.getElementById('info-food-image').alt = title;
            document.getElementById('info-food-description').innerHTML = formatDescriptionForHtml(description || getDefaultDescription(title));

            // Show overlay with a small delay for better effect
            setTimeout(() => {
                overlay.classList.add('active');
            }, 50);
        }

        function closeFoodInfoOverlay() {
            const overlay = document.getElementById('food-info-overlay');
            // Reset any card animations
            document.querySelectorAll('.product-card.show-order').forEach(c => c.classList.remove('show-order'));
            overlay.classList.remove('active');
        }

        function formatDescriptionForHtml(text) {
            if (!text) return "<p class='text-white/70'>Информация отсутствует.</p>";
            const lines = text.trim().split(/\r?\n/);
            let html = "";
            let inList = false;

            lines.forEach((rawLine) => {
                const line = rawLine.trim();
                if (!line) {
                    if (inList) { html += "</ul>"; inList = false; }
                    html += "<br>";
                    return;
                }

                const decorated = line.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
                const headingMatch = decorated.match(/^###\s*(.*)$/);
                const listMatch = decorated.match(/^-\s*(.*)$/);

                if (headingMatch) {
                    if (inList) { html += "</ul>"; inList = false; }
                    html += `<h3 class="text-xl font-black mb-3">${headingMatch[1]}</h3>`;
                    return;
                }

                if (listMatch) {
                    if (!inList) { html += "<ul class='list-disc pl-5 mb-3'>"; inList = true; }
                    html += `<li class="mb-1">${listMatch[1]}</li>`;
                    return;
                }

                if (inList) { html += "</ul>"; inList = false; }
                html += `<p class="mb-2">${decorated}</p>`;
            });

            if (inList) html += "</ul>";
            return html;
        }

        function getDefaultDescription(title) {
            const normTitle = title.toUpperCase().replace(/[–—]/g, '-').trim();
            const defaults = {
                "НОН-ДОГ": "### 1. НОН-ДОГ\n\n- **Состав:** Лепешка, сосиска, помидор, огурцы.\n- **Цены:** L: 5с\nXL: 7с",
                "NON-DOG": "### 1. НОН-ДОГ\n\n- **Состав:** Лепешка, сосиска, помидор, огурцы.\n- **Цены:** L: 5с\nXL: 7с",
                "БУЛОЧКА": "### 2. БУЛОЧКА\n\n- **Состав:** Булочка, сосиска, помидор, огурцы.\n- **Цены:** L: 6с\nXL: 8с",
                "М-ДОГ": "### 3. М-ДОГ\n\n- **Состав:** Булочка, сосиска, помидор, огурцы.\n- **Цена:** 10с",
                "TFC-ДОГ": "### 4. TFC-ДОГ\n\n- **Состав:** Булочка, фирменный соус, котлета, курица, помидор, огурцы, соус бургер, салатный лист.\n- **Цены:** L: 18с\nXL: 30с"
            };
            return defaults[normTitle] || "Информация отсутствует.";
        }

        function renderCart() {
            const listNode = document.getElementById('cart-items-list');
            const totalNode = document.getElementById('cart-total-price');
            listNode.innerHTML = '';
            let total = 0;

            if (cart.length === 0) {
                listNode.innerHTML = '<p class="text-center opacity-50 py-10">Ваша корзина пуста.</p>';
                totalNode.textContent = "0 сомони";
                return;
            }

            cart.forEach((item, index) => {
                const itemTotal = item.selectedPrice * item.qty;
                total += itemTotal;
                
                const emoji = subEmojiMap[item.subcategory] || '🥡';
                
                const itemEl = document.createElement('div');
                itemEl.className = "flex items-center gap-4 mb-4 p-3 rounded-2xl bg-white/5 border border-white/10";
                itemEl.innerHTML = `
                    <div class="text-3xl w-12 h-12 flex items-center justify-center bg-white/5 rounded-xl">${emoji}</div>
                    <div class="flex-1">
                        <h4 class="font-bold text-sm">${item.food}</h4>
                        <p class="text-[10px] opacity-50 uppercase tracking-wider">${item.selectedLabel} x ${item.qty}</p>
                        <div class="text-yellow-400 font-black text-sm mt-1">${itemTotal} смн</div>
                    </div>
                    <button onclick="removeFromCart(${index}, this)" class="w-10 h-10 rounded-xl bg-red-600/20 text-red-500 hover:bg-red-600 hover:text-white transition-all active:scale-90">
                        <i class="fa-solid fa-trash-can text-xs"></i>
                    </button>
                `;
                listNode.appendChild(itemEl);
            });

            totalNode.textContent = total + " сомони";
        }

        function removeFromCart(index, btnEl) {
            const itemEl = btnEl.closest('.flex');
            gsap.to(itemEl, { x: 50, opacity: 0, duration: 0.3, onComplete: () => {
                cart.splice(index, 1);
                updateCartBadge();
                renderCart();
            }});
        }

        function showPhoneOrderModal() {
            const overlay = document.getElementById('phone-order-modal-overlay');
            overlay.classList.add('active');
        }

        function closePhoneOrderModal() {
            const overlay = document.getElementById('phone-order-modal-overlay');
            overlay.classList.remove('active');
        }


        async function confirmFullCartOrder(e) {
            if (cart.length === 0) return alert("Корзина пуста!");
            const phoneNode = document.getElementById("cart-customer-phone");
            const phone = phoneNode.value.trim();

            const btn = e ? (e.currentTarget || e.target.closest('button')) : null;
            if(btn) gsap.to(btn, { scale: 0.95, duration: 0.1, yoyo: true, repeat: 1 });

            if (!phone || phone.length < 5) return alert("Введите номер телефона!");
            const phoneError = document.getElementById("cart-phone-error");
            if (phone.length !== 9) {
                phoneError.textContent = "Пожалуйста, введите 9 цифр.";
                phoneError.classList.remove("hidden");
                phoneNode.focus();
                return;
            } else { phoneError.classList.add("hidden"); }
            showWarningBeforeSubmit(() => {
                showDeliverySelection(async (type, payPhone) => {
                    const total = cart.reduce((sum, item) => sum + (item.selectedPrice * item.qty), 0);
                    const foodList = cart.map((item, idx) => `${idx + 1}. ${item.food} [${item.selectedLabel}] x${item.qty}`).join(', ');

                    showPaymentInstruction(total, (paymentMethod) => {
                        cart = [];
                        updateCartBadge();
                        closeCartModal();
                        submitOrderFromCard({ food: foodList, price: String(total), phone: phone, delivery_type: type, payment_method: paymentMethod, payment_phone: payPhone });
                    }, payPhone);
                });
            });
        }

        function updateCartBadge() {
            const badge = document.getElementById('cart-count');
            if (badge) {
                badge.textContent = cart.length;
                badge.classList.toggle('hidden', cart.length === 0);
                const totalQty = cart.reduce((sum, item) => sum + item.qty, 0);
                badge.textContent = totalQty;
                badge.classList.toggle('hidden', totalQty === 0);
            }
        }

        function animateToCart() {
            const modal = document.querySelector('.order-modal');
            const cartBtn = document.getElementById('cart-btn');
            if (!modal || !cartBtn) return;

            const rect = modal.getBoundingClientRect();
            const cartRect = cartBtn.getBoundingClientRect();
            const emoji = subEmojiMap[selectedOrderPayload.subcategory] || '🥡';
            console.log(selectedOrderPayload.subcategory);

            const flyer = document.createElement('div');
            flyer.innerHTML = `<div class="text-4xl">${emoji}</div>`;
            flyer.style.cssText = `position:fixed; z-index:13000; pointer-events:none; left:${rect.left + rect.width/2}px; top:${rect.top + rect.height/2}px;`;
            document.body.appendChild(flyer);

            gsap.to(flyer, {
                x: cartRect.left - rect.left - rect.width/2 + 20,
                y: cartRect.top - rect.top - rect.height/2 + 20,
                scale: 0.2,
                opacity: 0,
                duration: 1,
                ease: "power2.inOut",
                onComplete: () => flyer.remove()
            });
        }

        function confirmOrderFromModal(e) {
            if (!selectedOrderPayload) return;
            const qtyInput = document.getElementById("modal-qty");
            const phoneNode = document.getElementById("modal-customer-phone");

            const btn = e ? (e.currentTarget || e.target.closest('button')) : null;
            if(btn) gsap.to(btn, { scale: 0.95, duration: 0.1, yoyo: true, repeat: 1 });

            const qty = Math.max(1, parseInt(qtyInput.value || "1", 10) || 1);
            const total = selectedOrderPayload.selectedPrice * qty;
            const orderFood = selectedOrderPayload.food + " [" + selectedOrderPayload.selectedLabel + "] x" + qty;
            const orderPrice = String(total);

            const phone = phoneNode.value.trim();
            const phoneError = document.getElementById("modal-phone-error");
            if (phone.length !== 9) {
                phoneError.textContent = "Пожалуйста, введите 9 цифр.";
                phoneError.classList.remove("hidden");
                phoneNode.focus();
                return;
            } else { phoneError.classList.add("hidden"); }

            // Пеш аз фиристодан, огоҳиномаро нишон медиҳем
            setTimeout(() => {
                showWarningBeforeSubmit(() => {
                    showDeliverySelection((type, payPhone) => {
                        showPaymentInstruction(total, (paymentMethod) => {
                            submitOrderFromCard({ food: orderFood, price: orderPrice, phone: phone, delivery_type: type, payment_method: paymentMethod, payment_phone: payPhone });
                        }, payPhone);
                    });
                });
            }, 200);
        }

        function showWarningBeforeSubmit(onConfirm) {
            const overlay = document.createElement('div');
            overlay.className = "fixed inset-0 z-[12000] bg-black/80 backdrop-blur-md flex items-center justify-center p-6";
            overlay.innerHTML = `
                <div class="bg-zinc-900 border border-white/10 p-8 rounded-[32px] max-w-sm w-full text-center shadow-2xl animate-in zoom-in duration-300">
                    <div class="w-16 h-16 bg-red-500/20 text-red-500 rounded-full flex items-center justify-center mx-auto mb-4 text-3xl shadow-[0_0_20px_rgba(239,68,68,0.3)]">
                        <i class="fa-solid fa-circle-exclamation"></i>
                    </div>
                    <h2 class="text-xl font-black text-white mb-2">ВНИМАНИЕ!</h2>
                    <p class="text-white/60 text-sm mb-6 leading-relaxed">Пожалуйста, <b>не выходите из приложения</b> до тех пор, пока ваш заказ не будет готов!</p>
                    <button id="btn-ponyaltu" class="w-full py-4 bg-yellow-400 text-black font-black rounded-2xl active:scale-95 transition shadow-lg shadow-yellow-400/20">ПОНЯЛ</button>
                </div>
            `;
            document.body.appendChild(overlay);
            document.getElementById('btn-ponyaltu').onclick = () => {
                setTimeout(() => {
                    overlay.remove();
                    onConfirm();
                }, 200);
            };
        }

        function showPaymentInstruction(totalAmount, onComplete, paymentPhoneNumber) {
            const overlay = document.createElement('div');
            overlay.className = "fixed inset-0 z-[12001] bg-black/90 backdrop-blur-xl flex items-center justify-center p-6";
            const adminNumber = paymentPhoneNumber || "754169090"; 
            const profile = getOrCreateCustomerProfile();
            const customerId = (profile && profile.id) ? profile.id : '';
            overlay.innerHTML = `
                <div class="bg-zinc-900 border border-white/10 p-8 rounded-[32px] max-w-sm w-full text-center shadow-2xl animate-in zoom-in duration-300">
                    <div class="w-20 h-20 bg-yellow-400/20 text-yellow-400 rounded-full flex items-center justify-center mx-auto mb-6 text-4xl shadow-[0_0_30px_rgba(255,215,0,0.2)]">
                        <i class="fa-solid fa-wallet"></i>
                    </div>
                    <h2 class="text-2xl font-black text-white mb-2 uppercase tracking-tight">Оплата</h2>
                    <p class="text-white/60 text-xs mb-6 leading-relaxed">Скопируйте номер и оплатите <b class="text-yellow-400 text-lg">${totalAmount}</b> сомони. <br><b class="text-red-500">НЕ ЗАКРЫВАЙТЕ ПРИЛОЖЕНИЕ!</b></p>
                    
                    <div class="bg-white/5 border border-white/10 p-5 rounded-2xl flex items-center justify-between mb-8 group active:bg-white/10 transition-all">
                        <span class="text-2xl font-black text-white tracking-widest">${adminNumber}</span>
                        <button onclick="copyAdminNumber('${adminNumber}', this)" class="w-12 h-12 bg-yellow-400 text-black rounded-xl flex items-center justify-center transition-all active:scale-90" title="Копировать номер">
                            <i class="fa-solid fa-copy"></i>
                        </button>
                    </div>

                    <div class="flex flex-col gap-3">
                        <button id="btn-payment-confirmed" disabled class="w-full py-4 bg-black/50 text-white/40 font-black rounded-2xl transition uppercase tracking-widest text-xs cursor-not-allowed">
                            Я оплатил(а) (Картой)
                        </button>
                        <button id="btn-pay-cash" class="w-full py-4 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-black rounded-2xl active:scale-95 transition shadow-lg shadow-emerald-500/20 uppercase tracking-widest text-xs flex items-center justify-center gap-2">
                            <i class="fas fa-money-bill-wave"></i> НАЛИЧНЫМИ
                        </button>
                    </div>
                </div>
            `;
            document.body.appendChild(overlay);

            const confirmBtn = document.getElementById('btn-payment-confirmed');
            const cashBtn = document.getElementById('btn-pay-cash');
            const unlockButton = () => {
                confirmBtn.disabled = false;
                confirmBtn.className = "w-full py-4 bg-green-600 text-white font-black rounded-2xl active:scale-95 transition shadow-lg shadow-green-500/20 uppercase tracking-widest text-xs";
                window.removeEventListener('focus', unlockButton);
            };

            // Тугма вақте фаъол мешавад, ки муштарӣ аз дигар барнома ба браузер бармегардад
            window.addEventListener('focus', unlockButton);

            window.copyAdminNumber = (text, btn) => {
                navigator.clipboard.writeText(text).then(() => {
                    const icon = btn.querySelector('i');
                    icon.className = 'fa-solid fa-check';
                    setTimeout(() => icon.className = 'fa-solid fa-copy', 2000);
                });
            };

            cashBtn.onclick = () => {
                overlay.remove();
                onComplete("cash");
                window.removeEventListener('focus', unlockButton);
            };

            confirmBtn.onclick = () => {
                if (confirmBtn.disabled) return;
                overlay.remove();
                onComplete("online");
                window.removeEventListener('focus', unlockButton);
            };
        }

        function showDeliverySelection(onSelect) { // onSelect(type, phone)
            const overlay = document.createElement('div');
            overlay.className = "fixed inset-0 z-[12000] bg-black/80 backdrop-blur-md flex items-center justify-center p-6";
            overlay.innerHTML = `
                <div class="bg-zinc-900 border border-white/10 p-8 rounded-[32px] max-w-sm w-full text-center shadow-2xl animate-in zoom-in duration-300 overflow-y-auto max-h-[90vh]">
                    <div id="delivery-step-1">
                    <h2 class="text-xl font-black text-white mb-2">КАК ВАМ УДОБНО?</h2>
                    <p class="text-white/60 text-sm mb-6 leading-relaxed">Пожалуйста, выберите способ получения заказа:</p>
                    <div class="grid grid-cols-1 gap-3">
                        <button id="btn-delivery" class="w-full py-4 bg-red-600 text-white font-black rounded-2xl active:scale-95 transition flex items-center justify-center gap-3"><i class="fas fa-truck"></i> ДОСТАВКА</button>
                        <button id="btn-pickup" class="w-full py-4 bg-white/10 text-white font-black rounded-2xl active:scale-95 transition border border-white/10 flex items-center justify-center gap-3"><i class="fas fa-walking"></i> САМОВЫВОЗ</button>
                    </div>
                    </div>
                    <div id="delivery-step-2" class="hidden">
                        <div class="w-16 h-16 bg-red-600/20 text-red-600 rounded-full flex items-center justify-center mx-auto mb-4 text-3xl">
                            <i class="fa-solid fa-map-location-dot"></i>
                        </div>
                        <h2 class="text-xl font-black text-white mb-2 uppercase">КУДА ДОСТАВИТЬ?</h2>
                        <p class="text-white/60 text-sm mb-6 leading-relaxed">Пожалуйста, напишите ваш точный адрес:</p>
                        <textarea id="delivery-address-input" name="cust_addr_no_fill" rows="2" placeholder="Напишите здесь..."
                                  autocomplete="new-password" autocorrect="off" autocapitalize="off" spellcheck="false"
                                  class="w-full px-4 py-3 rounded-xl border border-white/10 bg-black/20 text-white focus:ring-2 focus:ring-yellow-400 outline-none transition font-bold mb-4"></textarea>
                        <button id="btn-confirm-address" class="w-full py-4 bg-blue-600 text-white font-black rounded-2xl active:scale-95 transition flex items-center justify-center gap-3 shadow-lg shadow-blue-500/20">
                            <i class="fas fa-check"></i> ПОДТВЕРДИТЬ АДРЕС
                        </button>
                    </div>
                </div>
            `;
            document.body.appendChild(overlay);
            
            document.getElementById('btn-delivery').onclick = () => { 
                document.getElementById('delivery-step-1').classList.add('hidden');
                document.getElementById('delivery-step-2').classList.remove('hidden');
                const addressInput = document.getElementById('delivery-address-input');

                // Вақте ки клавиатура пайдо мешавад, равзанаро ба боло мебарем
                addressInput.onfocus = () => {
                    overlay.classList.replace('items-center', 'items-start');
                    overlay.classList.add('pt-10');
                };
                addressInput.onblur = () => {
                    overlay.classList.replace('items-start', 'items-center');
                    overlay.classList.remove('pt-10');
                };
                addressInput.focus();
            };
            document.getElementById('btn-confirm-address').onclick = () => {
                const address = document.getElementById('delivery-address-input').value.trim();
                if (address.length < 5) return alert("Пожалуйста, введите полный адрес!");
                sessionStorage.setItem('delivery_address', address);
                
                // Гирифтани рақами навбатӣ барои Доставка
                fetch('/api/get-next-payment-phone')
                    .then(r => r.json())
                    .then(data => {
                        overlay.remove(); 
                        onSelect('delivery', data.phone);
                    });
            };

            document.getElementById('btn-pickup').onclick = () => { 
                // Гирифтани рақами навбатӣ барои Самовывоз (Гардиш)
                fetch(adminApiBase() + '/api/get-next-payment-phone')
                    .then(r => r.json())
                    .then(data => {
                        overlay.remove(); 
                        onSelect('pickup', data.phone);
                    });
            };
        }

        function showLiveStatus(message, isOk) {
            // Илова ба таърихи хабарҳо
            notificationsHistory.push({ message, isOk, time: new Date().toLocaleTimeString('ru-RU'), isNew: true });
            notificationsHistory.push({ 
                message, 
                isOk, 
                time: new Date().toLocaleTimeString('ru-RU'), 
                timestamp: Date.now(), 
                isNew: true 
            });
            // Захира кардан дар localStorage
            localStorage.setItem("tfc_notifications_history", JSON.stringify(notificationsHistory));
            
            // Пахши овоз ҳангоми пайдо шудани хабарнома
            notificationSound.play().catch(e => console.warn("Audio play blocked by browser:", e));
            
            // Агар саҳифаи хабарҳо кушода набошад, шумораро зиёд мекунем
            const isNotifOpen = document.getElementById('notifications-section').style.display === 'block';
            if (!isNotifOpen) {
                unreadNotifCount++;
                localStorage.setItem("tfc_unread_notif_count", unreadNotifCount);
                updateNotifBadge();
            }

            const chip = document.getElementById("live-status-chip");
            
            // Тоза кардани ҳама гуна setTimeout-и мавҷуда
            if (liveStatusTimeout) {
                clearTimeout(liveStatusTimeout);
            }

            // Аниматсия ва намоишро барои эффекти "пайдошавии нав" аз нав танзим кунед
            chip.style.animation = "none"; // Аниматсияи қаблиро тоза кунед
            chip.style.display = "none";
            void chip.offsetWidth; 
            
            chip.innerHTML = `
                <div class="flex items-center gap-3">
                    <div class="w-7 h-7 shrink-0 rounded-full flex items-center justify-center ${isOk ? 'bg-green-100 text-green-600' : 'bg-yellow-100 text-yellow-600'} text-sm shadow-inner">
                        <i class="fa-solid ${isOk ? 'fa-check' : 'fa-bell'}"></i>
                    </div>
                    <div class="leading-tight font-bold text-gray-800">${message}</div>
                </div>
            `;
            chip.classList.toggle("ok", !!isOk);
            chip.style.display = "block"; // Чипро намоиш диҳед
            chip.style.animation = "slideInNotif 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards"; // Аниматсияи пайдошавиро татбиқ кунед

            // Хабарнома дар экран 6 сония меистад
            liveStatusTimeout = setTimeout(() => {
                chip.style.animation = "slideOutNotif 0.5s ease forwards"; // Аниматсияи нопадидшавиро татбиқ кунед
                setTimeout(() => {
                    chip.style.display = "none"; // Пас аз ба итмом расидани аниматсия пинҳон кунед
                }, 500); // Бо давомнокии аниматсияи slideOutNotif мувофиқат кунед
            }, 6000); 
        }

        async function pollCustomerStatus() {
            let profile = null;
            try {
                profile = JSON.parse(localStorage.getItem("tfc_customer_profile") || "null");
            } catch (e) {}
            if (!profile || !profile.id) return;
            try {
                const res = await fetch(adminApiBase() + "/api/orders/customer-status?customer_id=" + encodeURIComponent(profile.id), { cache: "no-store" });
                if (!res.ok) return;
                const data = await res.json();
                if (!data || !data.ok || !Array.isArray(data.orders) || data.orders.length === 0) return;
                const last = data.orders[data.orders.length - 1];
                
                let statusType = "pending";
                let deliveryMsg = last.delivery_type === 'delivery' ? 'Доставка' : 'Самовывоз';
                let statusText = "Ваш заказ <b>отправлен</b>! ✅";
                let ok = false;

                let oosPart = "";
                // Тафтиш: Оё ҳамаи хӯрокҳо хат зада шудаанд?
                const cleanPrice = parseFloat(String(last.price || 0).replace(',', '.').replace(/[^0-9.]/g, ''));
                if (last.out_of_stock && parseFloat(last.refund) >= cleanPrice && cleanPrice > 0) {
                    statusType = "cancelled_oos";
                    statusText = `К сожалению, нет никаких блюд и мы вернем ваши деньги: ${last.refund} смн. ❌`;
                } else if (last.out_of_stock) {
                    const missingItems = [];
                    const regex = /<s>(.*?)<\/s>/g;
                    let match;
                    while ((match = regex.exec(last.food)) !== null) {
                        missingItems.push(match[1]);
                    }
                    if (missingItems.length > 0) {
                        const refundTxt = last.refund > 0 ? ` Из-за того, что у нас нет такого блюда, мы вернем вам ваши деньги: ${last.refund} сомони.` : "";
                        oosPart = `<br><span class="text-red-500 font-bold">Извините, "${missingItems.join(", ")}" нет в наличии.${refundTxt} ❌</span>`;
                    }
                }

                if (statusText.includes("К сожалению")) {
                    // Матни махсус аллакай таъин шудааст
                } else if (last.dostavka === 1) {
                    statusText = "Мы везем ваш заказ! 🚀🚗";
                    statusType = "shipping";
                } else if (last.dostavka === 2) {
                    statusText = "Ваш заказ доставлен! Приятного аппетита! 🏠✅";
                    statusType = "ready"; ok = true;
                } else if (last.omoda) {
                    statusText = last.delivery_type === 'pickup' ? "Ваш заказ готов! Пожалуйста, заберите свое блюдо." : "Ваш заказ готов! Через несколько минут мы его доставим. 🚀";
                    statusType = "ready"; ok = true;
                } else if (last.qabyl) {
                    let timeMsg = "";
                    if (last.estimated_time) {
                        timeMsg = last.delivery_type === 'delivery' ? 
                            `<br><b>Ваш заказ будет готов и прислан через ${last.estimated_time} минут.</b>` : 
                            `<br><b>Ваш заказ будет готов примерно через ${last.estimated_time} минут.</b>`;
                    }
                    statusText = `Заказ <b>принят</b> поваром! 👨‍🍳${timeMsg}`;
                    statusType = "accepted";
                }

                if (statusType === "pending" || statusType === "accepted") {
                    statusText += oosPart;
                }

                // Сохтани калиди беназир: ID-и заказ + статус
                const statusKey = last.id + "_" + statusType;

                if (statusKey !== latestCustomerStatus) {
                    latestCustomerStatus = statusKey;
                    localStorage.setItem("tfc_last_notified_status", statusKey);
                    showLiveStatus(statusText, ok);
                }
            } catch (e) {}
        }

        document.getElementById("main-content").addEventListener("click", function (e) {
            const infoBtn = e.target.closest(".food-info-sign");
            const btn = e.target.closest(".order-btn");
            const card = e.target.closest(".product-card");

            if (infoBtn && card) {
                e.preventDefault();
                e.stopPropagation();
                // Remove any active show-order classes - NO animation for info button
                document.querySelectorAll('.product-card.show-order').forEach(c => c.classList.remove('show-order'));
                // Clear any pending animations
                card.classList.remove('show-order');
                openFoodInfoOverlay(card);
                return;
            }

            if (!card) {
                // Агар берун аз карточка клик шавад, тугмаҳоро пинҳон мекунем
                document.querySelectorAll('.product-card.show-order').forEach(c => c.classList.remove('show-order'));
                return;
            }

            // Агар ин карточка дар бахши Вакансияҳо бошад, ягон кор накун
            if (card.closest('#vakansii-section')) return;

            if (btn) {
                // Қадами 2: Клик ба тугмаи "ЗАКАЗАТЬ"
                e.preventDefault();
                e.stopPropagation();
                // Add card animation before opening order modal
                document.querySelectorAll('.product-card.show-order').forEach(c => c.classList.remove('show-order'));
                card.classList.add('show-order');
                openOrderModal(card);
            } else {
                // Қадами 1: Пайдо кардани тугма ва калон кардани сурат
                const wasActive = card.classList.contains('show-order');
                document.querySelectorAll('.product-card.show-order').forEach(c => c.classList.remove('show-order'));
                if (!wasActive) card.classList.add('show-order');
            }
        });

        document.getElementById("modal-qty").addEventListener("input", updateModalTotal);
        document.getElementById("order-modal-overlay").addEventListener("click", function (e) {
            if (e.target.id === "order-modal-overlay") closeOrderModal();
        });
        document.getElementById("cart-modal-overlay").addEventListener("click", function (e) {
            if (e.target.id === "cart-modal-overlay") closeCartModal();
        });
        document.getElementById("notif-clear-modal-overlay").addEventListener("click", function (e) {
            if (e.target.id === "notif-clear-modal-overlay") closeNotifClearModal();
        });
        document.getElementById("phone-order-modal-overlay").addEventListener("click", function (e) {
            if (e.target.id === "phone-order-modal-overlay") closePhoneOrderModal();
        });

        function startCustomerStatusPolling() {
            if (statusPollTimer) clearInterval(statusPollTimer);
            pollCustomerStatus();
            statusPollTimer = setInterval(pollCustomerStatus, 3000);
        }

        function toggleFullScreen(vidId) {
            const vid = document.getElementById(vidId);
            if (vid.requestFullscreen) {
                vid.requestFullscreen().then(() => {
                });
            } else if (vid.webkitRequestFullscreen) {
                vid.webkitRequestFullscreen(); // Барои iOS (Safari)
            } else if (vid.msRequestFullscreen) {
                vid.msRequestFullscreen();
            }
        }

        function stopAllVideos() {
            document.querySelectorAll('video').forEach(v => {
                v.pause();
                // Пайдо кардани оверлей барои ҳар як видео ва нишон додани он
                const container = v.closest('.relative');
                if (container) {
                    const overlay = container.querySelector('.play-overlay');
                    if (overlay) overlay.style.opacity = '1';
                }
            });
        }

        function togglePlay(vidId, container) {
            const vid = document.getElementById(vidId);
            const overlay = container.querySelector('.play-overlay');
            if (vid.paused) {
                stopAllVideos(); // Пеш аз оғоз ҳамаро меистем
                vid.muted = false; // Садоро фаъол мекунем
                vid.play();
                if (overlay) overlay.style.opacity = '0'; // Тугмаро пинҳон мекунем
            } else {
                vid.pause();
                if (overlay) overlay.style.opacity = '1'; // Тугмаро боз нишон медиҳем
            }
        }

    </script>
</body>
</html>
"""

@app.route('/admin')
def admin_page():
    return redirect("https://tfc-admin-panel.onrender.com/")

@app.route('/sw.js')
def serve_sw():
    return send_from_directory('static', 'sw.js')

@app.route('/manifest.json')
def serve_manifest():
    # Ин функсия файли manifest.json-ро аз папкаи асосии лоиҳа мехонад
    return send_from_directory('.', 'manifest.json')

@app.route("/api/reviews/add", methods=["POST"])
def api_reviews_add():
    name = request.form.get("name")
    text = request.form.get("text")
    stars = request.form.get("stars")
    image_url = ""

    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filename = f"rev_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            image_url = filename

    created = datetime.now().strftime("%d.%m.%Y %H:%M")
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("INSERT INTO reviews (name, text, stars, image_url, created) VALUES (?, ?, ?, ?, ?)", (name, text, stars, image_url, created))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/reviews/delete/<int:review_id>", methods=["POST"])
def api_reviews_delete(review_id):
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/push/subscribe", methods=["POST"])
def api_push_subscribe():
    data = request.get_json()
    customer_id = data.get("customer_id")
    sub_json = json.dumps(data.get("subscription"))
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO push_subscriptions (customer_id, subscription_json) VALUES (?, ?)", (customer_id, sub_json))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/customers/register", methods=["POST"])
def api_customers_register():
    data = request.get_json() or {}
    full_name = data.get("full_name")
    customer_id = data.get("customer_id")
    if not full_name or not customer_id:
        return jsonify({"ok": False, "error": "missing_data"}), 400
    
    created = datetime.now().strftime("%d.%m.%Y %H:%M")
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO customers (full_name, customer_id, created) VALUES (?, ?, ?)", 
                    (full_name, customer_id, created))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/auth/send-code", methods=["POST"])
def api_send_code():
    data = request.get_json() or {}
    phone = data.get("phone", "").strip()
    if not phone:
        return jsonify({"ok": False, "error": "no_phone"})
    
    # Генератсияи коди 4-рақамӣ
    code = str(random.randint(1000, 9999))
    verification_codes[phone] = code
    
    # --- ИН ҶО МАҲАЛЛИ ПАЙВАСТ КАРДАНИ SMS API АСТ ---
    # Масалан, агар шумо Eskiz ё Twilio дошта бошед:
    # send_real_sms(phone, f"Ваш код подтверждения TFC: {code}")
    
    # Ҳоло мо симулятсия мекунем (дар консоли сервер чоп мекунем)
    print(f"\n[SMS SERVICE] Коди тасдиқ барои {phone}: {code}\n")
    
    return jsonify({"ok": True, "debug_code": code})

def send_real_sms(phone, message):
    """
    Ин функсия барои фиристодани SMS-и ҳақиқӣ тавассути API мебошад.
    Шумо бояд дар ин ҷо коди сервиси худро илова кунед.
    """
    # import requests
    # requests.post("https://api.sms-provider.com/send", data={"to": phone, "msg": message})
    pass

@app.route("/api/auth/verify-code", methods=["POST"])
def api_verify_code():
    data = request.get_json() or {}
    phone = data.get("phone", "").strip()
    code = data.get("code", "").strip()
    
    if phone in verification_codes and verification_codes[phone] == code:
        # Код дуруст аст, онро аз хотира тоза мекунем
        del verification_codes[phone]
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "wrong_code"})

# API Routes (Moved from bilol.py to app.py)
@app.route("/api/orders/new", methods=["POST", "OPTIONS"])
def api_orders_new():
    if request.method == "OPTIONS":
        return ("", 204)

    data = request.get_json() or {}
    customer = data.get("customer", "No-name")
    customer_id = data.get("customer_id", "")
    food = data.get("food", "")
    price = data.get("price", "0")
    phone = data.get("phone", "")
    delivery_type = data.get("delivery_type", "pickup")
    tip = data.get("tip", "")
    delivery_latitude = data.get("delivery_latitude", "")
    delivery_longitude = data.get("delivery_longitude", "")
    delivery_address = data.get("delivery_address", "")
    payment_method = data.get("payment_method", "online")
    payment_phone = data.get("payment_phone", "")

    if not tip:
        tip = "Наличными 💵" if payment_method == "cash" else f"Картой 💳 ({payment_phone})"
    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor() # Ensure timeout is applied here
    # Insert bo hamai maydonho baroi durust namoyish shudan dar admin
    cur.execute("""
        INSERT INTO orders (customer, customer_id, food, price, phone, delivery_type, tip, delivery_latitude, delivery_longitude, delivery_address, payment_method, qabyl, omoda, dostavka, created)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?)
    """, (customer, customer_id, food, price, phone, delivery_type, tip, delivery_latitude, delivery_longitude, delivery_address, payment_method, created))
    order_id = cur.lastrowid
    
    # Сабти заказ дар таърихи доимӣ (Архив), то пас аз нест кардан боқӣ монад
    cur.execute(
        "INSERT INTO full_order_history (customer, customer_id, food, price, phone, delivery_type, tip, payment_method, created) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (customer, customer_id, food, price, phone, delivery_type, tip, payment_method, created)
    )

    # Сабти маблағ дар таърихи доимӣ
    try:
        p_clean = "".join(c for c in str(price).replace(',', '.') if c.isdigit() or c == '.')
        amount = float(p_clean) if p_clean else 0.0
        cur.execute("INSERT INTO revenue_history (amount, day, customer_id) VALUES (?, ?, ?)", (amount, datetime.now().strftime("%Y-%m-%d"), customer_id))
    except: pass

    conn.commit()
    conn.close()
    return jsonify({"ok": True, "order_id": order_id})

@app.route("/api/get-next-payment-phone")
def api_get_next_phone():
    phone = get_next_payment_phone_for_rotation()
    return jsonify({"ok": True, "phone": phone})

@app.route("/api/orders/since", methods=["GET"])
def api_orders_since():
    try:
        last_id = int(request.args.get("last_id", 0))
        conn = sqlite3.connect(DB_PATH, timeout=20); cur = conn.cursor()
        cur.execute("SELECT id, customer, customer_id, food, price, qabyl, omoda, created, phone, delivery_type, delivery_latitude, delivery_longitude, delivery_address, estimated_time, tip FROM orders WHERE id > ?", (last_id,))
        rows = cur.fetchall(); conn.close()
        return jsonify({"ok": True, "orders": [{"id": r[0], "customer": r[1], "customer_id": r[2], "food": r[3], "price": r[4], "qabyl": bool(r[5]), "omoda": bool(r[6]), "created": r[7], "phone": r[8], "delivery_type": r[9], "delivery_latitude": r[10] if len(r) > 10 else "", "delivery_longitude": r[11] if len(r) > 11 else "", "delivery_address": r[12] if len(r) > 12 else "", "estimated_time": r[13], "tip": r[14] if len(r) > 14 else ""} for r in rows]})
    except ValueError:
        return jsonify({"ok": False, "error": "Invalid last_id parameter"}), 400
    except sqlite3.Error as e:
        print(f"Database error in api_orders_since: {e}")
        return jsonify({"ok": False, "error": "Database error"}), 500

@app.route("/api/orders/update-status", methods=["POST"])
def api_orders_update_status():
    data = request.get_json() or {}
    order_id, field = data.get("id"), data.get("field")
    db_value = int(data.get("value", 0))
    estimated_time = data.get("estimated_time")
    conn = sqlite3.connect(DB_PATH, timeout=20); cur = conn.cursor()
    if field == 'qabyl' and estimated_time is not None:
        cur.execute(f"UPDATE orders SET {field} = ?, estimated_time = ? WHERE id = ?", (db_value, estimated_time, order_id))
    else:
        cur.execute(f"UPDATE orders SET {field} = ? WHERE id = ?", (db_value, order_id))
    conn.commit(); conn.close()

    # Push Notification Logic
    if db_value > 0:
        # (Инҷо коди фиристодани Push-ро мисли bilol.py илова кардан мумкин аст)
        pass
    return jsonify({"ok": True})

@app.route("/api/orders/customer-status", methods=["GET"])
def api_orders_customer_status():
    customer_id = request.args.get("customer_id", "")
    try:
        conn = sqlite3.connect(DB_PATH, timeout=20); cur = conn.cursor()
        cur.execute("SELECT id, food, qabyl, omoda, phone, delivery_type, dostavka, out_of_stock, refund, estimated_time, price FROM orders WHERE customer_id = ? ORDER BY id DESC LIMIT 1", (customer_id,))
        r = cur.fetchone(); conn.close()
        orders = [{"id": r[0], "food": r[1], "qabyl": bool(r[2]), "omoda": bool(r[3]), "phone": r[4], "delivery_type": r[5], "dostavka": int(r[6]), "out_of_stock": bool(r[7]), "refund": r[8] if r[8] is not None else 0, "estimated_time": r[9] if len(r) > 9 else 0, "price": r[10] if len(r) > 10 else "0"}] if r else []
        return jsonify({"ok": True, "orders": orders})
    except Exception as e:
        print(f"Status Error: {e}")
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/foods/list", methods=["GET"])
def api_foods_list():
    conn = sqlite3.connect(DB_PATH, timeout=20); cur = conn.cursor()
    cur.execute("SELECT id, name, price, category, image_url, description FROM foods"); rows = cur.fetchall(); conn.close()
    return jsonify({"ok": True, "foods": [{"id": r[0], "name": r[1], "price": r[2], "category": r[3], "image_url": r[4], "description": r[5]} for r in rows]})

def get_orders():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT food, price, qabyl, omoda FROM orders ORDER BY id DESC LIMIT 10")
            orders = [dict(row) for row in cur.fetchall()]
        return orders
    except Exception as e:
        print(f"Database error: {e}")
        return []

def get_all_foods():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT id, name, price, category, subcategory, image_url, description FROM foods")
            foods = [dict(row) for row in cur.fetchall()]
        
        # Group by category and detect media type
        cat_map = {}
        for f in foods:
            f['is_video'] = bool(f.get('image_url') and f['image_url'].lower().endswith(('.mp4', '.webm', '.mov', '.ogg')))
            cat_map.setdefault(f['category'], []).append(f)
        return cat_map
    except Exception as e:
        print(f"Database error in get_all_foods: {e}")
        return {}

def get_all_reviews():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT id, name, text, stars, image_url, created FROM reviews ORDER BY id DESC")
            return [dict(row) for row in cur.fetchall()]
    except: return []

def get_all_aktsii():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT title, price, description, image_url, created FROM aktsii ORDER BY id DESC")
            results = [dict(row) for row in cur.fetchall()]
            for r in results:
                r['is_video'] = bool(r.get('image_url') and r['image_url'].lower().endswith(('.mp4', '.webm', '.mov', '.ogg')))
            return results
    except: return []

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE, orders=get_orders(), categories=get_all_foods(), text_reviews=get_all_reviews(), aktsii=get_all_aktsii(), vapid_public_key=VAPID_PUBLIC_KEY)

@app.route('/food/<int:food_id>')
def food_detail(food_id):
    """Display detailed information for a single food item"""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=20)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, price, category, description, image_url, created
            FROM foods WHERE id = ?
        """, (food_id,))
        food = cur.fetchone()
        conn.close()
        
        if not food:
            return redirect('/')
        
        food = dict(food)
        food['image_path'] = f"/static/images/{food['image_url']}" if food['image_url'] else ""
        
        # Check if image is a video
        food['is_video'] = bool(food['image_url'] and food['image_url'].lower().endswith(('.mp4', '.webm', '.mov', '.ogg')))
        
        return render_template_string(FOOD_DETAIL_TEMPLATE, food=food)
    except Exception as e:
        print(f"Error loading food detail: {e}")
        return redirect('/')

def get_local_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()

if __name__ == '__main__':
    host = "0.0.0.0"
    port = 5000
    local_ip = get_local_ip()
    print(f"Запущено на этом ПК: http://127.0.0.1:{port}")
    print(f"------------------------------------------------------")
    print(f"АДРЕС ДЛЯ ТЕЛЕФОНА: http://{local_ip}:{port}")
    print(f"Если страница не открывается:")
    print(f"1. Временно отключите Windows Firewall.")
    print(f"2. Установите тип сети Wi-Fi в Windows на 'Private'.")
    print(f"--------------c:/Users/Anis/Desktop/qwer/app.py----------------------------------------")
    # Дар муҳити корӣ (Production) Gunicorn-ро истифода баред:
    # gunicorn -w 4 -b 0.0.0.0:5000 app:app
    app.run(debug=False, host="0.0.0.0", port=port)
