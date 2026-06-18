from flask import Flask, render_template_string, request, jsonify, send_from_directory
import sqlite3
import json
import os
import socket
import re
from datetime import datetime
from werkzeug.utils import secure_filename
from pywebpush import webpush, WebPushException

app = Flask(__name__)
UPLOAD_FOLDER = 'static/images'

# Калидҳо бояд бо app.py якхела бошанд
VAPID_PUBLIC_KEY = "BCX7B8_p9v7Z-S-l1M0W4Y1Z2X3C4V5B6N7M8L9K0J1I2H3G4F5E6D7C8B9A0S1D2F3G4H5J6K7L8"
VAPID_PRIVATE_KEY = "m1N2B3V4C5X6Z7A8S9D0F1G2H3J4K5L6m1N2B3V4C5X"
VAPID_CLAIMS = {"sub": "mailto:admin@tfc-kulob.tj"}

API_KEY = "TFC_SECRET_SECURE_KEY_2026"

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "tfc_admin.db"))


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
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
            dostavka INTEGER NOT NULL DEFAULT 0,
            qabyl INTEGER NOT NULL DEFAULT 0,
            omoda INTEGER NOT NULL DEFAULT 0,
            out_of_stock INTEGER NOT NULL DEFAULT 0,
            refund REAL NOT NULL DEFAULT 0,
            estimated_time INTEGER DEFAULT 0,
            created TEXT NOT NULL
        )
        """
    )
    cur.execute("PRAGMA table_info(orders)")
    cols = [r[1] for r in cur.fetchall()]
    if "customer_id" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN customer_id TEXT NOT NULL DEFAULT ''")
    if "qabyl" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN qabyl INTEGER NOT NULL DEFAULT 0")
    if "omoda" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN omoda INTEGER NOT NULL DEFAULT 0")
    if "phone" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN phone TEXT NOT NULL DEFAULT ''")
    if "delivery_type" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN delivery_type TEXT NOT NULL DEFAULT ''")
    if "dostavka" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN dostavka INTEGER NOT NULL DEFAULT 0")
    if "out_of_stock" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN out_of_stock INTEGER NOT NULL DEFAULT 0")
    if "tip" not in cols: cur.execute("ALTER TABLE orders ADD COLUMN tip TEXT NOT NULL DEFAULT ''")
    if "refund" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN refund REAL NOT NULL DEFAULT 0")
    if "delivery_latitude" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN delivery_latitude TEXT DEFAULT ''")
    if "delivery_longitude" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN delivery_longitude TEXT DEFAULT ''")
    if "delivery_address" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN delivery_address TEXT DEFAULT ''")
    if "estimated_time" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN estimated_time INTEGER DEFAULT 0")
    if "payment_method" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT DEFAULT 'online'")
    
    cur.execute("CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL, customer_id TEXT UNIQUE NOT NULL, created TEXT NOT NULL)")
    cur.execute("CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, text TEXT NOT NULL, stars INTEGER NOT NULL, image_url TEXT, created TEXT NOT NULL)")

    # Сохтани ҷадвали revenue_history барои графикҳо
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

    # Сохтани ҷадвали full_order_history барои таърихи пурра
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
            created TEXT NOT NULL
        )
        """
    )
    cur.execute("PRAGMA table_info(full_order_history)")
    foh_cols = [r[1] for r in cur.fetchall()]
    if "tip" not in foh_cols: cur.execute("ALTER TABLE full_order_history ADD COLUMN tip TEXT NOT NULL DEFAULT ''")
    if "payment_method" not in foh_cols:
        cur.execute("ALTER TABLE full_order_history ADD COLUMN payment_method TEXT DEFAULT 'online'")

    # Create settings table
    cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")

    # Create foods table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS foods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            price TEXT NOT NULL,
            category TEXT NOT NULL,
            image_url TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            created TEXT NOT NULL
        )
        """
    )
    cur.execute("PRAGMA table_info(foods)")
    cols = [r[1] for r in cur.fetchall()]
    if "image_url" not in cols:
        cur.execute("ALTER TABLE foods ADD COLUMN image_url TEXT NOT NULL DEFAULT ''")
    if "description" not in cols:
        cur.execute("ALTER TABLE foods ADD COLUMN description TEXT NOT NULL DEFAULT ''")
    if "subcategory" not in cols:
        cur.execute("ALTER TABLE foods ADD COLUMN subcategory TEXT NOT NULL DEFAULT ''")

    # Create aktsii table and keep price/image/description available
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS aktsii (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            price TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            image_url TEXT NOT NULL DEFAULT '',
            created TEXT NOT NULL
        )
        """
    )
    cur.execute("PRAGMA table_info(aktsii)")
    cols = [r[1] for r in cur.fetchall()]
    if "price" not in cols:
        cur.execute("ALTER TABLE aktsii ADD COLUMN price TEXT NOT NULL DEFAULT ''")
    if "description" not in cols:
        cur.execute("ALTER TABLE aktsii ADD COLUMN description TEXT NOT NULL DEFAULT ''")
    if "image_url" not in cols:
        cur.execute("ALTER TABLE aktsii ADD COLUMN image_url TEXT NOT NULL DEFAULT ''")

    # Sync foods list (Force Update)
    foods_data = [
        # НОМ, НАРХ, КАТЕГОРИЯ, ЗЕРКАТЕГОРИЯ, СУРАТ, ТАВСИФ, ВАҚТ
        # ПАСТА (Меню)
        ("ПАСТА БОЛОНЕЗА", "31", "Меню", "Паста", "b1.png", "### ПАСТА БОЛОНЕЗА\n\n- **Состав:** Фарш, макарон соус, томатный соус, сыр пармезан.\n\n**Время приготовления:** 10–15 минут.\n\n**Цена:** 31с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПАСТА ФИТУЧИНИ", "35", "Меню", "Паста", "b2.png", "### ПАСТА ФИТУЧИНИ\n\n- **Состав:** Курица, грибы, макарон, сливки, сыр пармезан.\n\n**Время приготовления:** 10–15 минут.\n\n**Цена:** 35с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПАСТА ПЕНЕ", "32", "Меню", "Паста", "b3.png", "### ПАСТА ПЕНЕ\n\n- **Состав:** Говядина, лапша, сливки, томат.\n\n**Время приготовления:** 10–15 минут.\n\n**Цена:** 32с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПАСТА СОБА", "23", "Меню", "Паста", "b4.png", "### ПАСТА СОБА\n\n- **Состав:** Спагетти, лук, чеснок, кабачки, болгарский перец.\n\n**Время приготовления:** 10–15 минут.\n\n**Цена:** 23с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ГНЁЗДА С ГОВЯДИНОЙ", "27", "Меню", "Паста", "b5.png", "### ГНЁЗДА С ГОВЯДИНОЙ\n\n- **Состав:** Говядина, лапша, микс салат, помидор, томатный соус.\n\n**Время приготовления:** 10–15 минут.\n\n**Цена:** 27с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        
        # САЛАТҲО (Меню)
        ("САЛАТ ТАЙСКИЙ", "34", "Меню", "Салаты", "b6.png", "### САЛАТ ТАЙСКИЙ\n\n- **Состав:** Болгарский перец, лук репчатый, говядина, баклажан, помидор, огурцы.\n\n**Время приготовления:** 10–15 минут.\n\n**Цена:** 34с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("САЛАТ TFC", "35", "Меню", "Салаты", "b7.png", "### САЛАТ TFC\n\n- **Состав:** Курица, панировка, помидор, соус TFC, щавель, салатный лист.\n\n**Время приготовления:** 10–15 минут.\n\n**Цена:** 35с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ХРУСТЯЩИЙ БАКЛАЖАН", "17", "Меню", "Салаты", "b8.png", "### ХРУСТЯЩИЙ БАКЛАЖАН\n\n- **Состав:** Баклажан, кинза, помидор, сладкий чили соус.\n\n**Время приготовления:** 10–15 минут.\n\n**Цена:** 17с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("САЛАТ ЦЕЗАРЬ", "25", "Меню", "Салаты", "b9.png", "### САЛАТ ЦЕЗАРЬ\n\n- **Состав:** Курица, пекинская капуста, салатный лист, соус цезарь, помидор, сыр пармезан, сухари.\n\n**Время приготовления:** 10–15 минут.\n\n**Цена:** 25с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("САЛАТ ЗЕЛЁНАЯ ЛУЖАЙКА", "15", "Меню", "Салаты", "b10.png", "### САЛАТ ЗЕЛЁНАЯ ЛУЖАЙКА\n\n- **Состав:** Салатный лист, щавель, лук зелёный, лимон, зелёный горошек.\n\n**Время приготовления:** 10–15 минут.\n\n**Цена:** 15с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ГРЕЧЕСКИЙ САЛАТ", "34", "Меню", "Салаты", "b11.png", "### ГРЕЧЕСКИЙ САЛАТ\n\n- **Состав:** Помидор, огурец, болгарский перец, оливки, сыр фетакса, салатный лист.\n\n**Время приготовления:** 10–15 минут.\n\n**Цена:** 34с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),

        # ШӮРБОҲО (Меню)
        ("СУП МЕРДЖИМЕК", "15", "Меню", "Супы", "b12.png", "### СУП МЕРДЖИМЕК\n\n- **Состав:** Чечевица, овощи, сухари, лимон.\n\n**Цена:** 15с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("БОРЩ", "25", "Меню", "Супы", "b13.png", "### БОРЩ\n\n- **Состав:** Капуста, овощи, свёкла, сметана, зелень, мясо.\n\n**Цена:** 25с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ГРИБНОЙ СУП", "26", "Меню", "Супы", "b14.png", "### ГРИБНОЙ СУП\n\n- **Состав:** Лук, грибы, сливки, картошка.\n\n**Цена:** 26с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЛАГМАН", "21", "Меню", "Супы", "b15.png", "### ЛАГМАН\n\n- **Состав:** Лапша, овощи, помидор, говядина, горох.\n\n**Цена:** 21с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУП TFC", "28", "Меню", "Супы", "b16.png", "### СУП TFC\n\n- **Состав:** Фрикадельки, овощи, яйцо перепелиное, щавель.\n\n**Цена:** 28с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЧАХОХБИЛИ", "26", "Меню", "Супы", "b17.png", "### ЧАХОХБИЛИ\n\n- **Состав:** Курица, томатный соус, овощи.\n\n**Цена:** 26с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),

        # ҒАЗОҲОИ ГАРМ (Меню)
        ("БИФШТЕКС", "25", "Меню", "Горячие блюда", "b18.png", "### БИФШТЕКС\n\n- **Состав:** Котлета, картофельное пюре, яйцо.\n\n**Время приготовления:** 10–15 минут.\n\n**Цена:** 25с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КОТЛЕТА ПО-КИЕВСКИ", "28", "Меню", "Горячие блюда", "b19.png", "### КОТЛЕТА ПО-КИЕВСКИ\n\n- **Состав:** Филе, сливочное масло, яйцо.\n\n**Время приготовления:** 10–15 минут.\n\n**Цена:** 28с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ФИСТАШКИ БАРАНИНА", "45", "Меню", "Горячие блюда", "", "### ФИСТАШКИ БАРАНИНА\n\n**Время приготовления:** 10–15 минут.\n\n**Цена:** 45с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КАЗАН КАБОБ", "40", "Меню", "Горячие блюда", "b21.jpg", "### КАЗАН КАБОБ\n\n**Время приготовления:** 10–15 минут.\n\n**Цена:** 40с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЖАРОВНЯ ТФС (БАРАНИНА/ГОВЯДИНА)", "50", "Меню", "Горячие блюда", "b22.jpg", "### ЖАРОВНЯ TFC (БАРАНИНА/ГОВЯДИНА)\n\n**Время приготовления:** 10–15 минут.\n\n**Цена:** 50с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СТЕЙК ИЗ ФОРЕЛИ", "25", "Меню", "Горячие блюда", "b23.jpg", "### СТЕЙК ИЗ ФОРЕЛИ\n\n**Время приготовления:** 20–25 минут.\n\n**Цена:** 100гр — 25с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТАБАКА", "58", "Меню", "Горячие блюда", "b24.jpg", "### ТАБАКА\n\n**Время приготовления:** 20–25 минут.\n\n**Цена:** 58с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КОРЕЙКА БАРАНИНА", "50", "Меню", "Горячие блюда", "b25.jpg", "### КОРЕЙКА БАРАНИНА\n\n**Время приготовления:** 20–25 минут.\n\n**Цена:** 50с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СТЕЙК ИЗ ГОВЯДИНЫ", "58", "Меню", "Горячие блюда", "b26.jpg", "### СТЕЙК ИЗ ГОВЯДИНЫ\n\n**Время приготовления:** 20–25 минут.\n\n**Цена:** 58с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),

        # ДЕСЕРТҲО (Меню)
        ("ЧИЗКЕЙК", "12", "Меню", "Десерты", "b27.jpg", "### ЧИЗКЕЙК\n\n**Цена:** 100гр — 12с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("РАФАЭЛЛО", "12", "Меню", "Десерты", "b28.jpg", "### РАФАЭЛЛО\n\n**Цена:** 100гр — 12с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("НАПОЛЕОН", "10", "Меню", "Десерты", "b29.jpg", "### НАПОЛЕОН\n\n**Цена:** 100гр — 10с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТИРАМИСУ", "12", "Меню", "Десерты", "b30.jpg", "### ТИРАМИСУ\n\n**Цена:** 100гр — 12с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ФРУКТОВАЯ НАРЕЗКА (Большая)", "75", "Меню", "Десерты", "b31.jpg", "### ФРУКТОВАЯ НАРЕЗКА (Большая)\n\n**Цена:** 75с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ФРУКТОВАЯ НАРЕЗКА (Средняя)", "50", "Меню", "Десерты", "b32.jpg", "### ФРУКТОВАЯ НАРЕЗКА (Средняя)\n\n**Цена:** 50с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КЕШЬЮ", "45", "Меню", "Десерты", "b33.jpg", "### КЕШЬЮ\n\n**Цена:** 150гр — 45с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ФИСТАШКИ", "45", "Меню", "Десерты", "b34.jpg", "### ФИСТАШКИ\n\n**Цена:** 150гр — 45с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),

        # НӮШОКИҲО (Меню)
        ("АМЕРИКАНО", "15", "Меню", "Напитки", "b35.jpg", "### АМЕРИКАНО\n\n**Цена:** 15с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КАПУЧИНO", "18", "Меню", "Напитки", "b36.jpg", "### КАПУЧИНО\n\n**Цена:** 18с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЛАТТЕ", "18", "Меню", "Напитки", "b37.jpg", "### ЛАТТЕ\n\n**Цена:** 18с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЭСПРЕССО", "12", "Меню", "Напитки", "b38.jpg", "### ЭСПРЕССО\n\n**Цена:** 12с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЧАЙ (Зелёный / черный)", "5", "Меню", "Напитки", "b39.jpg", "### ЧАЙ (Зелёный / чёрный)\n\n**Цена:** 5с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЧАЙ (С лимоном)", "10", "Меню", "Напитки", "", "### ЧАЙ (С лимоном)\n\n**Цена:** 10с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЧАЙ (С лимоном и имбирем)", "15", "Меню", "Напитки", "", "### ЧАЙ (С лимоном и имбирем)\n\n**Цена:** 15с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЧАЙ ФРУКТОВЫЙ", "20", "Меню", "Напитки", "", "### ЧАЙ ФРУКТОВЫЙ\n\n- **Состав:** Клубника, малина, смородина, гвоздика.\n\n**Цена:** 20с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЧАЙ ФРУКТОВАЯ ЭКЗОТИКА", "24", "Меню", "Напитки", "", "### ЧАЙ ФРУКТОВАЯ ЭКЗОТИКА\n\n- **Состав:** Киви, апельсин, ананас.\n\n**Цена:** 24с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),

        # ПИЦЦА
        ("ПИЦЦА ГОВЯДИНА", "65/87", "Пицца", "Пицца", "a1.png", "### ПИЦЦА ГОВЯДИНА\n\n- **Состав:** Тесто, томатный соус, помидор, грибы, болгарский перец, маслины, сыр, котлета.\n\n**Цена:** L — 65с / XL — 87с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПИЦЦА АССОРТИ", "68/88", "Пицца", "Пицца", "a2.png", "### ПИЦЦА АССОРТИ\n\n- **Состав:** Тесто, соус, помидор, грибы, болгарский перец, сосиска, колбаса, курица, сыр, котлета.\n\n**Цена:** L — 68с / XL — 88с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПИЦЦА ЧЕТЫРЕ СЫРА", "61/78", "Пицца", "Пицца", "a3.png", "### ПИЦЦА ЧЕТЫРЕ СЫРА\n\n- **Состав:** Тесто, сливочный соус, сыр моцарелла, сыр чеддер, сыр голландский.\n\n**Цена:** L — 61с / XL — 78с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПИЦЦА ЧЕРНАЯ МЕТКА", "62/79", "Пицца", "Пицца", "a4.png", "### ПИЦЦА ЧЕРНАЯ МЕТКА\n\n- **Состав:** Тесто, сливочный соус, помидор, грибы, колбаса, курица, сыр.\n\n**Цена:** L — 62с / XL — 79с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПИЦЦА ТОНИ МОНТАНА", "73/90", "Пицца", "Пицца", "a5.png", "### ПИЦЦА ТОНИ МОНТАНА\n\n- **Состав:** Тесто, томатный соус, грибы, болгарский перец, охотничьи сосиски, сыр, котлета.\n\n**Цена:** L — 73с / XL — 90с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПИЦЦА TFC", "68/90", "Пицца", "Пицца", "a6.png", "### ПИЦЦА TFC\n\n- **Состав:** Тесто, томатный соус, помидор, перец халапеньо, курица, сыр, котлета.\n\n**Цена:** L — 68с / XL — 90с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПИЦЦА ПЕППЕРОНИ", "63/75", "Пицца", "Пицца", "a7.png", "### ПИЦЦА ПЕППЕРОНИ\n\n- **Состав:** Тесто, томатный соус, колбаса, сыр.\n\n**Цена:** L — 63с / XL — 75с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПИЦЦА КУРИНАЯ", "65/84", "Пицца", "Пицца", "a8.png", "### ПИЦЦА КУРИНАЯ\n\n- **Состав:** Тесто, соус сливочный, помидор, болгарский перец, курица, сыр.\n\n**Цена:** L — 65с / XL — 84с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ХАЧАПУРИ ПО-АДЖАРСКИ", "35", "Пицца", "Хачапури", "a9.png", "### ХАЧАПУРИ ПО-АДЖАРСКИ\n\n- **Состав:** Тесто, сыр, яйцо.\n\n**Цена:** 35с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ХАЧАПУРИ МЕГРЕЛЬСКИЙ", "40", "Пицца", "Хачапури", "a10.png", "### ХАЧАПУРИ МЕГРЕЛЬСКИЙ\n\n- **Состав:** Тесто, сыр, яйцо.\n\n**Цена:** 40с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        
        # СУШИ
        ("МИНИ РОЛЛЫ С СЫРОМ", "25", "Суши", "Роллы", "a.png", "### МИНИ РОЛЛЫ С СЫРОМ\n\n- **Состав:** Рис, сыр кримета, икра красная.\n\n**Цена:** 25с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СИЯКИ МАКИ", "24", "Суши", "Роллы", "b.png", "### СИЯКИ МАКИ\n\n- **Состав:** Рис, лосось.\n\n**Цена:** 24с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МИНИ РОЛЛЫ ФИЛАДЕЛЬФИЯ", "26", "Суши", "Роллы", "c.png", "### МИНИ РОЛЛЫ ФИЛАДЕЛЬФИЯ\n\n- **Состав:** Рис, лосось, сыр.\n\n**Цена:** 26с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("УНАГИ КАПА МАКИ", "27", "Суши", "Роллы", "d.png", "### УНАГИ КАПА МАКИ\n\n- **Состав:** Рис, огурец, угорь, унаги.\n\n**Цена:** 27с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЗАПЕЧЕНЫЙ САМУРАЙ", "51", "Суши", "Роллы", "e.png", "### ЗАПЕЧЕНЫЙ САМУРАЙ\n\n- **Состав:** Рис, сыр кримета, огурцы, лосось, кунжут, соус сливочный.\n\n**Цена:** 51с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЗАПЕЧЕНЫЙ УНАГИ", "61", "Суши", "Роллы", "f.png", "### ЗАПЕЧЕНЫЙ УНАГИ\n\n- **Состав:** Рис, сыр кримета, огурцы, икра масаго, угорь, соус унаги.\n\n**Цена:** 61с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЗАПЕЧЕННАЯ КАЛИФОРНИЯ С КРЕВЕТКОЙ", "59", "Суши", "Роллы", "g.png", "### ЗАПЕЧЕННАЯ КАЛИФОРНИЯ С КРЕВЕТКОЙ\n\n- **Состав:** Рис, сыр кримета, креветка, огурцы, икра табако, соус унаги.\n\n**Цена:** 59с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЗАПЕЧЕНЫЙ СЯКЕ", "54", "Суши", "Роллы", "h.png", "### ЗАПЕЧЕНЫЙ СЯКЕ\n\n- **Состав:** Рис, соус унаги, сыр кримета, огурец, соус теря, лосось.\n\n**Цена:** 54с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТЕМПУРА КРАЙЗИ", "44", "Суши", "Роллы", "i.png", "### ТЕМПУРА КРАЙЗИ\n\n- **Состав:** Рис, сыр кримета, лосось свежий, помидор.\n\n**Цена:** 44с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТЕМПУРА СНЕЖНЫЙ КРАБ", "45", "Суши", "Роллы", "j.png", "### ТЕМПУРА СНЕЖНЫЙ КРАБ\n\n- **Состав:** Рис, снежный краб, соус спайс, огурец свежий, панировочные сухари.\n\n**Цена:** 45с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ОВОЩНАЯ ТЕМПУРА", "35", "Суши", "Роллы", "k.png", "### ОВОЩНАЯ ТЕМПУРА\n\n- **Состав:** Рис, болгарский перец, огурец, помидор, панировочные сухари.\n\n**Цена:** 35с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТЕМПУРА ЦЕЗАРЬ", "38", "Суши", "Роллы", "l.png", "### ТЕМПУРА ЦЕЗАРЬ\n\n- **Состав:** Рис, курица, лист салата, помидор, панировочные сухари.\n\n**Цена:** 38с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("РОЛЛ КАНАДА TFC", "60", "Суши", "Роллы", "m.png", "### РОЛЛ КАНАДА TFC\n\n- **Состав:** Рис, сыр кримета, огурцы, угорь, унаги соус, кунжут.\n\n**Цена:** 60с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("РОЛЛ САНСИ", "58", "Суши", "Роллы", "n.png", "### РОЛЛ САНСИ\n\n- **Состав:** Рис, сыр кримета, лосось, кунжут, икра, огурцы.\n\n**Цена:** 58с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КАЛИФОРНИЯ СНЕЖНЫЙ КРАБ", "51", "Суши", "Роллы", "o.png", "### КАЛИФОРНИЯ СНЕЖНЫЙ КРАБ\n\n- **Состав:** Рис, икра, краб, огурцы, сыр кримета.\n\n**Цена:** 51с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("РОЛЛ ФИЛАДЕЛЬФИЯ", "58", "Суши", "Роллы", "p.png", "### РОЛЛ ФИЛАДЕЛЬФИЯ\n\n- **Состав:** Рис, сыр сливочный, лосось, огурцы.\n\n**Цена:** 58с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУШИ С КРЕВЕТКОЙ", "13", "Суши", "Суши", "q.png", "### СУШИ С КРЕВЕТКОЙ\n\n- **Состав:** Рис, креветки, соус яки.\n\n**Цена:** 13с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУШИ С УГРЕМ", "13", "Суши", "Суши", "r.png", "### СУШИ С УГРЕМ\n\n- **Состав:** Рис, угорь, соус унаги.\n\n**Цена:** 13с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУШИ С ЛОСОСЬЮ", "17", "Суши", "Суши", "s.png", "### СУШИ С ЛОСОСЬЮ\n\n- **Состав:** Рис, лосось, соус яки.\n\n**Цена:** 17с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУШИ ЗАПЕЧЕНЫЙ ЛОСОСЬ", "17", "Суши", "Суши", "t.png", "### СУШИ ЗАПЕЧЕНЫЙ ЛОСОСЬ\n\n- **Состав:** Рис, лосось, соус яки, соус унаги.\n\n**Цена:** 17с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУШИ ОСТРЫЕ С ТУНЦОМ", "12", "Суши", "Суши", "u.png", "### СУШИ ОСТРЫЕ С ТУНЦОМ\n\n- **Состав:** Рис, острый соус, тунец, соус унаги.\n\n**Цена:** 12с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СЕТ ТЕМПУРА", "135", "Суши", "Роллы", "w.png", "### СЕТ ТЕМПУРА\n\n- **Состав:** Темпура крайзи, Овощная темпура, Калифорния Снежный краб, Мини ролл с сыром.\n\n**Цена:** 135с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СЕТ КАНАДА TFC", "160", "Суши", "Роллы", "x.png", "### СЕТ КАНАДА TFC\n\n- **Состав:** Ролл Канада TFC, Санси, Калифорния Снежный краб, Суши с креветкой, Суши угрем, Ролл сияки маки, Унаги капа маки.\n\n**Цена:** 160с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СЕТ ЗАПЕЧЁННЫЙ", "146", "Суши", "Роллы", "y.png", "### СЕТ ЗАПЕЧЁННЫЙ\n\n- **Состав:** Запечённый унаги, Запечённый сияке, Запечённый самурай.\n\n**Цена:** 146с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        
        # ФАСТ ФУД
        ("НОН-ДОГ", "5/7", "Фастфуд", "Хот-доги", "1.png", "### НОН-ДОГ\n\n- **Состав:** Лепешка, сосиска, помидор, огурцы.\n\n**Цена:** L — 5с / XL — 7с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("БУЛОЧКА", "6/8", "Фастфуд", "Хот-доги", "2.png", "### БУЛОЧКА\n\n- **Состав:** Булочка, сосиска, помидор, огурцы.\n\n**Цена:** L — 6с / XL — 8с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("М-ДОГ", "10", "Фастфуд", "Хот-доги", "3.png", "### М-ДОГ\n\n- **Состав:** Булочка, сосиска, помидор, огурцы.\n\n**Цена:** 10с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("TFC-ДОГ", "18/30", "Фастфуд", "Хот-доги", "4.png", "### TFC-ДОГ\n\n- **Состав:** Булочка, фирменный соус, котлета, курица, помидор, огурцы, соус бургер, салатный лист.\n\n**Цена:** L — 18с / XL — 30с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЧИКЕН-ДОГ", "12/24", "Фастфуд", "Хот-доги", "5.png", "### ЧИКЕН-ДОГ\n\n- **Состав:** Булочка, майонез, сосиска, курица, помидор, огурцы, салатный лист.\n\n**Цена:** L — 12с / XL — 24с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("НАЧО-ДОГ", "14/26", "Фастфуд", "Хот-доги", "6.png", "### НАЧО-ДОГ\n\n- **Состав:** Булочка, сосиска, фирменный соус, огурцы, салатный лист, сырный соус, чипсы.\n\n**Цена:** L — 14с / XL — 26с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЧИКЕНЧИЗ-ДОГ", "16/28", "Фастфуд", "Хот-доги", "7.png", "### ЧИКЕНЧИЗ-ДОГ\n\n- **Состав:** Булочка, сыр чеддер, майонез, сосиска, курица, помидор, огурцы, салатный лист, кетчуп.\n\n**Цена:** L — 16с / XL — 28с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ШЕФ-ДОГ", "17/29", "Фастфуд", "Хот-доги", "8.png", "### ШЕФ-ДОГ\n\n- **Состав:** Булочка, майонез, сосиска, курица, помидор, огурцы, салатный лист, кетчуп, зелёный горошек.\n\n**Цена:** L — 17с / XL — 29с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("АМЕРИКАНО-ДОГ", "16/25", "Фастфуд", "Хот-доги", "9.png", "### АМЕРИКАНО-ДОГ\n\n- **Состав:** Булочка, кетчуп, чили соус, сосиска, кукуруза, колбаса.\n\n**Цена:** L — 16с / XL — 25с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ИТАЛИ-ДОГ", "12/20", "Фастфуд", "Хот-доги", "10.png", "### ИТАЛИ-ДОГ\n\n- **Состав:** Булочка, сырный соус, сыр чеддер, сосиска, помидор.\n\n**Цена:** L — 12с / XL — 20с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("БИФ-ДОГ", "41", "Фастфуд", "Хот-доги", "11.png", "### БИФ-ДОГ\n\n- **Состав:** Булочка, котлета, фирменный соус, сыр чеддер, помидор, салатный лист, соус бургер.\n\n**Цена:** 41с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КЛАССИК БУРГЕР", "23", "Фастфуд", "Бургеры", "12.png", "### КЛАССИК БУРГЕР\n\n- **Состав:** Булочка, соус бургер, салатный лист, помидор, консервированные огурцы, котлета.\n\n**Цена:** 23с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КЛАССИК ЧИЗБУРГЕР", "27", "Фастфуд", "Бургеры", "13.png", "### КЛАССИК ЧИЗБУРГЕР\n\n- **Состав:** Булочка, соус бургер, салатный лист, помидор, консервированные огурцы, котлета, сыр чеддер.\n\n**Цена:** 27с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ДАБЛ ЧИЗБУРГЕР", "43", "Фастфуд", "Бургеры", "14.png", "### ДАБЛ ЧИЗБУРГЕР\n\n- **Состав:** Булочка, соус бургер, салатный лист, помидор, консервированные огурцы, котлета, сыр чеддер.\n\n**Цена:** 43с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ДАБЛ БУРГЕР", "37", "Фастфуд", "Бургеры", "15.png", "### ДАБЛ БУРГЕР\n\n- **Состав:** Булочка, соус бургер, салатный лист, помидор, консервированные огурцы, котлета.\n\n**Цена:** 37с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("TFC БУРГЕР", "48", "Фастфуд", "Бургеры", "16.png", "### TFC БУРГЕР\n\n- **Состав:** Булочка, соус бургер, салатный лист, помидор, огурцы свежие, котлета, курица, сыр чеддер.\n\n**Цена:** 48с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ШЕФ БУРГЕР", "51", "Фастфуд", "Бургеры", "17.png", "### ШЕФ БУРГЕР\n\n- **Состав:** Булочка, соус бургер, салатный лист, помидор, консервированные огурцы, котлета, сыр чеддер.\n\n**Цена:** 51с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТОРТИЛЬЯ С КУРИЦЕЙ И С СЫРОМ", "23", "Фастфуд", "Тортильи", "18.png", "### ТОРТИЛЬЯ С КУРИЦЕЙ И С СЫРОМ\n\n- **Состав:** Лаваш, фирменный соус, сыр чеддер, салатный лист, помидор, огурцы, картошка, курица, кетчуп.\n\n**Цена:** 23с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТОРТИЛЬЯ С КУРИЦЕЙ", "15", "Фастфуд", "Тортильи", "19.png", "### ТОРТИЛЬЯ С КУРИЦЕЙ\n\n- **Состав:** Лаваш, фирменный соус, салатный лист, помидор, огурцы, картошка, курица, кетчуп.\n\n**Цена:** 15с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТОРТИЛЬЯ МИКС", "26", "Фастфуд", "Тортильи", "20.png", "### ТОРТИЛЬЯ МИКС\n\n- **Состав:** Лаваш, фирменный соус, салатный лист, помидор, консервированные огурцы, охотничья сосиска, курица.\n\n**Цена:** 26с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТОРТИЛЬЯ TFC", "40", "Фастфуд", "Тортильи", "21.png", "### ТОРТИЛЬЯ TFC\n\n- **Состав:** Лаваш, сыр моцарелла, фирменный соус, салатный лист, помидор, огурцы, котлета, чипсы, майонез, кетчуп.\n\n**Цена:** 40с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТОРТИЛЬЯ ГОВЯДИНА", "32", "Фастфуд", "Тортильи", "22.png", "### ТОРТИЛЬЯ ГОВЯДИНА\n\n- **Состав:** Лаваш, фирменный соус, помидор, огурцы, котлета, говядина, кетчуп, майонез, сырный соус.\n\n**Цена:** 32с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТОРТИЛЬЯ В ТЕМПУРАХ", "28", "Фастфуд", "Тортильи", "23.png", "### ТОРТИЛЬЯ В ТЕМПУРАХ\n\n- **Состав:** Лаваш, фирменный соус, сыр чеддер, салатный лист, помидор, огурцы, курица, кетчуп, панировка.\n\n**Цена:** 28с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СЭНДВИЧ SIMPLE", "19", "Фастфуд", "Сэндвичи", "24.png", "### СЭНДВИЧ SIMPLE\n\n- **Состав:** Булочка, майонез, салатный лист, курица.\n\n**Цена:** 19с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СЭНДВИЧ С СЫРОМ", "23", "Фастфуд", "Сэндвичи", "25.png", "### СЭНДВИЧ С СЫРОМ\n\n- **Состав:** Булочка, майонез, салатный лист, курица, сыр чеддер.\n\n**Цена:** 23с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КУРИНЫЙ ПАНИНИ", "26", "Фастфуд", "Сэндвичи", "26.png", "### КУРИНЫЙ ПАНИНИ\n\n- **Состав:** Булочка, майонез, свежие огурцы, курица, салатный лист, соус сырный.\n\n**Цена:** 26с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ГОВЯЖИЙ ПАНИНИ", "43", "Фастфуд", "Сэндвичи", "27.png", "### ГОВЯЖИЙ ПАНИНИ\n\n- **Состав:** Булочка, майонез, котлета, свежие огурцы, помидор, кетчуп, салатный лист.\n\n**Цена:** 43с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КАРТОШКА ФРИ", "12/17", "Фастфуд", "Гарниры", "28.png", "### КАРТОШКА ФРИ\n\n**Цена:** 100гр — 12с / 150гр — 17с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КАРТОФЕЛЬ ПО-ДЕРЕВЕНСКИ", "13/18", "Фастфуд", "Гарниры", "29.png", "### КАРТОФЕЛЬ ПО-ДЕРЕВЕНСКИ\n\n**Цена:** 100гр — 13с / 150гр — 18с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КАРТОФЕЛЬНЫЕ ШАРИКИ", "14/19", "Фастфуд", "Гарниры", "30.png", "### КАРТОФЕЛЬНЫЕ ШАРИКИ\n\n**Цена:** 100гр — 14с / 150гр — 19с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("НАГГЕТСЫ", "17/27", "Фастфуд", "Гарниры", "31.png", "### НАГГЕТСЫ\n\n**Цена:** 6шт — 17с / 10шт — 27с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ОСТРЫЕ КРЫЛЫШКИ", "35/45", "Фастфуд", "Гарниры", "32.png", "### ОСТРЫЕ КРЫЛЫШКИ\n\n**Цена:** 6шт — 35с / 10шт — 45с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СЛАДКИЕ КРЫЛЫШКИ", "36/46", "Фастфуд", "Гарниры", "33.png", "### СЛАДКИЕ КРЫЛЫШКИ\n\n**Цена:** 6шт — 36с / 10шт — 46с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КУРИНЫЕ НОЖКИ", "69/109", "Фастфуд", "Гарниры", "34.png", "### КУРИНЫЕ НОЖКИ\n\n**Цена:** 6шт — 69с / 10шт — 109с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СЫРНЫЕ ПАЛОЧКИ", "28", "Фастфуд", "Гарниры", "35.png", "### СЫРНЫЕ ПАЛОЧКИ\n\n**Цена:** 28с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("БАСКЕТ", "130", "Фастфуд", "Гарниры", "36.png", "### БАСКЕТ\n\n- **Состав:** 1п фри, 10шт наггетси, 6шт крылышки острый, 6шт Ножки острый.\n\n**Цена:** 130с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),

        # ЛЕТНЕЕ МЕНЮ (Летнее меню)
        ("СМУЗИ БАНАН + КИВИ", "26", "Летнее меню", "Смузи", "d1.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СМУЗИ БАНАН + АБРИКОС", "23", "Летнее меню", "Смузи", "d2.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СМУЗИ БАНАН + МАЛИНА", "26", "Летнее меню", "Смузи", "d3.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СМУЗИ БАНАН + ЯБЛОКО", "23", "Летнее меню", "Смузи", "d4.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СМУЗИ БАНАН + ДЫНЯ", "21", "Летнее меню", "Смузи", "d5.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СМУЗИ БАНАН + ВИШНЯ", "21", "Летнее меню", "Смузи", "d6.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ОКРОШКА (350МЛ)", "16", "Летнее меню", "Холодок", "d7.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("АЙРАН (500МЛ)", "6", "Летнее меню", "Холодок", "d8.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        # МОХИТО (Летнее меню)
        ("МОХИТО LIME", "19", "Летнее меню", "Мохито", "e1.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МОХИТО CLASSIC", "16", "Летнее меню", "Мохито", "e2.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МОХИТО FRUITE", "19", "Летнее меню", "Мохито", "e3.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МОХИТО PINEAPPLE", "19", "Летнее меню", "Мохито", "e4.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МОХИТО CHERRY", "16", "Летнее меню", "Мохито", "e5.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МОХИТО BLUE LAGOON", "19", "Летнее меню", "Мохито", "e6.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МОХИТО БАНАНОВЫЙ", "16", "Летнее меню", "Мохито", "e7.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МОХИТО KIWI", "19", "Летнее меню", "Мохито", "e8.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МОХИТО APPLE", "16", "Летнее меню", "Мохито", "e9.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    ]

    # Ин қисм маълумоти рӯйхатро ба базаи маълумот менависад
    for f in foods_data:
        cur.execute("""
            INSERT OR REPLACE INTO foods (name, price, category, subcategory, image_url, description, created)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, f)

    conn.commit()
    conn.close()


init_db()

HTML = r"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="screen-orientation" content="landscape">
    <meta name="x5-orientation" content="landscape">
    <meta name="orientation" content="landscape">
    <link rel="icon" type="image/jpeg" href="{{ url_for('static', filename='images/TFC.jpg') }}">
    <link rel="apple-touch-icon" href="{{ url_for('static', filename='images/TFC.jpg') }}">
    <link rel="manifest" href="/admin_manifest.json">
    <title>Admin Panel | TFC</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,600&display=swap');
        :root {
            --tfc: #e4002b;
            --tfc-dark: #b80024;
            --bg-dark: #0f0f0f;
            --bg-darker: #1a1a1a;
            --card-dark: #262626;
            --border-dark: #404040;
        }
        body { 
            font-family: 'DM Sans', system-ui, sans-serif; 
            background: var(--bg-dark);
            color: #e0e0e0;
        }
        .header-bar {
            background: linear-gradient(135deg, #1a0a0c 0%, #3d0d14 40%, #c8102e 100%);
            box-shadow: 0 12px 40px rgba(196, 16, 46, 0.35);
        }
        .stat-card, .toolbar-glass, .excel-table, .modal-panel {
            /* Default dark mode styles */
            background: var(--card-dark);
            backdrop-filter: blur(8px);
            border: 1px solid var(--border-dark);
            box-shadow: 0 12px 40px rgba(0,0,0,0.25);
        }
        .stat-card { border-radius: 1rem; padding: 0.3rem 0.8rem; display: flex; align-items: center; gap: 8px; }
        .excel-table { border-collapse: separate; border-spacing: 0; width: 100%; border: none; } /* Remove border from table itself */
        .excel-table thead th {
            position: sticky; top: 0; z-index: 10;
            background: rgba(196, 16, 46, 0.15); /* Dark mode header bg */
            border-bottom: 3px solid var(--tfc);
            font-size: 0.7rem; letter-spacing: 0.06em; text-transform: uppercase;
            color: #ff6b6b; font-weight: 700; padding: 14px 16px;
        }
        .excel-table td {
            border-bottom: 1px solid var(--border-dark);
            padding: 8px 10px; vertical-align: middle; color: #d0d0d0;
        }
        .excel-table tbody tr { transition: background 0.15s ease; background: var(--card-dark); }
        .excel-table tbody tr:nth-child(even) { background: rgba(255,255,255,0.03); }
        .excel-table tbody tr:hover { background: rgba(196, 16, 46, 0.15); }
        .excel-table tbody tr.completed { background: rgba(16, 185, 129, 0.15) !important; }
        .excel-table tbody tr.completed td { text-decoration: line-through; color: #10b981; }
        .excel-table tbody tr.completed td:last-child, .excel-table tbody tr.completed td:nth-last-child(2), .excel-table tbody tr.completed td:nth-last-child(3) { text-decoration: none; }
        .chip { border-radius: 9999px; padding: 0.35rem 0.85rem; font-size: 0.75rem; font-weight: 600; }
        .toast { position: fixed; bottom: 24px; right: 24px; z-index: 100; padding: 14px 20px; border-radius: 14px; background: #1f2937; color: white; font-size: 0.9rem; box-shadow: 0 10px 40px rgba(0,0,0,0.25); animation: toastIn 0.35s ease; }
        @keyframes toastIn { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: none; } }
        .modal-panel { box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5); }
        .empty-hint { border: 2px dashed var(--border-dark); border-radius: 1.5rem; color: #888; }
        .msg-btn { display: inline-flex; align-items: center; justify-content: center; width: 36px; height: 36px; border-radius: 8px; background: rgba(196, 16, 46, 0.2); color: #ff6b6b; border: 1px solid rgba(196, 16, 46, 0.4); cursor: pointer; transition: all 0.2s ease; font-size: 0.9rem; }
        .msg-btn:hover { background: rgba(196, 16, 46, 0.35); border-color: var(--tfc); }
        .tab-btn { cursor: pointer; }
        .tab-btn.active { color: white; border-color: var(--tfc); }
        .tab-content { display: block; }
        .tab-content.hidden { display: none; }

        /* Light mode styles */
        body.light-mode {
            --bg-dark: #f4f4f4;
            --light-tfc-red: #e4002b;
            --light-tfc-yellow: #ffc107;
            --text-dark: #1a1a1a;
            --card-dark: #ffffff;
            --border-dark: #e0e0e0;
            --light-hover-bg: #f5f5f5;
            --light-header-bg: #ffffff;
        }
        body.light-mode { background: var(--bg-dark); color: var(--text-dark); }
        body.light-mode .header-bar {
            background: #ffffff;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border-bottom: 1px solid var(--border-dark);
        }
        body.light-mode .header-bar .text-white { color: var(--text-dark) !important; }
        body.light-mode .header-bar .text-red-200\/90 { color: var(--light-tfc-red) !important; font-weight: 800; }
        body.light-mode .header-bar .bg-white\/95 { background: var(--tfc) !important; color: white !important; }
        
        body.light-mode .stat-card {
            background: var(--card-dark);
            border: 1px solid var(--border-dark);
            color: var(--text-dark);
            box-shadow: none;
        }
        body.light-mode .stat-card .text-red-100\/90 { color: #888; }
        body.light-mode .stat-card #pending-accept { color: #ffc107; }
        body.light-mode .stat-card #cooking-count { color: #fd7e14; }
        body.light-mode .stat-card #ready-count { color: var(--light-tfc-red); }
        body.light-mode .stat-card #revenue-total { color: #e4002b; }

        body.light-mode .toolbar-glass {
            background: var(--card-dark);
            border-color: var(--border-dark);
            box-shadow: none;
        }
        body.light-mode .excel-table tbody tr { background: var(--card-dark); border-bottom: 1px solid var(--border-dark); }
        body.light-mode .excel-table tbody tr:nth-child(even) { background: #fafafa; }
        body.light-mode .excel-table tbody tr:hover { background: #fef2f2; }
        body.light-mode .excel-table thead th {
            background: #fcfcfc;
            border-bottom: 2px solid #e4002b;
            color: #1a1a1a;
        }
        body.light-mode .excel-table td { color: #444444; border-bottom-color: #eeeeee; }
        body.light-mode .excel-table tbody tr.completed { background: #f0fdf4 !important; }
        body.light-mode .excel-table tbody tr.completed td { color: #15803d; }
        body.light-mode .excel-table tbody tr.completed .status-btn { background: rgba(40, 167, 69, 0.15) !important; color: #28a745 !important; }

        body.light-mode .bg-gray-900 { background: var(--card-dark) !important; border: 1px solid var(--border-dark); }
        body.light-mode .modal-panel { background: var(--card-dark); color: var(--text-dark); }
        body.light-mode .text-white { color: var(--text-dark) !important; }
        body.light-mode .text-gray-300, body.light-mode .text-gray-400, body.light-mode .text-gray-500 { color: #444 !important; }
        
        body.light-mode .tab-btn.active { color: var(--light-tfc-red); border-color: var(--light-tfc-red); }
        body.light-mode .tab-btn { color: #888888; }
        
        body.light-mode .header-bar button, body.light-mode .header-bar .bg-white\/15 {
            background: #f8f8f8;
            color: #333;
            border: 1px solid var(--border-dark);
        }
        body.light-mode .status-btn { background: #f3f4f6; border: 1px solid var(--border-dark); color: #666; }
        body.light-mode .status-btn.bg-emerald-600\/30 { background: rgba(40, 167, 69, 0.15) !important; color: #28a745 !important; }
        body.light-mode .status-btn.bg-red-600\/20 { background: rgba(228, 0, 43, 0.1) !important; color: var(--light-tfc-red) !important; }
        body.light-mode .status-btn.bg-amber-600\/30 { background: rgba(255, 193, 7, 0.15) !important; color: var(--light-tfc-yellow) !important; }
        body.light-mode .msg-btn { background: rgba(228, 0, 43, 0.05) !important; color: var(--light-tfc-red) !important; border-color: rgba(228, 0, 43, 0.2) !important; }
        body.light-mode .msg-btn:hover { background: rgba(228, 0, 43, 0.1) !important; border-color: var(--light-tfc-red) !important; }
        body.light-mode .filter-chip.bg-gray-900 { background: var(--light-tfc-red) !important; color: white !important; border-color: var(--light-tfc-red) !important; }
        body.light-mode .filter-chip.bg-gray-700 { background: #ffffff !important; color: #666 !important; border-color: var(--border-dark) !important; }
        body.light-mode .filter-chip.bg-gray-700:hover { background: #f9f9f9 !important; }
        body.light-mode .excel-table td.font-semibold.text-emerald-400 { color: #28a745 !important; }
        body.light-mode .excel-table td.font-semibold.text-white { color: #1a1a1a !important; }
        body.light-mode .excel-table td.font-mono.text-gray-500 { color: #777 !important; }
        body.light-mode .excel-table td.font-mono.text-sm.text-gray-400 { color: #666 !important; }
        body.light-mode .excel-table td.text-gray-300 { color: #333 !important; }

        /* Blue replacements - Clean look */
        body.light-mode .excel-table td .chip.bg-blue-600\/20 { background: rgba(255, 193, 7, 0.15) !important; color: var(--light-tfc-yellow) !important; border-color: rgba(255, 193, 7, 0.3) !important; }
        body.light-mode .excel-table td .chip.bg-red-600\/20 { background: rgba(228, 0, 43, 0.1) !important; color: var(--light-tfc-red) !important; border-color: rgba(228, 0, 43, 0.3) !important; }

        body.light-mode .status-btn.bg-blue-600 { background: var(--light-tfc-yellow) !important; color: #333 !important; box-shadow: 0 4px 10px rgba(255, 193, 7, 0.3) !important; }
        body.light-mode .status-btn.hover\:bg-blue-600\/20:hover { background: rgba(255, 193, 7, 0.1) !important; }
        body.light-mode .text-blue-400 { color: var(--light-tfc-yellow) !important; }

        body.light-mode .bg-blue-500\/10 { background: rgba(255, 193, 7, 0.1) !important; }
        body.light-mode .border-blue-500\/20 { border-color: rgba(255, 193, 7, 0.2) !important; }

        body.light-mode .bg-indigo-600 { background: var(--light-tfc-red) !important; }
        body.light-mode .hover\:bg-indigo-700:hover { background: var(--tfc-dark) !important; }

        body.light-mode .bg-blue-600 { background: var(--light-tfc-red) !important; }
        body.light-mode .hover\:bg-blue-700:hover { background: var(--tfc-dark) !important; }

        body.light-mode .bg-blue-600\/20 { background: rgba(255, 193, 7, 0.15) !important; }
        body.light-mode .hover\:bg-blue-600\/30:hover { background: rgba(255, 193, 7, 0.25) !important; }

        /* Password Modal Styling for Light Mode */
        body.light-mode .modal-panel { background: #ffffff !important; color: #1a1a1a !important; }
        body.light-mode #history-access-code { 
            background: #f9f9f9 !important; border-color: #e0e0e0 !important; color: #1a1a1a !important; 
            box-shadow: none !important;
        }
        body.light-mode #history-access-code:focus { border-color: var(--light-tfc-red) !important; ring: none !important; }

        /* History Modal Light Mode Styling */
        body.light-mode #historyModal .modal-panel {
            background: #ffffff; border-color: #e0e0e0; box-shadow: none;
        }
        body.light-mode #historyModal .modal-panel > div:first-child { /* Header */
            background: var(--light-header-bg);
            border-color: var(--border-dark);
            color: var(--text-dark);
        }
        body.light-mode #historyModal .modal-panel > div:first-child h3 {
            color: var(--text-dark);
        }
        body.light-mode #historyModal .modal-panel > div:first-child p {
            color: #666;
        }
        body.light-mode #historyModal .modal-panel > div:nth-child(2) { /* Content area */
            background: var(--bg-dark);
            color: var(--text-dark);
        }
        body.light-mode #historyModal .bg-slate-900\/50 { /* Chart container */
            background: var(--card-dark);
            border: 1px solid var(--border-dark);
        }
        body.light-mode #historyModal .bg-slate-800\/50 { /* Table header */
            background: var(--light-header-bg);
        }
        body.light-mode #historyModal .text-slate-400 { /* Table header text */
            color: #666;
        }
        body.light-mode #history-table-body {
            color: var(--text-dark);
            border-color: var(--border-dark);
        }
        body.light-mode #history-table-body tr {
            background: var(--card-dark);
        }
        body.light-mode #history-table-body tr:nth-child(even) {
            background: #fafafa;
        }
        body.light-mode #history-table-body tr:hover {
            background: var(--light-hover-bg);
        }
        body.light-mode #historyModal .divide-y.divide-slate-800 {
            border-color: var(--border-dark);
        }
        body.light-mode #historyModal .text-emerald-400 {
            color: #28a745; /* Keep green for profit */
        }
        body.light-mode #historyModal .text-blue-400 {
            color: var(--light-tfc-yellow) !important; /* Change customer count to yellow */
        }
        body.light-mode #historyModal .bg-emerald-500\/10 {
            background: rgba(40, 167, 69, 0.1) !important;
            border-color: rgba(40, 167, 69, 0.2) !important;
        }
        body.light-mode #historyModal .bg-blue-500\/10 {
            background: rgba(255, 193, 7, 0.1) !important;
            border-color: rgba(255, 193, 7, 0.2) !important;
        }
        #rotate-hint {
            display: none;
            position: fixed; inset: 0; background: #0f0f0f; color: #fff; z-index: 99999;
            flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 20px;
        }
        @media screen and (max-width: 1024px) and (orientation: portrait) {
            #rotate-hint { display: flex; }
            main, header { display: none; }
        }
        /* Ислоҳ барои клавиатура дар ҳолати landscape */
        @media screen and (max-height: 500px) {
            .fixed.inset-0.flex { align-items: flex-start !important; padding-top: 20px; overflow-y: auto; }
            .modal-panel { margin-bottom: 200px; } /* Ҷой барои скаролл */
        }
    </style>
</head>
<body class="min-h-screen text-gray-300">
    <div id="rotate-hint" onclick="enableGameMode()">
        <i class="fas fa-sync fa-3x mb-4 text-red-600 animate-pulse"></i>
        <h2 class="text-xl font-bold">Поверните телефон на 90 градусов</h2>
        <p class="text-gray-400 mt-2">Для использования панели админа требуется альбомный режим (landscape).</p>
    </div>
    <header class="header-bar text-white">
        <div class="max-w-full mx-auto px-2 py-3 flex items-center justify-between gap-4">
            <div class="flex items-center gap-4">
                <div class="w-12 h-12 rounded-2xl bg-white/95 overflow-hidden shadow-lg">
                    <img src="{{ url_for('static', filename='images/TFC.jpg') }}" class="w-full h-full object-cover" alt="TFC Logo">
                </div>
                <div class="flex items-center gap-4">
                    <div>
                        <h1 class="text-xl font-bold tracking-tight">TFC <span class="font-normal text-white/80 text-sm">Admin</span></h1>
                        <p class="text-[9px] text-red-200/90 tracking-[0.1em] uppercase">Tajik Fried Fish & Chicken</p>
                    </div>
                    <div class="flex items-center gap-1.5 sm:gap-2">
                        <div class="stat-card">
                            <span id="total-orders" class="text-lg font-bold">0</span> <span class="text-[9px] uppercase opacity-60">Всего</span>
                        </div>
                        <div class="stat-card">
                            <span id="pending-accept" class="text-lg font-bold text-red-400">0</span> <span class="text-[9px] uppercase opacity-60">Ожидание</span>
                        </div>
                        <div class="stat-card">
                            <span id="cooking-count" class="text-lg font-bold text-orange-300">0</span> <span class="text-[9px] uppercase opacity-60">Готовка</span>
                        </div>
                        <div class="stat-card">
                            <span id="ready-count" class="text-lg font-bold text-emerald-300">0</span> <span class="text-[9px] uppercase opacity-60">Готово</span>
                        </div>
                        <button type="button" onclick="toggleTheme()" class="flex items-center justify-center w-10 h-10 bg-white/10 hover:bg-white/20 rounded-xl transition-all" title="Ивази мавзӯъ">
                            <i id="theme-icon" class="fas fa-moon"></i>
                        </button>
                        <div id="current-time" class="hidden sm:block text-xs font-mono opacity-60"></div>
                    </div>
                </div>
            </div>

        </div>
    </header>

    <main class="max-w-full mx-auto px-0 py-2">
        <div class="flex gap-4 mb-6 border-b border-gray-700">
            <button type="button" onclick="switchTab('orders')" id="orders-tab-btn" 
                    class="tab-btn active px-6 py-3 font-semibold text-white border-b-2 border-red-600 transition-colors">
                <i class="fas fa-receipt mr-2"></i>Заказы
            </button>
            <button type="button" onclick="switchTab('foods')" id="foods-tab-btn" 
                    class="tab-btn px-6 py-3 font-semibold text-gray-400 border-b-2 border-transparent hover:text-white transition-colors">
                <i class="fas fa-utensils mr-2"></i>Меню
            </button>
            <button type="button" onclick="switchTab('vakansii')" id="vakansii-tab-btn" 
                    class="tab-btn px-6 py-3 font-semibold text-gray-400 border-b-2 border-transparent hover:text-white transition-colors">
                <i class="fas fa-briefcase mr-2"></i>Вакансии
            </button>
            <button type="button" onclick="switchTab('aktsii')" id="aktsii-tab-btn" 
                    class="tab-btn px-6 py-3 font-semibold text-gray-400 border-b-2 border-transparent hover:text-white transition-colors">
                <i class="fas fa-bullhorn mr-2"></i>Акции
            </button>
        </div>

        <!-- ORDERS SECTION -->
        <div id="orders-section" class="tab-content">
        <div class="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6 mb-6">
            <div>
                <h2 class="text-3xl sm:text-4xl font-bold text-white">Заказы</h2>
                <p class="text-gray-400 mt-2 flex items-center gap-2 text-sm">
                    <span class="inline-flex w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
                    Поиск, фильтр и экспорт в CSV
                </p>
            </div>
        </div>

        <div class="toolbar-glass rounded-2xl p-4 mb-4 flex flex-col sm:flex-row flex-wrap gap-3 items-stretch sm:items-center justify-between">
            <div class="relative flex-1 min-w-[200px] max-w-md">
                <i class="fas fa-search absolute left-4 top-1/2 -translate-y-1/2 text-gray-500 text-sm"></i>
                <input type="search" id="admin-order-search" name="ignore-autofill-1" placeholder="Поиск..." value="" autocomplete="new-password"
                       class="w-full pl-11 pr-4 py-3 rounded-xl border border-gray-600 bg-gray-900/50 text-gray-200 text-sm placeholder-gray-500 focus:ring-2 focus:ring-red-500/40 focus:border-red-600 outline-none"
                       oninput="applyFilters()">
            </div>
            <div class="flex flex-wrap gap-2 items-center">
                <span class="text-xs text-gray-400 uppercase tracking-wide mr-1">Статус:</span>
                <button type="button" data-filter="all" onclick="setFilter('all')" class="filter-chip chip bg-gray-900 text-white border border-gray-700">Все</button>
                <button type="button" data-filter="pending" onclick="setFilter('pending')" class="filter-chip chip bg-gray-700 text-gray-200 hover:bg-gray-600 border border-gray-600">Ожидание</button>
                <button type="button" data-filter="cooking" onclick="setFilter('cooking')" class="filter-chip chip bg-gray-700 text-gray-200 hover:bg-gray-600 border border-gray-600">Готовка</button>
                <button type="button" data-filter="done" onclick="setFilter('done')" class="filter-chip chip bg-gray-700 text-gray-200 hover:bg-gray-600 border border-gray-600">Выполнено</button>
                <button type="button" onclick="exportCsv()" class="chip bg-emerald-600 text-white hover:bg-emerald-700 inline-flex items-center gap-2">
                    <i class="fas fa-file-csv"></i>
                </button>
                <button type="button" onclick="showHistory()" class="chip bg-indigo-600 text-white hover:bg-indigo-700 inline-flex items-center gap-2">
                    <i class="fas fa-chart-line"></i>
                </button>
                <button type="button" onclick="showPopularFoods()" class="chip bg-pink-600 text-white hover:bg-pink-700 inline-flex items-center gap-2" title="Популярные блюда">
                    <i class="fas fa-fire"></i>
                </button>
                <button type="button" onclick="showFullHistory()" class="chip bg-orange-600 text-white hover:bg-orange-700 inline-flex items-center gap-2" title="Полная история заказов">
                    <i class="fas fa-history"></i>
                </button>
                <button type="button" onclick="changeAdminPassword()" class="chip bg-gray-700 text-gray-200 hover:bg-gray-600 border border-gray-600" title="Изменить пароль">
                    <i class="fas fa-key"></i>
                </button>
                <button type="button" onclick="clearAllOrders()" class="chip bg-red-600 text-white hover:bg-red-700 inline-flex items-center gap-2">
                    <i class="fas fa-trash-can"></i>
                </button>
            </div>
        </div>

        <div class="bg-gray-900 rounded-2xl shadow-xl border border-gray-800 overflow-hidden">
            <div class="max-h-[min(70vh,720px)] overflow-auto">
                <table class="excel-table" id="main-table">
                    <thead>
                        <tr>
                            <th class="text-left rounded-tl-lg">№</th>
                            <th class="text-left">Имя</th>
                            <th class="text-left">Телефон</th>
                            <th class="text-left">Тип</th>
                            <th class="text-left">ID</th>
                            <th class="text-left">Блюдо</th>
                            <th class="text-left">Цена</th>
                            <th class="text-center">Время</th>
                            <th class="text-center">Принят</th>
                            <th class="text-center">Готов</th>
            <th class="text-center">В пути</th>
            <th class="text-left rounded-tr-lg">📍 Адрес</th>
                        </tr>
                    </thead>
                    <tbody id="orders-table"></tbody>
                </table>
            </div>
            <div id="empty-state" class="hidden empty-hint m-6 p-12 text-center text-gray-500">
                <i class="fas fa-inbox text-4xl text-gray-500 mb-3"></i>
                <p class="font-medium text-gray-400">Заказов нет или ничего не найдено</p>
                <p class="text-sm mt-1">Добавьте новый заказ или измените фильтр</p>
            </div>
        </div>

        <p class="mt-6 text-center text-xs text-gray-500">
            TFC Admin v2 • Dark Theme • <span id="saved-hint" class="text-emerald-500/80"></span>
        </p>
        </div>

        <!-- FOODS SECTION -->
        <div id="foods-section" class="tab-content hidden">
            <div class="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6 mb-6">
                <div>
                    <h2 class="text-3xl sm:text-4xl font-bold text-white">Меню блюд</h2>
                    <p class="text-gray-400 mt-2 flex items-center gap-2 text-sm">
                        <span class="inline-flex w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
                        Управление блюдами: добавление, удаление, изменение цен
                    </p>
                </div>
                <button type="button" onclick="showAddFoodModal()"
                        class="inline-flex items-center justify-center gap-2 bg-[#e4002b] hover:bg-[#c8102e] text-white px-6 py-3.5 rounded-2xl font-semibold shadow-lg shadow-red-500/25 hover:shadow-xl active:scale-[0.98] transition-all">
                    <i class="fas fa-plus"></i>
                    Новое блюдо
                </button>
            </div>

            <div class="toolbar-glass rounded-2xl p-4 mb-4 flex flex-col sm:flex-row flex-wrap gap-3 items-stretch sm:items-center justify-between">
                <div class="relative flex-1 min-w-[200px] max-w-md">
                    <i class="fas fa-search absolute left-4 top-1/2 -translate-y-1/2 text-gray-500 text-sm"></i>
                    <input type="search" id="admin-food-search" name="ignore-autofill-2" placeholder="Поиск по названию..." value="" autocomplete="new-password"
                           class="w-full pl-11 pr-4 py-3 rounded-xl border border-gray-600 bg-gray-900/50 text-gray-200 text-sm placeholder-gray-500 focus:ring-2 focus:ring-red-500/40 focus:border-red-600 outline-none"
                           oninput="applyFoodsFilter()">
                </div>
                <div class="flex flex-wrap gap-2 items-center">
                    <span class="text-xs text-gray-400 uppercase tracking-wide mr-1">Категория:</span>
                    <button type="button" data-category="all" onclick="setFoodsCategory('all')" class="food-category-chip chip bg-gray-900 text-white border border-gray-700">Все</button>
                    <button type="button" data-category="Меню" onclick="setFoodsCategory('Меню')" class="food-category-chip chip bg-gray-700 text-gray-200 hover:bg-gray-600 border border-gray-600">Меню</button>
                    <button type="button" data-category="Пицца" onclick="setFoodsCategory('Пицца')" class="food-category-chip chip bg-gray-700 text-gray-200 hover:bg-gray-600 border border-gray-600">Пицца</button>
                    <button type="button" data-category="Суши" onclick="setFoodsCategory('Суши')" class="food-category-chip chip bg-gray-700 text-gray-200 hover:bg-gray-600 border border-gray-600">Суши</button>
                    <button type="button" data-category="Фастфуд" onclick="setFoodsCategory('Фастфуд')" class="food-category-chip chip bg-gray-700 text-gray-200 hover:bg-gray-600 border border-gray-600">Фастфуд</button>
                    <button type="button" data-category="Летнее меню" onclick="setFoodsCategory('Летнее меню')" class="food-category-chip chip bg-gray-700 text-gray-200 hover:bg-gray-600 border border-gray-600">Летнее меню</button>
                    <button type="button" data-category="Комбо" onclick="setFoodsCategory('Комбо')" class="food-category-chip chip bg-gray-700 text-gray-200 hover:bg-gray-600 border border-gray-600">Комбо</button>
                    <span id="foods-subcategory-label" class="text-xs text-gray-400 uppercase tracking-wide mr-1 hidden">Подкатегория:</span>
                    <select id="foods-subcategory-select" onchange="setFoodsSubcategory(this.value)" class="hidden rounded-xl border border-gray-600 bg-gray-900/50 text-gray-200 px-4 py-3 text-sm outline-none">
                        <option value="all">Все</option>
                    </select>
                </div>
            </div>

            <div class="bg-gray-900 rounded-2xl shadow-xl border border-gray-800 overflow-hidden">
                <div class="max-h-[min(70vh,720px)] overflow-auto">
                    <table class="excel-table" id="foods-table">
                        <thead>
                            <tr>
                                <th class="text-left rounded-tl-lg">№</th>
                            <th class="text-left">Название</th>
                            <th class="text-left">Категория / Подкат.</th>
                            <th class="text-left">Цена (сом)</th>
                            <th class="text-left">Картинка</th>
                            <th class="text-left">Подробная информация</th>
                            <th class="text-center rounded-tr-lg">Действие</th>
                            </tr>
                        </thead>
                        <tbody id="foods-table-body"></tbody>
                    </table>
                </div>
                <div id="empty-foods-state" class="hidden empty-hint m-6 p-12 text-center text-gray-500">
                    <i class="fas fa-bread-slice text-4xl text-gray-500 mb-3"></i>
                <p class="font-medium text-gray-400">Блюд нет или ничего не найдено</p>
                <p class="text-sm mt-1">Добавьте новое блюдо или измените категорию</p>
                </div>
            </div>

        <p class="mt-6 text-center text-xs text-gray-500">
            TFC Admin v2 • Menu Management
        </p>
        </div>

        <!-- VAKANSII SECTION -->
        <div id="vakansii-section" class="tab-content hidden">
            <div class="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6 mb-6">
                <div>
                    <h2 class="text-3xl sm:text-4xl font-bold text-white">Вакансии</h2>
                    <p class="text-gray-400 mt-2 text-sm">Управление вакансиями</p>
                </div>
                <button type="button" onclick="showAddVakansiiModal()" class="inline-flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-6 py-3.5 rounded-2xl font-semibold transition-all">
                    <i class="fas fa-plus"></i> Новая вакансия
                </button>
            </div>
            <div class="bg-gray-900 rounded-2xl shadow-xl border border-gray-800 overflow-hidden">
            <div class="max-h-[650px] overflow-auto">
                    <table class="excel-table">
                        <thead>
                            <tr>
                                <th class="text-left">Заголовок</th>
                                <th class="text-left">Зарплата</th>
                                <th class="text-left">Описание</th>
                                <th class="text-center">Действие</th>
                            </tr>
                        </thead>
                        <tbody id="vakansii-table-body"></tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- AKTSII SECTION -->
        <div id="aktsii-section" class="tab-content hidden">
            <div class="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6 mb-6">
                <div>
                    <h2 class="text-3xl sm:text-4xl font-bold text-white">Акции</h2>
                    <p class="text-gray-400 mt-2 text-sm">Управление акциями: напишите здесь о скидках.</p>
                </div>
                <button type="button" onclick="showAddAktsiiModal()"
                        class="inline-flex items-center justify-center gap-2 bg-red-600 hover:bg-red-700 text-white px-6 py-3.5 rounded-2xl font-semibold transition-all">
                    <i class="fas fa-plus"></i> Новая акция
                </button>
            </div>
            <div class="bg-gray-900 rounded-2xl shadow-xl border border-gray-800 overflow-hidden">
                <div class="max-h-[500px] overflow-auto">
                    <table class="excel-table">
                        <thead>
                            <tr>
                                <th class="text-left">Заголовок</th>
                                <th class="text-left">Цена</th>
                                <th class="text-left">Текст акции</th>
                                <th class="text-left w-32">Дата</th>
                                <th class="text-center">Действие</th>
                            </tr>
                        </thead>
                        <tbody id="aktsii-table-body"></tbody>
                    </table>
                </div>
            </div>
        </div>
    </main>

    <div id="addModal" onclick="if(event.target===this)hideAddModal()"
         class="hidden fixed inset-0 bg-black/60 backdrop-blur-sm z-50 items-center justify-center p-4">
        <div onclick="event.stopPropagation()" class="modal-panel bg-white rounded-2xl w-full max-w-lg overflow-hidden">
            <div class="bg-gradient-to-r from-red-600 to-red-700 px-6 py-4 text-white flex justify-between items-center">
                <h3 class="text-xl font-semibold">Новый заказ</h3>
                <div class="flex items-center gap-2">
                    <button type="button" onclick="addNewOrder()" class="bg-yellow-400 hover:bg-yellow-500 text-black px-5 py-2 rounded-xl font-bold text-sm transition-all shadow-lg active:scale-95">Принять</button>
                    <button type="button" onclick="hideAddModal()" class="p-2 rounded-lg hover:bg-white/20 transition-colors" aria-label="Закрыть">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
            <div class="px-6 py-6 space-y-5 max-h-[75vh] overflow-y-auto">
                <div>
                    <label class="block text-sm font-medium text-gray-600 mb-1.5">Имя клиента</label>
                    <input id="modal-name" type="text" autocomplete="off" class="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-red-500/40 outline-none"
                           placeholder="Например: Рустам Каримов">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-600 mb-1.5">Блюдо / сет</label>
                    <input id="modal-food" type="text" autocomplete="off" class="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-red-500/40 outline-none"
                           placeholder="Например: 2× Bucket + Кола">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-600 mb-1.5">Цена (сом)</label>
                    <div class="relative">
                        <input id="modal-price" type="text" inputmode="decimal" autocomplete="off" class="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-red-500/40 outline-none"
                               placeholder="45">
                        <span class="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 text-sm">сом</span>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- FOOD ADD/EDIT MODAL -->
    <div id="addFoodModal" onclick="if(event.target===this)hideAddFoodModal()"
         class="hidden fixed inset-0 bg-black/60 backdrop-blur-sm z-50 items-center justify-center p-4">
        <div onclick="event.stopPropagation()" class="modal-panel bg-white rounded-2xl w-full max-w-lg overflow-hidden">
            <div class="bg-gradient-to-r from-red-600 to-red-700 px-6 py-4 text-white flex justify-between items-center">
                <h3 class="text-xl font-semibold" id="food-modal-title">Новое блюдо</h3>
                <div class="flex items-center gap-2">
                    <button type="button" id="food-modal-submit-btn" onclick="saveFood()" class="bg-yellow-400 hover:bg-yellow-500 text-black px-5 py-2 rounded-xl font-bold text-sm transition-all shadow-lg active:scale-95">Создать</button>
                    <button type="button" onclick="hideAddFoodModal()" class="p-2 rounded-lg hover:bg-white/20 transition-colors" aria-label="Закрыть">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
            <div class="px-6 py-6 space-y-5 max-h-[75vh] overflow-y-auto">
                <input type="hidden" id="food-modal-id" value="">
                <div>
                    <label id="label-food-name" class="block text-sm font-medium text-gray-600 mb-1.5">Название</label>
                    <input id="food-modal-name" type="text" autocomplete="off" class="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-red-500/40 outline-none"
                           placeholder="Например: ПАСТА БОЛОНЕЗА">
                </div>
                <div id="food-modal-category-container">
                    <label class="block text-sm font-medium text-gray-600 mb-1.5">Категория</label>
                    <select id="food-modal-category" onchange="updateSubcategories()" class="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-red-500/40 outline-none">
                        <option value="Меню">Меню</option>
                        <option value="Пицца">Пицца</option>
                        <option value="Суши">Суши</option>
                        <option value="Фастфуд">Фастфуд</option>
                        <option value="Летнее меню">Летнее меню</option>
                        <option value="Комбо">Комбо</option>
                        <option value="Вакансии">Вакансии</option>
                        <option value="Otziv">Отзывы</option>
                    </select>
                </div>
                <div id="food-modal-subcategory-container" class="hidden">
                    <label class="block text-sm font-medium text-gray-600 mb-1.5">Подкатегория</label>
                    <select id="food-modal-subcategory" class="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-red-500/40 outline-none">
                    </select>
                </div>
                <div id="food-modal-desc-container">
                    <label class="block text-sm font-medium text-gray-600 mb-1.5">Подробная информация</label>
                    <textarea id="food-modal-description" rows="5" autocomplete="off" class="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-red-500/40 outline-none"
                              placeholder="Введите описание, требования и т.д."></textarea>
                </div>
                <div>
                    <label id="label-food-price" class="block text-sm font-medium text-gray-600 mb-1.5">Цена (сом)</label>
                    <div class="relative">
                        <input id="food-modal-price" type="text" inputmode="decimal" class="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-red-500/40 outline-none"
                               placeholder="31">
                        <span class="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 text-sm">сом</span>
                    </div>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-600 mb-1.5">Медиафайл (Фото или Видео)</label>
                    <input id="food-modal-file" type="file" accept="image/*,video/*" class="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-red-500/40 outline-none bg-gray-50 text-sm file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-xs file:font-bold file:bg-red-600 file:text-white hover:file:bg-red-700 cursor-pointer">
                    <input type="hidden" id="food-modal-image" value="">
                    <p class="text-[10px] text-gray-400 mt-1">Можно загрузить фото или видео.</p>
                </div>
            </div>
        </div>
    </div>

    <!-- REVENUE HISTORY MODAL -->
    <div id="historyModal" onclick="if(event.target===this)hideHistoryModal()"
         class="hidden fixed inset-0 bg-black/60 backdrop-blur-sm z-50 items-center justify-center p-4">
        <div onclick="event.stopPropagation()" class="modal-panel bg-[#0f172a] rounded-3xl w-full max-w-4xl overflow-hidden border border-slate-700 shadow-2xl">
            <div class="bg-slate-800/50 px-8 py-6 text-white flex justify-between items-center border-b border-slate-700">
                <div>
                    <h3 class="text-2xl font-bold flex items-center gap-3">
                        <i class="fas fa-chart-line text-emerald-400"></i>
                        Trading Analytics
                    </h3>
                    <p class="text-slate-400 text-xs uppercase tracking-widest mt-1">Отчет по доходам TFC</p>
                </div>
                <div class="flex items-center gap-2">
                    <button type="button" onclick="clearHistory()" class="p-2 rounded-lg hover:bg-red-500/20 text-red-400 transition-colors" title="Очистить историю">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                    <button type="button" onclick="hideHistoryModal()" class="p-2 rounded-lg hover:bg-white/10 text-white transition-colors">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
            <div class="p-8 space-y-8 max-h-[85vh] overflow-y-auto bg-gradient-to-b from-[#0f172a] to-[#1e293b]">
                <!-- Trading Chart Container -->
                <div class="bg-slate-900/50 p-6 rounded-2xl border border-slate-700">
                    <canvas id="tradingChart" style="width: 100%; height: 300px;"></canvas>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="bg-slate-900/50 rounded-2xl border border-slate-700 overflow-hidden">
                        <table class="w-full text-left">
                            <thead class="bg-slate-800/50 text-slate-400 text-[10px] uppercase tracking-wider"> <!-- Table header for history modal -->
                                <tr><th class="px-6 py-4">Дата</th><th class="px-6 py-4">Заказов</th><th class="px-6 py-4 text-right">Выручка</th></tr>
                            </thead>
                            <tbody id="history-table-body" class="divide-y divide-slate-800 text-slate-300"></tbody>
                        </table>
                    </div>
                    <div class="grid grid-cols-1 gap-4">
                        <div class="flex flex-col justify-center items-center p-6 bg-emerald-500/10 rounded-2xl border border-emerald-500/20">
                            <div class="text-emerald-400 text-xs font-bold uppercase tracking-widest mb-1">Общий профит</div>
                            <div id="grand-total-display" class="text-4xl font-black text-white tabular-nums tracking-tighter">0</div>
                        </div>
                        <div class="flex flex-col justify-center items-center p-6 bg-blue-500/10 rounded-2xl border border-blue-500/20"> <!-- This will be yellow in light mode -->
                            <div class="text-blue-400 text-xs font-bold uppercase tracking-widest mb-1">Всего клиентов</div>
                            <div id="grand-customers-display" class="text-4xl font-black text-white tabular-nums tracking-tighter">0</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- FULL ORDER HISTORY MODAL -->
    <div id="fullHistoryModal" onclick="if(event.target===this)hideFullHistoryModal()"
         class="hidden fixed inset-0 bg-black/60 backdrop-blur-sm z-50 items-center justify-center p-4">
        <div onclick="event.stopPropagation()" class="modal-panel bg-white rounded-2xl w-full max-w-5xl overflow-hidden shadow-2xl">
            <div class="bg-orange-600 px-6 py-4 text-white flex justify-between items-center">
                <div>
                    <h3 class="text-xl font-bold flex items-center gap-3">
                        <i class="fas fa-history"></i>
                        Полная история заказов
                    </h3>
                    <p class="text-white/80 text-[10px] uppercase tracking-widest mt-0.5">Все поступившие заказы (архив)</p>
                </div>
                <div class="flex items-center gap-2">
                    <button type="button" onclick="clearFullHistory()" class="p-2 rounded-lg hover:bg-red-500/20 text-white transition-colors" title="Тоза кардани таърих">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                    <button type="button" onclick="hideFullHistoryModal()" class="p-2 rounded-lg hover:bg-white/20 text-white transition-colors">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
            <div class="p-0 max-h-[80vh] overflow-y-auto">
                <table class="excel-table">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="text-left px-6 py-3 text-xs font-bold text-gray-500 uppercase">Дата</th>
                            <th class="text-left px-6 py-3 text-xs font-bold text-gray-500 uppercase">Имя</th>
                            <th class="text-left px-6 py-3 text-xs font-bold text-gray-500 uppercase">Телефон</th>
                            <th class="text-left px-6 py-3 text-xs font-bold text-gray-500 uppercase">Блюдо</th>
                            <th class="text-left px-6 py-3 text-xs font-bold text-gray-500 uppercase">Сумма</th>
                            <th class="text-left px-6 py-3 text-xs font-bold text-gray-500 uppercase">Тип</th>
                        </tr>
                    </thead>
                    <tbody id="full-history-table-body" class="divide-y divide-gray-200">
                        <!-- Маълумот инҷо меояд -->
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- POPULAR FOODS MODAL -->
    <div id="popularFoodsModal" onclick="if(event.target===this)hidePopularFoodsModal()"
         class="hidden fixed inset-0 bg-black/60 backdrop-blur-sm z-50 items-center justify-center p-4">
        <div onclick="event.stopPropagation()" class="modal-panel bg-white rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl">
            <div class="bg-pink-600 px-6 py-4 text-white flex justify-between items-center">
                <div>
                    <h3 class="text-xl font-bold flex items-center gap-3">
                        <i class="fas fa-fire"></i>
                        Популярные блюда
                    </h3>
                </div>
                <button type="button" onclick="hidePopularFoodsModal()" class="p-2 rounded-lg hover:bg-white/20 text-white transition-colors">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="p-0 max-h-[70vh] overflow-y-auto">
                <table class="excel-table">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="text-left px-6 py-3 text-xs font-bold text-gray-500 uppercase">Название блюда</th>
                            <th class="text-center px-6 py-3 text-xs font-bold text-gray-500 uppercase">Количество</th>
                            <th class="text-right px-6 py-3 text-xs font-bold text-gray-500 uppercase">Общая сумма</th>
                        </tr>
                    </thead>
                    <tbody id="popular-foods-table-body" class="divide-y divide-gray-200"></tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- PASSWORD MODAL FOR HISTORY -->
    <div id="passwordModal" onclick="if(event.target===this)hidePasswordModal()"
         class="hidden fixed inset-0 bg-black/60 backdrop-blur-sm z-[60] flex items-start justify-center pt-20 sm:items-center sm:pt-0 p-4">
        <div onclick="event.stopPropagation()" class="modal-panel bg-white rounded-2xl w-full max-w-sm overflow-hidden shadow-2xl">
            <div class="bg-gray-800 px-6 py-4 text-white flex justify-between items-center">
                <h3 class="text-lg font-semibold">Доступ к истории</h3>
                <button type="button" onclick="hidePasswordModal()" class="p-2 rounded-lg hover:bg-white/20 transition-colors">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="p-6 space-y-4">
                <input id="history-access-code" type="text" placeholder="Введите код..." autocomplete="off" autocapitalize="off" spellcheck="false"
                       class="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-red-500/40 outline-none text-center text-xl tracking-widest" style="-webkit-text-security: disc;"> <!-- Password input -->
                <button type="button" onclick="verifyHistoryCode()" 
                        class="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl transition-all shadow-lg active:scale-95">Войти</button>
            </div>
        </div>
    </div>

    <!-- MODAL FOR CHANGING PASSWORD -->
    <div id="changePasswordModal" onclick="if(event.target===this)hideChangePasswordModal()"
         class="hidden fixed inset-0 bg-black/60 backdrop-blur-sm z-[70] items-start justify-center pt-20 sm:items-center sm:pt-0 p-4">
        <div onclick="event.stopPropagation()" class="modal-panel bg-white rounded-2xl w-full max-w-sm overflow-hidden shadow-2xl">
            <div class="bg-gray-800 px-6 py-4 text-white flex justify-between items-center">
                <h3 class="text-lg font-semibold">Изменение пароля</h3>
                <button type="button" onclick="hideChangePasswordModal()" class="p-2 rounded-lg hover:bg-white/20 transition-colors">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="p-6 space-y-4 text-gray-800">
                <div>
                    <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Текущий пароль</label>
                    <input id="old-pass-input" type="password" class="w-full px-4 py-3 rounded-xl border border-gray-200 outline-none focus:ring-2 focus:ring-red-500/40">
                </div>
                <div>
                    <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Новый пароль</label>
                    <input id="new-pass-input" type="password" class="w-full px-4 py-3 rounded-xl border border-gray-200 outline-none focus:ring-2 focus:ring-red-500/40">
                </div>
                <button type="button" onclick="submitPasswordChange()"
                        class="w-full py-3 bg-red-600 hover:bg-red-700 text-white font-bold rounded-xl transition-all shadow-lg active:scale-95">Сохранить</button>
            </div>
        </div>
    </div>

    <!-- CUSTOM CONFIRM MODAL -->
    <div id="confirmModal" onclick="if(event.target===this)hideConfirmModal()"
         class="hidden fixed inset-0 bg-black/60 backdrop-blur-sm z-[70] items-center justify-center p-4">
        <div onclick="event.stopPropagation()" class="modal-panel bg-white rounded-2xl w-full max-w-sm overflow-hidden shadow-2xl">
            <div class="p-6 text-center space-y-6">
                <div class="w-16 h-16 bg-red-100 text-red-600 rounded-full flex items-center justify-center mx-auto text-2xl">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
                <p id="confirm-msg" class="text-gray-800 font-medium text-lg leading-relaxed"></p>
                <div class="flex gap-3">
                    <button type="button" onclick="hideConfirmModal()" class="flex-1 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 font-bold rounded-xl transition-all">Отмена</button>
                    <button type="button" id="confirm-execute-btn" class="flex-1 py-3 bg-red-600 hover:bg-red-700 text-white font-bold rounded-xl transition-all shadow-lg active:scale-95">Да, выполнить</button>
                </div>
            </div>
        </div>
    </div>

    <div id="toast-host"></div>

    <script>
        const STORAGE_KEY = 'tfc_admin_orders_v2';
        let orders = [];
        let filterMode = 'all';
        let revenueChart = null;
        let accessTarget = null;
        let confirmAction = null;
        let isAuthorized = false;
        let lastSeenOrderId = 0;

        const newOrderSound = new Audio('/static/music.mp3'); // Файли садоӣ бояд дар папкаи static бошад

        function showConfirm(msg, action) {
            document.getElementById('confirm-msg').textContent = msg;
            confirmAction = action;
            document.getElementById('confirm-execute-btn').onclick = () => { confirmAction(); hideConfirmModal(); };
            const m = document.getElementById('confirmModal');
            m.classList.remove('hidden');
            m.classList.add('flex');
        }

        function hideConfirmModal() {
            document.getElementById('confirmModal').classList.add('hidden');
            document.getElementById('confirmModal').classList.remove('flex');
        }

        // Функция барои автоматикӣ гузаштан ба ҳолати албомӣ (landscape)
        async function enableGameMode() {
            const docEl = document.documentElement;
            const requestFs = docEl.requestFullscreen || docEl.mozRequestFullScreen || docEl.webkitRequestFullscreen || docEl.msRequestFullscreen;

            try {
                // Барои қулф кардани самти экран бояд Fullscreen фаъол шавад
                if (requestFs && !document.fullscreenElement) {
                    await requestFs.call(docEl);
                }
                if (screen.orientation && screen.orientation.lock) {
                    await screen.orientation.lock('landscape');
                }
            } catch (err) {
                console.warn("Orientation lock failed:", err);
            }
            // Танҳо як бор пас аз клики аввалин иҷро мешавад
            document.removeEventListener('click', enableGameMode);
            document.removeEventListener('touchstart', enableGameMode);
        }

        function loadOrders() {
            try {
                const raw = localStorage.getItem(STORAGE_KEY);
                if (raw) {
                    orders = JSON.parse(raw);
                    return;
                }
            } catch (e) {}
            orders = [];
            saveOrders();
        }

        function saveOrders() {
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify(orders));
                const el = document.getElementById('saved-hint');
                if (el) el.textContent = 'Данные сохранены в этом браузере.';
            } catch (e) {
                toast('Не удалось сохранить', true);
            }
        }

        function parsePrice(p) {
            const n = parseFloat(String(p).replace(',', '.').replace(/[^0-9.]/g, ''));
            return isNaN(n) ? 0 : n;
        }

        function filteredOrders() {
            const q = (document.getElementById('admin-order-search')?.value || '').trim().toLowerCase();
            let list = orders.filter(o => {
                if (!q) return true;
                const customerName = o.nom || o.customer || '';
                return (customerName + ' ' + (o.mijoz_id || '') + ' ' + o.khurok).toLowerCase().includes(q);
            });
            list = list.filter(o => {
                const isDelivery = o.delivery_type === 'delivery';
                // Заказ считается полностью завершенным только если он доставлен (для доставки) или готов (для самовывоза)
                const isDone = o.qabyl && o.omoda && (!isDelivery || o.dostavka === 2);
                const isPending = !o.qabyl;
                // Ҳамаи заказҳои қабулшуда дар таби "Готовка" мемонанд, то гум нашаванд
                const inProgress = o.qabyl;

                if (filterMode === 'all') return true; // Ҳамаи заказҳо дар ин ҷо мемонанд
                if (filterMode === 'pending') return isPending;
                if (filterMode === 'cooking') return inProgress;
                if (filterMode === 'done') return isDone;
                return true;
            });
            return list;
        }

        function setFilter(mode) {
            filterMode = mode;
            document.querySelectorAll('.filter-chip[data-filter]').forEach(btn => {
                const on = btn.getAttribute('data-filter') === mode;
                btn.className = 'filter-chip chip ' + (on ? 'bg-gray-900 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300');
            });
            renderTable();
        }

        function applyFilters() { renderTable(); }

        function renderTable() {
            const tbody = document.getElementById('orders-table');
            const emptyEl = document.getElementById('empty-state');
            const list = filteredOrders();
            tbody.innerHTML = '';

            list.forEach((order, index) => {
                let isCompleted = false;
                if (order.delivery_type === 'delivery') {
                    isCompleted = order.qabyl && order.omoda && order.dostavka === 2;
                } else {
                    isCompleted = order.qabyl && order.omoda;
                }
            // Тафтиши он ки оё ҳамаи хӯрокҳо хат зада шудаанд (refund == price)
            const isFullyOOS = order.out_of_stock && (parsePrice(order.pul) > 0 && (order.refund >= parsePrice(order.pul)));
                const row = document.createElement('tr');
            row.className = (isCompleted || isFullyOOS) ? 'completed table-row' : 'table-row';
                const customerName = order.nom || order.customer || 'Неизвестно';

                row.innerHTML = `
                    <td class="font-mono text-gray-500">${index + 1}</td>
                    <td class="font-semibold text-white whitespace-nowrap">${escapeHtml(customerName)}</td>
                    <td class="font-bold text-yellow-400">${escapeHtml(order.phone || '—')}</td>
                    <td>
                        <span class="chip flex items-center gap-1 w-fit ${order.delivery_type === 'delivery'
                            ? 'bg-red-600/20 text-red-400 border border-red-600/30'
                            : 'bg-blue-600/20 text-blue-400 border border-blue-600/30'}"> <!-- This will be yellow in light mode -->
                            <i class="fas ${order.delivery_type === 'delivery' ? 'fa-truck' : 'fa-walking'} text-xs"></i>
                            ${order.delivery_type === 'delivery' ? 'Доставка' : 'Самовывоз'}
                        </span>
                        <div class="text-[10px] opacity-60 mt-1 flex items-center gap-1">
                            ${order.payment_method === 'cash' ? '<i class="fas fa-money-bill-wave text-emerald-500"></i> Наличные' : '<i class="fas fa-credit-card text-blue-400"></i> Онлайн'}
                        </div>
                    </td>
                    <td class="font-mono text-sm text-gray-400">#${order.id} <span class="opacity-50">(${escapeHtml(order.mijoz_id || '—')})</span></td>
                    <td class="text-gray-300 whitespace-nowrap">
                        ${order.khurok.split(', ').map(it => {
                            const isStruck = it.includes('<s>');
                            const clean = it.replace(/<\/?s>/g, '');
                            return `<span onclick="toggleFoodItem(${order.id}, \`${order.khurok.replace(/`/g, '\\`').replace(/"/g, '&quot;')}\`, \`${it.replace(/`/g, '\\`').replace(/"/g, '&quot;')}\`)" 
                                          class="cursor-pointer hover:text-red-500 transition-colors ${isStruck ? 'line-through text-red-500 opacity-50' : ''}">${escapeHtml(clean)}</span>`;
                        }).join(', ')}
                    </td>
                    <td class="font-semibold tabular-nums">
                        <span class="text-emerald-400">${escapeHtml(order.pul)} смн</span>
                        ${order.refund > 0 ? `<span class="ml-2 text-red-500 font-black animate-pulse">(-${order.refund})</span>` : ''}
                    </td>
                    <td class="text-center">
                        ${isFullyOOS ? '<span class="text-gray-600 text-xs">—</span>' : `
                        <input type="number" id="time-${order.id}" oninput="updateOrderTime(${order.id}, this.value)" 
                               placeholder="мин" class="w-14 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-center text-white" value="${order.estimated_time || ''}">
                        `}
                    </td>
                    <td class="text-center">
                        ${isFullyOOS ? '<div class="text-gray-500 opacity-50 text-[10px] line-through italic">Отменено</div>' : `
                        <button type="button" onclick="toggleStatus(${order.id}, 'qabyl')"
                                class="status-btn inline-flex items-center justify-center w-10 h-10 rounded-xl text-xl ${order.qabyl ? 'bg-emerald-600/30 text-emerald-400' : 'bg-red-600/20 text-red-400 hover:bg-red-600/30'}">
                            <i class="fas ${order.qabyl ? 'fa-check' : 'fa-hourglass-start'}"></i>
                        </button>
                        <div class="text-[10px] mt-1 font-medium ${order.qabyl ? 'text-emerald-400' : 'text-red-400'}">${order.qabyl ? 'Принят' : 'Ожидание'}</div>
                        `}
                    </td>
                    <td class="text-center">
                        ${isFullyOOS ? '<div class="text-gray-500 opacity-50 text-[10px] line-through italic">Отменено</div>' : `
                        <button type="button" onclick="toggleStatus(${order.id}, 'omoda')"
                                class="status-btn inline-flex items-center justify-center w-10 h-10 rounded-xl text-xl ${order.omoda ? 'bg-emerald-600/30 text-emerald-400' : 'bg-amber-600/30 text-amber-400 hover:bg-amber-600/40'}">
                            <i class="fas ${order.omoda ? 'fa-check' : 'fa-fire-burner'}"></i>
                        </button>
                        <div class="text-[10px] mt-1 font-medium ${order.omoda ? 'text-emerald-400' : 'text-amber-400'}">${order.omoda ? 'Готов' : 'Готовка'}</div>
                        `}
                    </td>
                    <td class="text-center">
                        ${(isFullyOOS || order.delivery_type !== 'delivery') ? '<span class="text-gray-600 text-xs">—</span>' : `
                            <div class="flex flex-col items-center">
                                <button type="button" onclick="toggleStatus(${order.id}, 'dostavka')"
                                        class="status-btn inline-flex items-center justify-center w-10 h-10 rounded-xl text-xl transition-all
                                        ${order.dostavka === 1 ? 'bg-blue-600 text-white scale-110' : /* This will be yellow in light mode */
                                          order.dostavka === 2 ? 'bg-emerald-600 text-white' :
                                          'bg-gray-700/30 text-gray-500 hover:bg-blue-600/20'}">
                                    <i class="fas ${order.dostavka === 1 ? 'fa-truck-fast' : order.dostavka === 2 ? 'fa-house-circle-check' : 'fa-truck'}"></i>
                                </button>
                                <div class="text-[9px] mt-1 font-bold uppercase tracking-tighter
                                    ${order.dostavka === 1 ? 'text-blue-400' : /* This will be yellow in light mode */
                                      order.dostavka === 2 ? 'text-emerald-400' : 
                                      'text-gray-500'}">
                                    ${order.dostavka === 1 ? 'В ПУТИ' : order.dostavka === 2 ? 'ДОСТАВЛЕН' : 'ОЖИДАНИЕ'}
                                </div>
                            </div>
                        `}
                    </td>
                    <td class="text-left min-w-[150px]">
                        ${order.delivery_type === 'delivery' ? `
                            <div class="flex flex-col gap-1 py-1">
                                ${order.delivery_address ? `<span class="text-[11px] font-bold text-white leading-tight break-words">${escapeHtml(order.delivery_address)}</span>` : ''}
                                ${order.delivery_latitude ? `
                                    <a href="https://www.google.com/maps?q=${order.delivery_latitude},${order.delivery_longitude}" target="_blank" class="flex items-center gap-1 text-[10px] text-blue-400 hover:text-blue-300">
                                        <i class="fas fa-location-dot text-red-600"></i> GPS Карта
                                    </a>
                                ` : ''}
                                ${(!order.delivery_address && !order.delivery_latitude) ? '<span class="text-red-500 text-[10px] font-bold italic">Адрес не указан</span>' : ''}
                            </div>
                        ` : '<span class="text-gray-600 text-xs">—</span>'}
                    </td>
                `;
                tbody.appendChild(row);
            });

            const showEmpty = list.length === 0;
            emptyEl.classList.toggle('hidden', !showEmpty);
            document.querySelector('#main-table').closest('.overflow-auto').classList.toggle('hidden', showEmpty);

            updateStats();
        }

        async function toggleFoodItem(orderId, currentFood, itemText) {
            const order = orders.find(o => o.id === orderId);
            if (!order) return;

            let items = currentFood.split(', ');
            let isStriking = !itemText.includes('<s>');
            let refundDiff = 0;

            // Тоза кардани ном ва ёфтани нархи воқеӣ
            const rawItem = itemText.replace(/<\/?s>/g, '').trim();
            let clean = rawItem.replace(/^\d+\.\s*/, ''); // Тоза кардани рақами тартибӣ
            
            let qty = 1;
            const qtyMatch = clean.match(/\s+x(\d+)$/);
            if (qtyMatch) {
                qty = parseInt(qtyMatch[1]);
                clean = clean.replace(/\s+x(\d+)$/, '');
            }

            let label = "";
            const labelMatch = clean.match(/\[(.*?)\]/);
            if (labelMatch) {
                label = labelMatch[1];
                clean = clean.replace(/\s*\[.*?\]/, '');
            }

            const foodInMenu = foods.find(f => f.name.toUpperCase() === clean.trim().toUpperCase());
            if (foodInMenu) {
                const prices = String(foodInMenu.price).split('/');
                let unitPrice = parseFloat(prices[0].replace(/[^0-9.]/g, ''));
                if ((label.toLowerCase().includes("больш") || label.toLowerCase().includes("калон")) && prices.length > 1) {
                    unitPrice = parseFloat(prices[1].replace(/[^0-9.]/g, ''));
                }
                if (!isNaN(unitPrice)) refundDiff = unitPrice * qty;
            }

            let newItems = items.map(it => {
                if (it === itemText) {
                    if (it.includes('<s>')) {
                        return it.replace('<s>', '').replace('</s>', '');
                    }
                    return `<s>${it}</s>`;
                }
                return it;
            });
            let newFullText = newItems.join(', ');
            let newRefund = (order.refund || 0) + (isStriking ? refundDiff : -refundDiff);
            if (newRefund < 0) newRefund = 0;

            await fetch('/api/orders/update-status', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ id: orderId, field: 'food', value: newFullText })
            });
            await fetch('/api/orders/update-status', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ id: orderId, field: 'refund', value: newRefund })
            });
            await fetch('/api/orders/update-status', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ id: orderId, field: 'out_of_stock', value: 1 })
            });
            
            if (order) { 
                order.khurok = newFullText; 
                order.out_of_stock = true; 
                order.refund = newRefund;
                saveOrders();
            }
            renderTable();
        }

        async function updateOrderTime(id, val) {
            const order = orders.find(o => o.id === id);
            if (order) {
                order.estimated_time = parseInt(val) || 0;
                saveOrders(); // Захира дар браузер (localStorage)
                // Фиристодан ба сервер барои нигоҳ доштан дар базаи маълумот
                try {
                    await fetch("/api/orders/update-status", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ id: id, field: 'estimated_time', value: order.estimated_time })
                    });
                } catch (e) {}
            }
        }

        function escapeHtml(s) {
            const d = document.createElement('div');
            d.textContent = s;
            return d.innerHTML;
        }

        async function toggleStatus(id, field) {
            const order = orders.find(o => o.id === id);
            if (!order) return;
            let nextValue;
            const body = { id: id, field: field };

            if (field === 'dostavka') {
                nextValue = (parseInt(order.dostavka) || 0) + 1;
                if (nextValue > 2) nextValue = 0; // 0: Ожидание -> 1: В пути -> 2: Доставлен -> 0
            } else {
                nextValue = !order[field];
            }
            body.value = nextValue;

            if (field === 'qabyl' && nextValue) {
                const tInp = document.getElementById(`time-${id}`);
                if (tInp && tInp.value) {
                    body.estimated_time = parseInt(tInp.value);
                    order.estimated_time = body.estimated_time;
                }
            }

            order[field] = nextValue;
            try {
                await fetch("/api/orders/update-status", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(body)
                });
            } catch (e) {}
            saveOrders();
            renderTable();
            
            // Тафтиши пурра иҷро шудани заказ (барои Доставка — бояд статус 2 шавад)
            const fullyDone = order.delivery_type === 'delivery' ? (order.qabyl && order.omoda && order.dostavka === 2) : (order.qabyl && order.omoda);
            if (fullyDone) {
                createConfetti();
                toast('Заказ полностью выполнен!');
            }
        }

        async function deleteOrder(id) {
            showConfirm('Удалить этот заказ?', async () => {
                try {
                    const res = await fetch(`/api/orders/delete/${id}`, { method: 'DELETE' });
                    const data = await res.json();
                    if (data.ok) {
                        orders = orders.filter(o => o.id !== id);
                        saveOrders();
                        renderTable();
                        toast('Заказ удален');
                    }
                } catch (e) { toast('Ошибка при удалении', true); }
            });
        }

        async function clearAllOrders() {
            showConfirm('Удалить ВСЕ заказы из базы?', async () => {
                try {
                    const res = await fetch('/api/orders/clear-all', { method: 'POST' });
                    if (res.ok) {
                        orders = [];
                        localStorage.removeItem(STORAGE_KEY);
                        lastSeenOrderId = 0;
                        renderTable();
                        toast('База очищена');
                    }
                } catch (e) { toast('Ошибка при очистке', true); }
            });
        }

        function createConfetti() {
            for (let i = 0; i < 50; i++) {
                const el = document.createElement('div');
                el.textContent = ['🍗','✅','⭐'][Math.floor(Math.random()*3)];
                el.style.cssText = 'position:fixed;left:'+(Math.random()*100)+'vw;top:-20px;font-size:20px;z-index:9999;pointer-events:none;';
                document.body.appendChild(el);
                el.animate(
                    [{ transform: 'translateY(0) rotate(0)' }, { transform: 'translateY('+(window.innerHeight+80)+'px) rotate('+(Math.random()*720)+'deg)' }],
                    { duration: 2000 + Math.random()*2000, easing: 'cubic-bezier(0.25,0.1,0.25,1)' }
                );
                setTimeout(() => el.remove(), 4000);
            }
        }

        function toggleTheme() {
            document.body.classList.toggle('light-mode');
            const isLight = document.body.classList.contains('light-mode');
            document.getElementById('theme-icon').className = isLight ? 'fas fa-sun' : 'fas fa-moon';
            localStorage.setItem('admin_theme', isLight ? 'light' : 'dark');
        }

        async function updateStats() {
            const totalEl = document.getElementById('total-orders');
            const pendingEl = document.getElementById('pending-accept');
            const cookingEl = document.getElementById('cooking-count');
            const readyEl = document.getElementById('ready-count');

            if (totalEl) totalEl.textContent = orders.length;
            if (pendingEl) pendingEl.textContent = orders.filter(o => !o.qabyl).length;
            if (cookingEl) cookingEl.textContent = orders.filter(o => o.qabyl && !o.omoda).length;
            if (readyEl) readyEl.textContent = orders.filter(o => o.omoda).length;
            
            // Гирифтани омори рӯзона аз Backend (Барои имрӯз ва таърих)
            try {
                const res = await fetch('/api/stats/daily-revenue');
                const data = await res.json();
                if (data.ok) {
                    window.dailyStatsHistory = data.stats;
                }
            } catch (e) {}
        }

        function showAddModal() {
            const m = document.getElementById('addModal');
            m.classList.remove('hidden');
            m.classList.add('flex');
            document.getElementById('modal-name').focus();
        }

        function hideAddModal() {
            const m = document.getElementById('addModal');
            m.classList.add('hidden');
            m.classList.remove('flex');
        }

        function showHistory() {
            if (isAuthorized) {
                renderHistoryData();
                return;
            }
            accessTarget = 'history';
            const m = document.getElementById('passwordModal');
            m.classList.remove('hidden');
            m.classList.add('flex');
            document.getElementById('history-access-code').value = '';
            setTimeout(() => document.getElementById('history-access-code').focus(), 100);
        }

        function hidePasswordModal() {
            document.getElementById('passwordModal').classList.add('hidden');
            document.getElementById('passwordModal').classList.remove('flex');
        }

        function showFullHistory() {
            if (isAuthorized) {
                renderFullHistory();
                return;
            }
            accessTarget = 'full-history';
            const m = document.getElementById('passwordModal');
            m.classList.remove('hidden');
            m.classList.add('flex');
            document.getElementById('history-access-code').value = '';
            setTimeout(() => document.getElementById('history-access-code').focus(), 100);
        }

        function hideFullHistoryModal() {
            document.getElementById('fullHistoryModal').classList.add('hidden');
            document.getElementById('fullHistoryModal').classList.remove('flex');
        }

        async function renderFullHistory() {
            try {
                const res = await fetch('/api/orders/full-history');
                const data = await res.json();
                const tbody = document.getElementById('full-history-table-body');
                tbody.innerHTML = '';
                
                if (data.ok) {
                    data.history.reverse().forEach(h => {
                        tbody.innerHTML += `
                            <tr class="hover:bg-gray-50 transition-colors">
                                <td class="px-6 py-4 text-xs font-mono text-gray-500">${h.created}</td>
                                <td class="px-6 py-4 text-sm font-bold text-gray-900 whitespace-nowrap">${escapeHtml(h.customer)}</td>
                                <td class="px-6 py-4 text-sm font-semibold text-blue-600">${escapeHtml(h.phone)}</td>
                                <td class="px-6 py-4 text-sm text-gray-700 whitespace-nowrap">${escapeHtml(h.food)}</td>
                                <td class="px-6 py-4 text-sm font-black text-emerald-600">${escapeHtml(h.price)} смн</td>
                                <td class="px-6 py-4 text-[10px] font-bold uppercase text-gray-400">
                                    ${h.delivery_type === 'delivery' ? '🚛 Доставка' : '🛍️ Самовывоз'}
                                    <div class="opacity-60">${h.payment_method === 'cash' ? '💵 Наличные' : '💳 Онлайн'}</div>
                                </td>
                            </tr>`;
                    });
                    const m = document.getElementById('fullHistoryModal');
                    m.classList.remove('hidden');
                    m.classList.add('flex');
                }
            } catch (e) { toast('Ошибка при загрузке истории', true); }
        }

        async function clearFullHistory() {
            showConfirm('Вы уверены, что хотите очистить ПОЛНУЮ ИСТОРИЮ?', async () => {
                const res = await fetch('/api/orders/clear-full-history', { method: 'POST' });
                if ((await res.json()).ok) { hideFullHistoryModal(); toast('История очищена'); }
            });
        }

        async function verifyHistoryCode() {
            const code = document.getElementById('history-access-code').value;
            
            const res = await fetch('/api/settings/get?key=admin_password');
            const data = await res.json();
            const correctCode = data.val || "159951.tfc";

            if (code !== correctCode) {
                toast("Неверный код доступа!", true);
                return;
            }
            hidePasswordModal();
            isAuthorized = true;
            
            if (accessTarget === 'history') {
                renderHistoryData();
            } else if (accessTarget === 'full-history') {
                renderFullHistory();
            } else if (accessTarget === 'popular-foods') {
                renderPopularFoods();
            } else if (accessTarget) {
                actualSwitchTab(accessTarget);
            }
        }

        async function changeAdminPassword() {
            document.getElementById('old-pass-input').value = '';
            document.getElementById('new-pass-input').value = '';
            const m = document.getElementById('changePasswordModal');
            m.classList.remove('hidden');
            m.classList.add('flex');
            setTimeout(() => document.getElementById('old-pass-input').focus(), 100);
        }

        function hideChangePasswordModal() {
            document.getElementById('changePasswordModal').classList.add('hidden');
            document.getElementById('changePasswordModal').classList.remove('flex');
        }

        async function submitPasswordChange() {
            const oldPass = document.getElementById('old-pass-input').value;
            const newPass = document.getElementById('new-pass-input').value;

            const res = await fetch('/api/settings/get?key=admin_password');
            const data = await res.json();
            const currentStored = data.val || "159951.tfc";

            if (oldPass !== currentStored) {
                toast("Неверный текущий пароль!", true);
                return;
            }
            if (!newPass.trim()) {
                toast("Пароль не может быть пустым!", true);
                return;
            }

            const confirmRes = await fetch('/api/settings/set', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({key: 'admin_password', val: newPass.trim()})
            });
            
            if ((await confirmRes.json()).ok) {
                toast("Пароль успешно изменен!");
                hideChangePasswordModal();
            } else {
                toast("Ошибка при смене пароля", true);
            }
        }

        async function renderHistoryData() {
            // Даъват кардани маълумоти нав аз сервер
            const res = await fetch('/api/stats/daily-revenue');
            const data = await res.json();
            const stats = (data.ok ? data.stats : []).reverse(); // Аз кӯҳна ба нав барои график

            const tbody = document.getElementById('history-table-body');
            tbody.innerHTML = '';
            let grandTotal = 0;
            let grandCustomers = 0;
            
            const labels = [];
            const values = [];

            stats.forEach((s, idx) => {
                grandTotal += s.total;
                grandCustomers += (s.count || 0);
                labels.push(s.day);
                values.push(s.total);
                
                tbody.innerHTML += `
                    <tr class="hover:bg-slate-800/30 transition-colors">
                        <td class="px-6 py-4 font-mono text-sm">${s.day}</td>
                        <td class="px-6 py-4 text-blue-400 font-bold">${s.count || 0} чел.</td>
                        <td class="px-6 py-4 text-right font-bold text-emerald-400">+ ${s.total} смн</td>
                    </tr>`;
            });
            document.getElementById('grand-total-display').textContent = grandTotal.toFixed(0) + ' смн';
            document.getElementById('grand-customers-display').textContent = grandCustomers + ' чел.';

            const m = document.getElementById('historyModal');
            m.classList.remove('hidden');
            m.classList.add('flex');

            // Сохтани график
            setTimeout(() => renderTradingChart(labels, values), 100);
        }

        function renderTradingChart(labels, data) {
            const ctx = document.getElementById('tradingChart').getContext('2d');
            if (revenueChart) revenueChart.destroy();

            const gradient = ctx.createLinearGradient(0, 0, 0, 300);
            gradient.addColorStop(0, 'rgba(16, 185, 129, 0.4)');
            gradient.addColorStop(1, 'rgba(16, 185, 129, 0)');

            revenueChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Выручка (смн)',
                        data: data,
                        borderColor: '#10b981',
                        borderWidth: 4,
                        pointBackgroundColor: '#10b981',
                        pointRadius: 5,
                        fill: true,
                        backgroundColor: gradient,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { grid: { color: '#334155' }, ticks: { color: '#94a3b8' } },
                        x: { grid: { display: false }, ticks: { color: '#94a3b8' } }
                    }
                }
            });
        }

        function hideHistoryModal() {
            document.getElementById('historyModal').classList.add('hidden');
            document.getElementById('historyModal').classList.remove('flex');
        }

        async function clearHistory() {
            showConfirm('Очистить ВСЮ историю доходов?', async () => {
                try {
                    const res = await fetch('/api/stats/clear-history', { method: 'POST' });
                    const data = await res.json();
                    if (data.ok) {
                        toast('История доходов полностью очищена');
                        hideHistoryModal();
                    }
                } catch (e) { toast('Ошибка при очистке истории', true); }
            });
        }

        function addNewOrder() {
            const name = document.getElementById('modal-name').value.trim();
            const food = document.getElementById('modal-food').value.trim();
            const price = document.getElementById('modal-price').value.trim();
            if (!name || !food || !price) {
                toast('Заполните все поля', true);
                return;
            }
            const newId = orders.length ? Math.max(...orders.map(o => o.id)) + 1 : 1;
            orders.unshift({ id: newId, nom: name, mijoz_id: '', khurok: food, pul: price, qabyl: false, omoda: false });
            saveOrders();
            hideAddModal();
            document.getElementById('modal-name').value = '';
            document.getElementById('modal-food').value = '';
            document.getElementById('modal-price').value = '';
            renderTable();
            toast('Заказ добавлен');
        }

        function showPopularFoods() {
            if (isAuthorized) {
                renderPopularFoods();
                return;
            }
            accessTarget = 'popular-foods';
            const m = document.getElementById('passwordModal');
            m.classList.remove('hidden');
            m.classList.add('flex');
            document.getElementById('history-access-code').value = '';
            setTimeout(() => document.getElementById('history-access-code').focus(), 100);
        }

        function hidePopularFoodsModal() {
            document.getElementById('popularFoodsModal').classList.add('hidden');
            document.getElementById('popularFoodsModal').classList.remove('flex');
        }

        async function renderPopularFoods() {
            try {
                const res = await fetch('/api/stats/popular-foods');
                const data = await res.json();
                const tbody = document.getElementById('popular-foods-table-body');
                tbody.innerHTML = '';
                if (data.ok) {
                    data.stats.forEach(s => {
                        tbody.innerHTML += `
                            <tr class="hover:bg-gray-50 transition-colors">
                                <td class="px-6 py-4 text-sm font-bold text-gray-900">${escapeHtml(s.food)}</td>
                                <td class="px-6 py-4 text-sm text-center font-semibold text-blue-600">${s.count} шт.</td>
                                <td class="px-6 py-4 text-sm text-right font-black text-emerald-600">${s.total.toFixed(2)} смн</td>
                            </tr>`;
                    });

                    const m = document.getElementById('popularFoodsModal');
                    m.classList.remove('hidden');
                    m.classList.add('flex');
                }
            } catch (e) { toast('Ошибка в загрузке статистики', true); }
        }

        function exportCsv() {
            const rows = [['№','Ном','ID','Хӯрок','Пул (сом)','Қабул','Омода']];
            orders.forEach(o => {
                rows.push([o.id, o.nom, o.mijoz_id || '', o.khurok, o.pul, o.qabyl ? 'ҳа' : 'не', o.omoda ? 'ҳа' : 'не']);
            });
            const NL = String.fromCharCode(10);
            const csv = rows.map(r => r.map(c => '"' + String(c).replace(/"/g,'""') + '"').join(',')).join(NL);
            const blob = new Blob([String.fromCharCode(0xfeff) + csv], { type: 'text/csv;charset=utf-8;' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = 'tfc_orders_' + new Date().toISOString().slice(0,10) + '.csv';
            a.click();
            URL.revokeObjectURL(a.href);
            toast('Файл CSV скачан');
        }

        function toast(msg, err) {
            const host = document.getElementById('toast-host');
            const t = document.createElement('div');
            t.className = 'toast';
            if (err) t.style.background = '#b91c1c';
            t.textContent = msg;
            host.appendChild(t);
            setTimeout(() => { t.remove(); }, 6000);
        }

        let sessionStart = Date.now();
        function updateClock() {
            const timeEl = document.getElementById('current-time');
            setInterval(() => {
                const diff = Math.floor((Date.now() - sessionStart) / 1000);
                const h = Math.floor(diff / 3600).toString().padStart(2, '0');
                const m = Math.floor((diff % 3600) / 60).toString().padStart(2, '0');
                const s = (diff % 60).toString().padStart(2, '0');
                timeEl.textContent = `Смена: ${h}:${m}:${s}`;
            }, 1000);
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                hideAddModal();
                hidePasswordModal();
            }
        });

        window.onload = function() {
            if (localStorage.getItem('admin_theme') === 'light') {
                document.body.classList.add('light-mode');
                const icon = document.getElementById('theme-icon');
                if (icon) icon.className = 'fas fa-sun';
            }

            // Таъхири кӯтоҳ (300мс) барои нест кардани маълумоте, ки браузер худаш пур мекунад
            setTimeout(() => {
                if(document.getElementById('admin-order-search')) document.getElementById('admin-order-search').value = '';
                if(document.getElementById('admin-food-search')) document.getElementById('admin-food-search').value = '';
            }, 300);

            loadFoods(); // Бояд менюро бор кунем, то нархҳоро донем
            loadOrders();
            renderTable();
            updateClock();
            setFilter('all');
            
            // Вақте ки корбар бори аввал ба экран клик мекунад, барнома ба ҳолати албомӣ мегузарад
            document.addEventListener('click', enableGameMode);
            document.addEventListener('touchstart', enableGameMode);

            // Live notifications from menu website
            startLivePolling();

            // Илова кардани скаролл барои дидани майдон ҳангоми пайдо шудани клавиатура
            document.addEventListener('focusin', (e) => {
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                    setTimeout(() => {
                        e.target.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }, 300);
                }
            });
        };

        async function startLivePolling() {
            try {
                await fetchNewOrders(true);
            } catch (e) {}

            setInterval(() => {
                fetchNewOrders(false).catch(() => {});
            }, 1000);
        }

        async function fetchNewOrders(isInitial) {
            // Танҳо як бор fetch мекунем бо истифодаи lastSeenOrderId
            const res = await fetch(`/api/orders/since?last_id=${lastSeenOrderId}`, { cache: 'no-store' });
            if (!res.ok) return;
            const data = await res.json();
            const newOrders = Array.isArray(data.orders) ? data.orders : [];
            if (newOrders.length === 0) return;

            // Филтр кардани танҳо заказҳои воқеан нав
            const trulyNewOrders = newOrders.filter(o => !orders.some(existing => existing.id === o.id));
            if (trulyNewOrders.length === 0) return;

            for (const o of trulyNewOrders) {
                orders.unshift({
                    id: o.id,
                    nom: o.customer,
                    mijoz_id: o.customer_id || '',
                    khurok: o.food,
                    pul: o.price,
                    phone: o.phone || '',
                    delivery_type: o.delivery_type || 'pickup',
                    qabyl: !!o.qabyl,
                    omoda: !!o.omoda,
                    dostavka: parseInt(o.dostavka) || 0,
                    out_of_stock: !!o.out_of_stock,
                    refund: o.refund || 0,
                    delivery_latitude: o.delivery_latitude || '',
                    delivery_longitude: o.delivery_longitude || '',
                    delivery_address: o.delivery_address || '',
                    estimated_time: o.estimated_time || 0,
                    payment_method: o.payment_method || 'online',
                    tip: o.tip || ''
                });
                if (o.id > lastSeenOrderId) lastSeenOrderId = o.id;
            }

            renderTable();

            // Хабарнома (Toast) танҳо барои заказҳои нав ва агар боркунии аввалия набошад
            if (!isInitial) {
                const last = trulyNewOrders[trulyNewOrders.length - 1];
                const idPart = last.customer_id ? ` [${last.customer_id}]` : '';
                const typeStr = last.delivery_type === 'delivery' ? 'ДОСТАВКА' : 'САМОВЫВОЗ';
                
                newOrderSound.play().catch(e => console.warn("Audio play blocked:", e));

                toast(`Новый заказ (${typeStr}) от ${last.phone || 'без номера'}! ${last.customer}`);
            }
        }

        // TAB SWITCHING
        function switchTab(tabName) {
            if (tabName === 'orders' || isAuthorized) {
                actualSwitchTab(tabName);
                return;
            }
            accessTarget = tabName;
            const m = document.getElementById('passwordModal');
            m.classList.remove('hidden');
            m.classList.add('flex');
            document.getElementById('history-access-code').value = '';
            setTimeout(() => document.getElementById('history-access-code').focus(), 100);
        }

        function actualSwitchTab(tabName) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            
            const contentEl = document.getElementById(tabName + '-section');
            const btnEl = document.getElementById(tabName + '-tab-btn');
            if (contentEl) contentEl.classList.remove('hidden');
            if (btnEl) btnEl.classList.add('active');
            
            if (tabName === 'foods') {
                loadFoods();
            }
            if (tabName === 'vakansii') {
                loadVakansii();
            }
            if (tabName === 'aktsii') {
                loadAktsii();
            }
        }

        const subcategoriesMap = {
            'Меню': ['Паста', 'Салаты', 'Супы', 'Горячие блюда', 'Десерты', 'Напитки'],
            'Фастфуд': ['Хот-доги', 'Бургеры', 'Тортильи', 'Сэндвичи', 'Гарниры'],
            'Суши': ['Суши', 'Роллы'],
            'Пицца': ['Пицца', 'Хачапури'],
            'Летнее меню': ['Смузи', 'Мохито', 'Холодок'],
            'Комбо': ['Комбо']
        };

        function updateSubcategories() {
            const cat = document.getElementById('food-modal-category').value;
            const subContainer = document.getElementById('food-modal-subcategory-container');
            const subSelect = document.getElementById('food-modal-subcategory');
            
            const subs = subcategoriesMap[cat] || [];
            subSelect.innerHTML = '';
            
            if (subs.length > 0) {
                subContainer.classList.remove('hidden');
                subs.forEach(s => {
                    const opt = document.createElement('option');
                    opt.value = s;
                    opt.textContent = s;
                    subSelect.appendChild(opt);
                });
            } else {
                subContainer.classList.add('hidden');
            }
        }

        let foods = [];
        let foodsFilterCategory = 'all';
        let foodsFilterSubcategory = 'all';

        function updateFoodsSubcategoryControls() {
            const select = document.getElementById('foods-subcategory-select');
            const label = document.getElementById('foods-subcategory-label');
            const subs = subcategoriesMap[foodsFilterCategory] || [];

            select.innerHTML = '<option value="all">Все</option>';
            if (foodsFilterCategory !== 'all' && subs.length > 0) {
                subs.forEach(s => {
                    const opt = document.createElement('option');
                    opt.value = s;
                    opt.textContent = s;
                    select.appendChild(opt);
                });
                label.classList.remove('hidden');
                select.classList.remove('hidden');
            } else {
                label.classList.add('hidden');
                select.classList.add('hidden');
            }
        }

        async function loadFoods() {
            try {
                const response = await fetch('/api/foods/list');
                const data = await response.json();
                foods = Array.isArray(data.foods) ? data.foods : [];
            } catch (e) {
                toast('Ошибка при загрузке меню', true);
            }
            updateFoodsSubcategoryControls();
            renderFoodsTable();
        }

        function applyFoodsFilter() {
            renderFoodsTable();
        }

        function setFoodsCategory(category) {
            foodsFilterCategory = category;
            foodsFilterSubcategory = 'all';
            updateFoodsSubcategoryControls();
            document.querySelectorAll('.food-category-chip[data-category]').forEach(btn => {
                const btnCategory = btn.getAttribute('data-category');
                if (btnCategory === category) {
                    btn.classList.add('bg-gray-900', 'text-white');
                    btn.classList.remove('bg-gray-700', 'text-gray-200');
                } else {
                    btn.classList.remove('bg-gray-900', 'text-white');
                    btn.classList.add('bg-gray-700', 'text-gray-200');
                }
            });
            renderFoodsTable();
        }

        function setFoodsSubcategory(subcategory) {
            foodsFilterSubcategory = subcategory;
            renderFoodsTable();
        }

        function matchesSubcategory(food, subcategory) {
            const selected = subcategory.toLowerCase();
            const foodSub = (food.subcategory || '').toLowerCase();
            const name = (food.name || '').toUpperCase();

            if (foodSub) {
                return foodSub === selected;
            }

            if (foodsFilterCategory === 'Меню') {
                if (selected === 'паста') return name.includes('ПАСТА') || name.includes('ГНЁЗДА');
                if (selected === 'салаты') return name.includes('САЛАТ') || name.includes('БАКЛАЖАН') || name.includes('ГРЕЧЕСКИЙ');
                if (selected === 'супы') return name.includes('СУП') || name.includes('БОРЩ') || name.includes('ЛАГМАН') || name.includes('ЧАХОВ') || name.includes('МЕРДЖИМЕК');
                if (selected === 'горячие блюда') return name.includes('СТЕКС') || name.includes('КОТЛЕТ') || name.includes('ЖАРОВНЯ') || name.includes('ТАБАКА') || name.includes('СТЕЙК') || name.includes('КОРЕЙКА') || name.includes('КАБOБ') || name.includes('ФОРЕЛИ');
                if (selected === 'десерты') return name.includes('ЧИЗКЕЙК') || name.includes('РАФАЭЛЛО') || name.includes('НАПОЛЕОН') || name.includes('ТИРАМИСУ') || name.includes('ФРУКТОВАЯ') || name.includes('КЕШЬЮ') || name.includes('ФИСТАШКИ');
                if (selected === 'напитки') return name.includes('АМЕРИКАНО') || name.includes('КАПУЧИН') || name.includes('ЛАТТЕ') || name.includes('ЭСПРЕССО') || name.includes('ЧАЙ') || name.includes('АЙРАН') || name.includes('МОХИТО');
            }
            if (foodsFilterCategory === 'Фастфуд') {
                if (selected === 'хот-доги') return name.includes('ДОГ') || name.includes('БУЛОЧКА');
                if (selected === 'бургеры') return name.includes('БУРГЕР');
                if (selected === 'тортильи') return name.includes('ТОРТИЛЬЯ');
                if (selected === 'сэндвичи') return name.includes('СЭНДВИЧ') || name.includes('ПАНИНИ');
                if (selected === 'гарниры') return name.includes('КАРТО') || name.includes('НАГГЕТС') || name.includes('КРЫЛЫШКИ') || name.includes('НОЖКИ') || name.includes('ПАЛОЧКИ') || name.includes('БАСКЕТ');
            }
            if (foodsFilterCategory === 'Суши') {
                if (selected === 'суши') return name.includes('СУШИ') && !name.includes('РОЛЛ') && !name.includes('МАКИ') && !name.includes('ТЕМПУРА') && !name.includes('СЕТ');
                if (selected === 'роллы') return name.includes('РОЛЛ') || name.includes('МАКИ') || name.includes('КАЛИФОРНИЯ') || name.includes('ТЕМПУРА') || name.includes('СЕТ') || name.includes('ЗАПЕЧЕН');
            }
            if (foodsFilterCategory === 'Летнее меню') {
                if (selected === 'смузи') return name.includes('СМУЗИ');
                if (selected === 'мохито') return name.includes('МОХИТО');
                if (selected === 'холодок') return name.includes('АЙРАН') || name.includes('ОКРОШКА');
            }
            if (foodsFilterCategory === 'Пицца') return selected === 'пицца' || selected === 'хачапури';
            if (foodsFilterCategory === 'Комбо') return selected === 'комбо';

            return false;
        }

        function filteredFoods() {
            const q = (document.getElementById('foods-search-input')?.value || '').trim().toLowerCase();
            let list = foods.filter(f => {
                if (!q) return true;
                return f.name.toLowerCase().includes(q);
            });
            list = list.filter(f => {
                if (foodsFilterCategory === 'all') {
                    // Скрываем Вакансии и Отзывы из общего списка блюд
                    return f.category !== 'Вакансии' && f.category !== 'Otziv';
                }
                if (f.category !== foodsFilterCategory) return false;
                if (foodsFilterSubcategory === 'all') return true;
                return matchesSubcategory(f, foodsFilterSubcategory);
            });
            return list;
        }

        function renderFoodsTable() {
            const tbody = document.getElementById('foods-table-body');
            const emptyEl = document.getElementById('empty-foods-state');
            const list = filteredFoods();
            tbody.innerHTML = '';

            list.forEach((food, index) => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td class="font-mono text-gray-500">${index + 1}</td>
                    <td class="font-semibold text-white">${escapeHtml(food.name)}</td>
                    <td class="text-gray-400 text-sm">${escapeHtml(food.category)} <br> <span class="text-[10px] text-gray-500 font-bold">${escapeHtml(food.subcategory || '')}</span></td>
                    <td class="font-semibold text-emerald-400 tabular-nums">${escapeHtml(food.price)} сом</td>
                    <td class="text-gray-400 text-xs">${escapeHtml(food.image_url || '—')}</td>
                    <td class="text-gray-300 text-xs whitespace-pre-wrap max-w-xs">${escapeHtml(food.description || '—')}</td>
                    <td class="text-center space-x-2 flex items-center justify-center">
                        <button type="button" onclick="editFood(${food.id})" class="inline-flex items-center justify-center w-9 h-9 rounded-lg bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 transition-colors" title="Изменить">
                            <i class="fas fa-edit"></i> <!-- This will be yellow in light mode -->
                        </button>
                        <button type="button" onclick="deleteFood(${food.id})" class="inline-flex items-center justify-center w-9 h-9 rounded-lg text-gray-500 hover:bg-red-600/20 hover:text-red-400 transition-colors" title="Удалить">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </td>
                `;
                tbody.appendChild(row);
            });

            const showEmpty = list.length === 0;
            emptyEl.classList.toggle('hidden', !showEmpty);
            document.querySelector('#foods-table').closest('.overflow-auto').classList.toggle('hidden', showEmpty);
        }

        // VAKANSII MANAGEMENT
        async function loadVakansii() {
            await loadFoods();
            const tbody = document.getElementById('vakansii-table-body');
            tbody.innerHTML = '';
            const list = foods.filter(f => f.category === 'Вакансии');
            list.forEach(v => {
                tbody.innerHTML += `
                    <tr>
                        <td class="text-white font-semibold">${v.name}</td>
                        <td class="text-yellow-500 font-bold">${v.price}</td>
                        <td class="text-gray-400 text-xs max-w-xs truncate">${v.description || '—'}</td>
                        <td class="text-center">
                            <button onclick="editFood(${v.id})" class="text-blue-400 mr-3"><i class="fas fa-edit"></i></button>
                            <button onclick="deleteFood(${v.id})" class="text-red-400"><i class="fas fa-trash"></i></button>
                        </td>
                    </tr>`;
            });
        }

        // AKTSII MANAGEMENT
        let aktsii = [];
        async function loadAktsii() {
            try {
                const res = await fetch('/api/aktsii/list');
                const data = await res.json();
                aktsii = data.aktsii || [];
                renderAktsii();
            } catch (e) { toast('Ошибка при загрузке акций', true); }
        }

        function renderAktsii() {
            const tbody = document.getElementById('aktsii-table-body');
            tbody.innerHTML = '';
            aktsii.forEach(a => {
                tbody.innerHTML += `
                    <tr>
                        <td class="text-white text-sm py-4">${a.image_url ? `<div class="flex items-center gap-3"><img src="/static/images/${escapeHtml(a.image_url)}" class="h-12 w-12 rounded-xl object-cover border border-gray-700" alt="Акция"/><span>${escapeHtml(a.title)}</span></div>` : escapeHtml(a.title)}</td>
                        <td class="text-gray-200 text-sm py-4">${escapeHtml(a.price)}</td>
                        <td class="text-white text-sm whitespace-pre-wrap py-4">${escapeHtml(a.description)}</td>
                        <td class="text-gray-500 text-xs">${escapeHtml(a.created.split(' ')[0])}</td>
                        <td class="text-center">
                            <button onclick="deleteAktsii(${a.id})" class="text-red-400 hover:text-red-300"><i class="fas fa-trash"></i></button>
                        </td>
                    </tr>`;
            });
        }

        function showAddAktsiiModal() {
            showAddFoodModal();
            document.getElementById('food-modal-category').value = 'AktsiiInternal';
            document.getElementById('food-modal-title').textContent = 'Новая акция';
            document.getElementById('label-food-name').textContent = 'Заголовок акции';
            document.getElementById('label-food-price').textContent = 'Цена / скидка';
            document.getElementById('food-modal-name').placeholder = 'Например: Скидка 20% на пиццу';
            document.getElementById('food-modal-price').placeholder = 'Например: 99/149';
            document.getElementById('food-modal-description').placeholder = 'Подробно: условия, срок действия, контакты';
            document.getElementById('food-modal-submit-btn').onclick = saveAktsii;
            document.getElementById('food-modal-category-container').classList.add('hidden');
            document.getElementById('food-modal-desc-container').classList.remove('hidden');
            document.getElementById('food-modal-subcategory-container').classList.add('hidden');
        }

        async function saveAktsii() {
            const title = document.getElementById('food-modal-name').value.trim();
            const price = document.getElementById('food-modal-price').value.trim();
            const desc = document.getElementById('food-modal-description').value.trim();
            const fileInput = document.getElementById('food-modal-file');

            if (!title || !price || !desc) { toast('Заполните заголовок, цену и текст акции', true); return; }

            const foodSubmitBtn = document.getElementById('food-modal-submit-btn');
            foodSubmitBtn.disabled = true;

            const formData = new FormData();
            formData.append('title', title);
            formData.append('price', price);
            formData.append('description', desc);
            if (fileInput.files[0]) {
                formData.append('image', fileInput.files[0]);
            }

            const res = await fetch('/api/aktsii/add', { method: 'POST', body: formData });
            const data = await res.json();
            foodSubmitBtn.disabled = false;
            
            if (data.ok) { 
                hideAddFoodModal(); 
                loadAktsii(); 
                toast('Акция добавлена'); 
            } else {
                toast('Ошибка при сохранении', true);
            }
        }

        async function deleteAktsii(id) {
            showConfirm('Удалить эту акцию?', async () => {
                const res = await fetch(`/api/aktsii/delete/${id}`, { method: 'DELETE' });
                if ((await res.json()).ok) { loadAktsii(); toast('Акция удалена'); }
            });
        }

        function showAddFoodModal() {
            document.getElementById('food-modal-id').value = '';
            document.getElementById('food-modal-title').textContent = 'Новое блюдо';
            document.getElementById('food-modal-submit-btn').onclick = saveFood;
            // Показ полей, которые были скрыты для акции
            document.getElementById('food-modal-name').parentElement.classList.remove('hidden');
            document.getElementById('food-modal-price').parentElement.parentElement.classList.remove('hidden');
            document.getElementById('food-modal-file').parentElement.classList.remove('hidden');

            document.getElementById('food-modal-name').value = '';
            document.getElementById('food-modal-category').value = 'Меню';
            document.getElementById('food-modal-subcategory').value = ''; // Reset subcategory value
            updateSubcategories();
            document.getElementById('food-modal-price').value = '';
            document.getElementById('food-modal-image').value = '';
            document.getElementById('food-modal-file').value = '';
            document.getElementById('food-modal-description').value = '';
            document.getElementById('label-food-name').textContent = 'Название блюда';
            document.getElementById('label-food-price').textContent = 'Цена (сом)';
            document.getElementById('food-modal-submit-btn').textContent = 'Создать';
            document.getElementById('food-modal-category-container').classList.remove('hidden');
            document.getElementById('food-modal-desc-container').classList.remove('hidden'); // Show description by default for new food
            const m = document.getElementById('addFoodModal');
            m.classList.remove('hidden');
            m.classList.add('flex');
            document.getElementById('food-modal-name').focus();
        }

        function showAddVakansiiModal(isEdit = false) {
            if (!isEdit) {
                showAddFoodModal();
            }
            document.getElementById('food-modal-category').value = 'Вакансии';
            document.getElementById('food-modal-title').textContent = isEdit ? 'Редактировать вакансию' : 'Новая вакансия';
            document.getElementById('label-food-name').textContent = 'Заголовок вакансии';
            document.getElementById('label-food-price').textContent = 'Зарплата';
            document.getElementById('food-modal-name').placeholder = 'Например: Менеджер по продажам';
            document.getElementById('food-modal-price').placeholder = 'Например: 800-1200';
            document.getElementById('food-modal-description').placeholder = 'Подробная информация: требования, условия, контакты';
            document.getElementById('food-modal-submit-btn').textContent = isEdit ? 'Сохранить' : 'Создать';
            document.getElementById('food-modal-category-container').classList.add('hidden');
            document.getElementById('food-modal-desc-container').classList.remove('hidden');
            document.getElementById('food-modal-subcategory-container').classList.add('hidden');

            const m = document.getElementById('addFoodModal');
            m.classList.remove('hidden'); m.classList.add('flex');
        }

        function editFood(foodId) {
            const food = foods.find(f => f.id === foodId);
            if (!food) return;
            document.getElementById('food-modal-id').value = food.id;
            document.getElementById('food-modal-title').textContent = 'Редактировать блюдо';
            document.getElementById('food-modal-name').value = food.name;
            document.getElementById('food-modal-category').value = food.category;
            updateSubcategories();
            document.getElementById('food-modal-subcategory').value = food.subcategory || '';
            document.getElementById('food-modal-price').value = food.price;
            document.getElementById('food-modal-image').value = food.image_url || '';
            document.getElementById('food-modal-file').value = '';
            document.getElementById('food-modal-description').value = food.description || '';
            
            if (food.category === 'Вакансии') {
                showAddVakansiiModal(true);
            } else {
                document.getElementById('food-modal-category-container').classList.remove('hidden');
                document.getElementById('food-modal-desc-container').classList.remove('hidden');
                document.getElementById('food-modal-submit-btn').textContent = 'Сохранить';
            }

            const m = document.getElementById('addFoodModal');
            m.classList.remove('hidden');
            m.classList.add('flex');
            document.getElementById('food-modal-name').focus();
        }

        function hideAddFoodModal() {
            const m = document.getElementById('addFoodModal');
            m.classList.add('hidden');
            m.classList.remove('flex');
        }

        async function saveFood() {
            const id = document.getElementById('food-modal-id').value.trim();
            const name = document.getElementById('food-modal-name').value.trim();
            const category = document.getElementById('food-modal-category').value.trim();
            const subcategory = document.getElementById('food-modal-subcategory').value.trim();
            const price = document.getElementById('food-modal-price').value.trim();
            const existing_image = document.getElementById('food-modal-image').value.trim();
            const description = document.getElementById('food-modal-description').value.trim();
            const fileInput = document.getElementById('food-modal-file');

            if (!name || !price) {
                toast('Заполните все поля', true);
                return;
            }

            const formData = new FormData();
            formData.append('name', name);
            formData.append('category', category);
            formData.append('subcategory', subcategory);
            formData.append('price', price);
            formData.append('description', description);
            formData.append('image_url', existing_image);

            if (fileInput.files[0]) {
                formData.append('image', fileInput.files[0]);
            }

            const method = id ? 'PUT' : 'POST';
            const url = id ? `/api/foods/update/${id}` : '/api/foods/add';

            try {
                const response = await fetch(url, {
                    method: method,
                    body: formData
                });
                const data = await response.json();
                if (data.ok) {
                    hideAddFoodModal();
                    loadFoods();
                    if (category === 'Вакансии') {
                        toast(id ? 'Данные обновлены' : 'Вакансия добавлена');
                    } else {
                        toast(id ? 'Блюдо обновлено' : 'Блюдо добавлено');
                    }
                } else {
                    const errMap = { 'duplicate_name': 'Это название уже существует', 'missing_fields': 'Заполните поля' };
                    toast('Ошибка: ' + (errMap[data.error] || data.error || 'Неизвестная ошибка'), true);
                }
            } catch (e) {
                console.error(e);
                toast('Ошибка при создании', true);
            }
        }

        async function deleteFood(foodId) {
            const food = foods.find(f => f.id === foodId);
            const isVakansiya = food && food.category === 'Вакансии';
            const confirmMsg = isVakansiya ? 'Удалить эту вакансию?' : 'Удалить это блюдо?';
            
            showConfirm(confirmMsg, async () => {
                try {
                    const response = await fetch(`/api/foods/delete/${foodId}`, {
                        method: 'DELETE',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    const data = await response.json();
                    if (data.ok) {
                        isVakansiya ? loadVakansii() : loadFoods();
                        toast(isVakansiya ? 'Вакансия удалена' : 'Блюдо удалено');
                    } else {
                        toast('Ошибка при удалении', true);
                    }
                } catch (e) {
                    toast('Ошибка при удалении', true);
                }
            });
        }
    </script>
</body>
</html>"""

@app.route('/')
def admin_panel():
    return render_template_string(HTML)

@app.route('/admin_manifest.json')
def serve_admin_manifest():
    # Ин файлро аз папкаи асосӣ мехонем, на аз static
    return send_from_directory('.', 'admin_manifest.json')

@app.after_request
def add_cors_headers(resp):
    # Allow menu website (other port) to send orders
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@app.route("/api/external/sync", methods=["POST"])
def api_external_sync():
    """Қабули маълумот аз Client (app.py) тавассути API"""
    if request.headers.get("X-API-KEY") != API_KEY:
        return jsonify({"ok": False, "error": "Unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    sync_type = data.get("sync_type") # 'order' ё 'customer'

    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()

    try:
        if sync_type == "order":
            customer = data.get("customer", "Неизвестно")
            customer_id = data.get("customer_id", "")
            food = data.get("food", "Блюдо")
            price = data.get("price", "0")
            phone = data.get("phone", "")
            delivery_type = data.get("delivery_type", "pickup")
            delivery_address = data.get("delivery_address", "")
            payment_method = data.get("payment_method", "online")
            tip = data.get("tip", "")
            created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cur.execute(
                "INSERT INTO orders (customer, customer_id, food, price, phone, delivery_type, delivery_address, payment_method, tip, qabyl, omoda, created) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)",
                (customer, customer_id, food, price, phone, delivery_type, delivery_address, payment_method, tip, created),
            )
            order_id = cur.lastrowid

            cur.execute(
                "INSERT INTO full_order_history (customer, customer_id, food, price, phone, delivery_type, payment_method, tip, created) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (customer, customer_id, food, price, phone, delivery_type, payment_method, tip, created)
            )

            p_clean = "".join(c for c in str(price).replace(',', '.') if c.isdigit() or c == '.')
            amount = float(p_clean) if p_clean else 0.0
            cur.execute("INSERT INTO revenue_history (amount, day, customer_id) VALUES (?, ?, ?)", (amount, created[:10], customer_id))
            
            conn.commit()
            return jsonify({"ok": True, "order_id": order_id})

        elif sync_type == "customer":
            full_name = data.get("full_name")
            cust_id = data.get("customer_id")
            created = datetime.now().strftime("%d.%m.%Y %H:%M")
            cur.execute("INSERT OR IGNORE INTO customers (full_name, customer_id, created) VALUES (?, ?, ?)", (full_name, cust_id, created))
            conn.commit()
            return jsonify({"ok": True})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        conn.close()

    return jsonify({"ok": False, "error": "unknown_sync_type"}), 400


@app.route("/api/orders/new", methods=["POST", "OPTIONS"])
def api_orders_new():
    if request.method == "OPTIONS":
        return ("", 204)

    data = request.get_json(silent=True) or {}
    customer = (data.get("customer") or "Неизвестно").strip()
    customer_id = str(data.get("customer_id") or "").strip()
    food = (data.get("food") or "Блюдо").strip()
    price = str(data.get("price") or "0").strip()
    phone = str(data.get("phone") or "").strip()
    delivery_type = str(data.get("delivery_type") or "pickup").strip()
    delivery_latitude = str(data.get("delivery_latitude") or "").strip()
    delivery_longitude = str(data.get("delivery_longitude") or "").strip()
    delivery_address = str(data.get("delivery_address") or "").strip()
    payment_method = str(data.get("payment_method") or "online").strip()
    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO orders (customer, customer_id, food, price, phone, delivery_type, delivery_latitude, delivery_longitude, delivery_address, payment_method, qabyl, omoda, created) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)",
        (customer, customer_id, food, price, phone, delivery_type, delivery_latitude, delivery_longitude, delivery_address, payment_method, created),
    )
    order_id = cur.lastrowid

    # Log to full history table
    cur.execute(
        "INSERT INTO full_order_history (customer, customer_id, food, price, phone, delivery_type, payment_method, created) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (customer, customer_id, food, price, phone, delivery_type, payment_method, created)
    )

    # Сабти маблағ дар таърихи доимӣ
    try:
        p_clean = "".join(c for c in str(price).replace(',', '.') if c.isdigit() or c == '.')
        amount = float(p_clean) if p_clean else 0.0
        cur.execute("INSERT INTO revenue_history (amount, day, customer_id) VALUES (?, ?, ?)", (amount, datetime.now().strftime("%Y-%m-%d"), customer_id))
    except: pass

    conn.commit()
    conn.close()

    return jsonify(
        {
            "ok": True,
            "order": {
                "id": order_id,
                "customer": customer,
                "customer_id": customer_id,
                "food": food,
                "price": price,
                "phone": phone,
                "qabyl": False,
                "omoda": False,
                "created": created,
            },
        }
    )


@app.route("/api/orders/since", methods=["GET"])
def api_orders_since():
    last_id = request.args.get("last_id", "0")
    try:
        last_id_int = int(last_id)
    except ValueError:
        last_id_int = 0

    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, customer, customer_id, food, price, qabyl, omoda, created, phone, delivery_type, dostavka, out_of_stock, refund, delivery_latitude, delivery_longitude, delivery_address, estimated_time, payment_method, tip FROM orders WHERE id > ? ORDER BY id ASC",
        (last_id_int,),
    )
    rows = cur.fetchall()
    conn.close()

    return jsonify(
        {
            "ok": True,
            "orders": [
                {
                    "id": r[0],
                    "customer": r[1],
                    "customer_id": r[2],
                    "food": r[3],
                    "price": r[4],
                    "qabyl": bool(r[5]),
                    "omoda": bool(r[6]),
                    "created": r[7],
                    "phone": r[8] if len(r) > 8 else "",
                    "delivery_type": r[9] if len(r) > 9 else "pickup",
                    "dostavka": int(r[10]) if len(r) > 10 else 0,
                    "out_of_stock": bool(r[11]) if len(r) > 11 else False,
                    "refund": r[12] if len(r) > 12 else 0,
                    "delivery_latitude": r[13] if len(r) > 13 else "",
                    "delivery_longitude": r[14] if len(r) > 14 else "",
                    "delivery_address": r[15] if len(r) > 15 else "",
                    "estimated_time": r[16] if len(r) > 16 else 0,
                    "payment_method": r[17] if len(r) > 17 else "online",
                    "tip": r[18] if len(r) > 18 else "",
                }
                for r in rows
            ],
        }
    )

@app.route("/api/orders/update-status", methods=["POST", "OPTIONS"])
def api_orders_update_status():
    if request.method == "OPTIONS":
        return ("", 204)

    data = request.get_json(silent=True) or {}
    order_id = data.get("id")
    field = (data.get("field") or "").strip()
    value = data.get("value")
    estimated_time = data.get("estimated_time")
    if field not in ("qabyl", "omoda", "dostavka", "out_of_stock", "food", "refund", "estimated_time"):
        return jsonify({"ok": False, "error": "invalid_field"}), 400
    try:
        order_id = int(order_id)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid_id"}), 400

    db_value = str(value) if field == 'food' else (float(value) if field == 'refund' else int(value))
        
    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
    
    # Гирифтани маълумоти кунунӣ барои навсозии таърих ва пешгирӣ аз такрор
    cur.execute(f"SELECT {field if field != 'food' else 'food'}, customer_id, food, delivery_type, created, refund, price, estimated_time FROM orders WHERE id = ?", (order_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"ok": False, "error": "not_found"}), 404

    current_val, customer_id, food_name, del_type, created_at, old_refund, orig_price_str, old_est_time = row
    
    # Агар статус тағйир наёфта бошад (барои майдонҳои техникӣ), Push намефиристем
    if field not in ('food', 'refund') and int(current_val) == db_value:
        conn.close()
        return jsonify({"ok": True, "note": "no_change"})
    
    if field == 'qabyl' and estimated_time is not None:
        cur.execute("UPDATE orders SET qabyl = ?, estimated_time = ? WHERE id = ?", (db_value, estimated_time, order_id))
    else:
        cur.execute(f"UPDATE orders SET {field} = ? WHERE id = ?", (db_value, order_id))

    # ТАФТИШИ УМУМӢ: Агар заказ пурра хат зада шуда бошад, онро ҳамчун "Иҷрошуда" қайд мекунем
    # Ин тафтиш бояд ҳар вақте ки хӯрок, маблағ ё статус тағйир меёбад, иҷро шавад
    if field in ('food', 'refund', 'out_of_stock'):
        cur.execute("SELECT refund, price, out_of_stock FROM orders WHERE id = ?", (order_id,))
        rv, ps, oos = cur.fetchone()
        try: pc = float("".join(c for c in str(ps).replace(',', '.') if c.isdigit() or c == '.'))
        except: pc = 0.0
        if oos and pc > 0 and rv >= pc:
            cur.execute("UPDATE orders SET qabyl = 1, omoda = 1 WHERE id = ?", (order_id,))

    # НАВСОЗИИ ТАЪРИХИ ДАРОМАД ВА АРХИВ
    if field == 'refund':
        diff = db_value - old_refund
        if diff != 0:
            # 1. Кам кардани маблағ аз таърихи даромад (График)
            # Мо маблағи манфиро илова мекунем, то суммаи умумии он рӯз дуруст шавад
            order_date = created_at[:10] if created_at else datetime.now().strftime("%Y-%m-%d")
            cur.execute("INSERT INTO revenue_history (amount, day, customer_id) VALUES (?, ?, ?)", (-diff, order_date, customer_id))
            
            # 2. Навсозии сумма дар архиви заказҳо (Full History)
            try:
                p_clean = "".join(c for c in str(orig_price_str).replace(',', '.') if c.isdigit() or c == '.')
                orig_p = float(p_clean) if p_clean else 0.0
                new_display_price = str(round(orig_p - db_value, 2))
                cur.execute("UPDATE full_order_history SET price = ? WHERE customer_id = ? AND created = ?", (new_display_price, customer_id, created_at))
            except: pass

    if field == 'food':
        # Навсозии рӯйхати хӯрокҳо дар архив, агар ягон чиз хат зада шуда бошад
        cur.execute("UPDATE full_order_history SET food = ? WHERE customer_id = ? AND created = ?", (db_value, customer_id, created_at))

    conn.commit()
    updated = cur.rowcount > 0
    conn.close()

    # Фиристодани Push агар статус "ҳа" (1) шавад
    if updated and db_value == 1:
        conn = sqlite3.connect(DB_PATH, timeout=20); cur = conn.cursor()
        cur.execute("SELECT subscription_json FROM push_subscriptions WHERE customer_id = ?", (customer_id,))
        sub_row = cur.fetchone()
        if sub_row:
            sub_info = json.loads(sub_row[0])
            # Гирифтани маблағ ва рефунд барои муқоиса
            cur.execute("SELECT refund, price FROM orders WHERE id = ?", (order_id,))
            ref_val, orig_price_str = cur.fetchone()
            
            # Тоза кардани нархи аслӣ барои муқоиса
            try:
                p_clean = "".join(c for c in str(orig_price_str).replace(',', '.') if c.isdigit() or c == '.')
                orig_p = float(p_clean) if p_clean else 0.0
            except: orig_p = 0.0
            
            # Находим названия блюд, которые были зачеркнуты (<s>...</s>)
            struck_items = re.findall(r'<s>(.*?)</s>', food_name)
            struck_str = f" \"{', '.join(struck_items)}\"" if struck_items else ""

            if field == 'qabyl':
                t_val = estimated_time if estimated_time is not None else old_est_time
                time_str = ""
                if t_val:
                    if del_type == 'delivery':
                        time_str = f" Ваш заказ будет готов и доставлен примерно через {t_val} минут."
                    else:
                        time_str = f" Ваш заказ будет готов примерно через {t_val} минут."

                if ref_val >= orig_p and orig_p > 0:
                    msg = f"К сожалению, нет никаких блюд и мы вернем ваши деньги: {ref_val} смн."
                elif ref_val > 0:
                    msg = f"Извините, блюд{struck_str} нет в наличии, и мы вернем вам ваши деньги: {ref_val} смн."
                else:
                    msg = f"Заказ принят!{time_str} Пожалуйста, переведите оплату на номер 754169090."
            elif field == 'out_of_stock':
                if ref_val >= orig_p and orig_p > 0:
                    msg = f"К сожалению, нет никаких блюд и мы вернем ваши деньги: {ref_val} смн."
                else:
                    msg = f"Извините, блюд{struck_str} нет в наличии, и мы вернем вам ваши деньги: {ref_val} смн."
            elif field == 'omoda':
                # Пешгирӣ аз фиристодани паёми "Готов", агар заказ пурра бекор шуда бошад
                if ref_val >= orig_p and orig_p > 0:
                    conn.close()
                    return jsonify({"ok": updated})
                if del_type == 'pickup':
                    msg = "Ваш заказ готов! Пожалуйста, заберите свое блюдо."
                else:
                    msg = "Ваш заказ готов! Через несколько минут мы его доставим. 🚀"
            elif field == 'dostavka':
                if db_value == 1:
                    msg = "Мы везем ваш заказ! 🚀🚗"
                elif db_value == 2:
                    msg = "Ваш заказ доставлен! Приятного аппетита! 🏠✅"
                else:
                    msg = "Статус доставки обновлен."
            else:
                msg = "Статус заказа обновлен."

            # Тоза кардани тегҳои <s> аз рӯйхати хӯрокҳо барои хабарномаи тоза
            display_food = re.sub(r'<s>.*?</s>', '', food_name)
            display_food = re.sub(r',\s*,', ',', display_food).strip().strip(',').strip()

            try:
                webpush(sub_info, json.dumps({"title": "TFC Хабарнома", "body": f"{msg} ({display_food})" if display_food else msg}), 
                        vapid_private_key=VAPID_PRIVATE_KEY, vapid_claims=VAPID_CLAIMS)
            except WebPushException: pass
        conn.close()

    return jsonify({"ok": updated})

@app.route("/api/orders/clear-all", methods=["POST"])
def api_orders_clear_all():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
    cur.execute("DELETE FROM orders")
    # Ин фармон рақамгузории (ID)-ро аз нав ба 1 мегардонад
    cur.execute("DELETE FROM sqlite_sequence WHERE name='orders'")
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/orders/delete/<int:order_id>", methods=["DELETE"])
def api_order_delete_db(order_id):
    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
    cur.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return jsonify({"ok": ok})

@app.route("/api/orders/customer-status", methods=["GET"])
def api_orders_customer_status():
    customer_id = str(request.args.get("customer_id", "")).strip()
    if not customer_id:
        return jsonify({"ok": True, "orders": []})

    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, food, qabyl, omoda, created, estimated_time FROM orders WHERE customer_id = ? ORDER BY id ASC",
        (customer_id,),
    )
    rows = cur.fetchall()
    conn.close()

    return jsonify(
        {
            "ok": True,
            "orders": [
                {
                    "id": r[0],
                    "food": r[1],
                    "qabyl": bool(r[2]),
                    "omoda": bool(r[3]),
                    "created": r[4],
                    "estimated_time": r[5] if len(r) > 5 else 0,
                }
                for r in rows
            ],
        }
    )

# FOOD MANAGEMENT API ROUTES
@app.route("/api/foods/list", methods=["GET"])
def api_foods_list():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
    cur.execute("SELECT id, name, price, category, image_url, description, subcategory FROM foods ORDER BY category, subcategory, name ASC")
    rows = cur.fetchall()
    conn.close()

    return jsonify(
        {
            "ok": True,
            "foods": [
                {
                    "id": r[0],
                    "name": r[1],
                    "price": r[2],
                    "category": r[3],
                    "image_url": r[4],
                    "description": r[5],
                    "subcategory": r[6] if len(r) > 6 else "",
                }
                for r in rows
            ],
        }
    )

@app.route("/api/foods/add", methods=["POST", "OPTIONS"])
def api_foods_add():
    if request.method == "OPTIONS":
        return ("", 204)

    # Гирифтани маълумот аз Form (multipart/form-data)
    name = request.form.get("name", "").strip()
    price = request.form.get("price", "").strip()
    category = request.form.get("category", "Меню").strip()
    subcategory = request.form.get("subcategory", "").strip()
    description = request.form.get("description", "").strip()
    image_url = request.form.get("image_url", "").strip()

    # Коркарди сурат агар бор карда шавад
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            # Илова кардани вақт барои номи беназир
            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            if not os.path.exists(UPLOAD_FOLDER):
                os.makedirs(UPLOAD_FOLDER)
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            image_url = filename

    if not name or not price:
        return jsonify({"ok": False, "error": "missing_fields"}), 400

    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO foods (name, price, category, subcategory, image_url, description, created) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, price, category, subcategory, image_url, description, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        food_id = cur.lastrowid
        conn.commit()
        conn.close()
        return jsonify(
            {
                "ok": True,
                "food": {
                    "id": food_id,
                    "name": name,
                    "price": price,
                    "category": category,
                    "image_url": image_url,
                },
            }
        )
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"ok": False, "error": "duplicate_name"}), 400
    except Exception as e:
        if 'conn' in locals(): conn.close()
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/foods/update/<int:food_id>", methods=["PUT", "OPTIONS"])
def api_foods_update(food_id):
    if request.method == "OPTIONS":
        return ("", 204)

    name = request.form.get("name", "").strip()
    price = request.form.get("price", "").strip()
    category = request.form.get("category", "Меню").strip()
    subcategory = request.form.get("subcategory", "").strip()
    description = request.form.get("description", "").strip()
    image_url = request.form.get("image_url", "").strip()

    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            if not os.path.exists(UPLOAD_FOLDER):
                os.makedirs(UPLOAD_FOLDER)
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            image_url = filename

    if not name or not price:
        return jsonify({"ok": False, "error": "missing_fields"}), 400

    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE foods SET name = ?, price = ?, category = ?, subcategory = ?, image_url = ?, description = ? WHERE id = ?",
            (name, price, category, subcategory, image_url, description, food_id),
        )
        conn.commit()
        updated = cur.rowcount > 0
        conn.close()
        return jsonify({"ok": updated})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"ok": False, "error": "duplicate_name"}), 400

@app.route("/api/foods/delete/<int:food_id>", methods=["DELETE", "OPTIONS"])
def api_foods_delete(food_id):
    if request.method == "OPTIONS":
        return ("", 204)

    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
    cur.execute("DELETE FROM foods WHERE id = ?", (food_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return jsonify({"ok": deleted})

@app.route("/api/aktsii/list", methods=["GET"])
def api_aktsii_list():
    conn = sqlite3.connect(DB_PATH, timeout=20); cur = conn.cursor()
    cur.execute("SELECT id, title, price, description, image_url, created FROM aktsii ORDER BY id DESC")
    rows = cur.fetchall(); conn.close()
    return jsonify({"ok": True, "aktsii": [{"id": r[0], "title": r[1], "price": r[2], "description": r[3], "image_url": r[4], "created": r[5]} for r in rows]})

@app.route("/api/aktsii/add", methods=["POST"])
def api_aktsii_add():
    title = request.form.get("title", "").strip()
    price = request.form.get("price", "").strip()
    description = request.form.get("description", "").strip()
    image_url = ""
    if not title or not price or not description:
        return jsonify({"ok": False, "error": "missing_fields"}), 400

    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filename = f"promo_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            image_url = filename

    conn = sqlite3.connect(DB_PATH, timeout=20); cur = conn.cursor()
    cur.execute("INSERT INTO aktsii (title, price, description, image_url, created) VALUES (?, ?, ?, ?, ?)",
                (title, price, description, image_url, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/aktsii/delete/<int:aktsii_id>", methods=["DELETE"])
def api_aktsii_delete(aktsii_id):
    conn = sqlite3.connect(DB_PATH, timeout=20); cur = conn.cursor()
    cur.execute("DELETE FROM aktsii WHERE id = ?", (aktsii_id,))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/orders/full-history", methods=["GET"])
def api_full_order_history():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
    cur.execute("SELECT customer, customer_id, food, price, phone, delivery_type, created, payment_method FROM full_order_history")
    rows = cur.fetchall()
    conn.close()
    
    history = [
        {"customer": r[0], "customer_id": r[1], "food": r[2], "price": r[3], "phone": r[4], "delivery_type": r[5], "created": r[6], "payment_method": r[7] if len(r) > 7 else "online"}
        for r in rows
    ]
    return jsonify({"ok": True, "history": history})

@app.route("/api/orders/clear-full-history", methods=["POST"])
def api_clear_full_history():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
    cur.execute("DELETE FROM full_order_history")
    cur.execute("DELETE FROM sqlite_sequence WHERE name='full_order_history'")
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/stats/daily-revenue", methods=["GET"])
def api_daily_revenue():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
    # Гирифтани маблағ ва шумораи заказҳо дар як рӯз
    cur.execute("SELECT COUNT(DISTINCT customer_id), SUM(amount), day FROM revenue_history GROUP BY day")
    rows = cur.fetchall()
    conn.close()
    
    stats = [{"day": r[2], "total": round(r[1], 2), "count": r[0]} for r in rows]
    stats.sort(key=lambda x: x['day'], reverse=True)
    return jsonify({"ok": True, "stats": stats})

@app.route("/api/stats/popular-foods", methods=["GET"])
def api_popular_foods():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
    # Гирифтани ҳамаи сабтҳо барои коркард дар Python
    cur.execute("SELECT food, price FROM full_order_history")
    rows = cur.fetchall()
    conn.close()

    aggregated = {}
    for food_str, price_str in rows:
        try:
            # Тоза кардани нарх аз рамзҳои иловагӣ ва табдил ба адад
            p_clean = "".join(c for c in str(price_str).replace(',', '.') if c.isdigit() or c == '.')
            price = float(p_clean) if p_clean else 0.0
        except:
            price = 0.0

        # Агар якчанд хӯрок дар як сатр бошад (бо вергул ҷудо шуда), онҳоро ҷудо мекунем
        items = [i.strip() for i in food_str.split(',')]
        for item_str in items:
            # Тоза кардани рақами тартибӣ (масалан "1. ")
            clean_item = re.sub(r'^\d+\.\s*', '', item_str)
            match = re.search(r'^(.*?)\s+x(\d+)$', clean_item)
            
            if match:
                base_name = match.group(1).strip()
                qty = int(match.group(2))
            else:
                base_name = clean_item.strip()
                qty = 1

            if base_name not in aggregated:
                aggregated[base_name] = {"count": 0, "total": 0.0}
            
            aggregated[base_name]["count"] += qty
            # Нархро танҳо ба хӯроки аввал ё ба таври умумӣ тақсим кардан мумкин аст, 
            # дар ин ҷо барои содагӣ мо нархи умумиро ба сабти аввал вобаста мекунем ё дар омор нишон медиҳем.
            if item_str == items[0]:
                aggregated[base_name]["total"] += price

    stats = [{"food": k, "count": v["count"], "total": v["total"]} for k, v in aggregated.items()]
    # Батартиб даровардан аз рӯи миқдори фурӯш
    stats.sort(key=lambda x: x['count'], reverse=True)
    return jsonify({"ok": True, "stats": stats})

@app.route("/api/customers/delete/<string:customer_id>", methods=["DELETE"])
def api_customers_delete(customer_id):
    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
    cur.execute("DELETE FROM customers WHERE customer_id = ?", (customer_id,))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return jsonify({"ok": ok})

@app.route("/api/stats/clear-history", methods=["POST"])
def api_stats_clear_history():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
    cur.execute("DELETE FROM revenue_history")
    # Ин фармон рақамгузории (ID)-ро аз нав ба 1 мегардонад
    cur.execute("DELETE FROM sqlite_sequence WHERE name='revenue_history'")
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/customers/list", methods=["GET"])
def api_customers_list():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    cur = conn.cursor()
    cur.execute("SELECT full_name, customer_id, created FROM customers ORDER BY id DESC")
    rows = cur.fetchall(); conn.close()
    return jsonify({"ok": True, "customers": [{"full_name": r[0], "customer_id": r[1], "created": r[2]} for r in rows]})

@app.route("/api/settings/get", methods=["GET"])
def api_get_setting():
    key = request.args.get("key")
    conn = sqlite3.connect(DB_PATH, timeout=20); cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = ?", (key,)); r = cur.fetchone(); conn.close()
    return jsonify({"ok": True, "val": r[0] if r else ""})

@app.route("/api/settings/set", methods=["POST"])
def api_set_setting():
    data = request.get_json()
    conn = sqlite3.connect(DB_PATH, timeout=20); cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (data['key'], data['val']))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

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
    admin_port = 5001
    local_ip = get_local_ip()
    print(f"\n" + "="*60)
    print(f"🚀 ССЫЛКА ДЛЯ ТЕЛЕФОНА (Панель Админа):")
    print(f"👉 http://{local_ip}:{admin_port}")
    print(f"")
    print(f"🏠 ССЫЛКА НА КОМПЬЮТЕРЕ: http://127.0.0.1:{admin_port}")
    print(f"="*60 + "\n")
    # Дар муҳити корӣ (Production) Gunicorn-ро истифода баред:
    # gunicorn -w 4 -b 0.0.0.0:5001 bilol:app
    app.run(debug=False, host="0.0.0.0", port=admin_port)
