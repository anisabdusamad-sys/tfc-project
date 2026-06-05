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

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "tfc_admin.db"))


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
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
    if "refund" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN refund REAL NOT NULL DEFAULT 0")
    if "delivery_latitude" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN delivery_latitude TEXT DEFAULT ''")
    if "delivery_longitude" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN delivery_longitude TEXT DEFAULT ''")
    if "delivery_address" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN delivery_address TEXT DEFAULT ''")
    
    cur.execute("CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, text TEXT NOT NULL, stars INTEGER NOT NULL, image_url TEXT, created TEXT NOT NULL)")

    # Сохтани ҷадвали revenue_history барои графикҳо
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS revenue_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            day TEXT NOT NULL
        )
        """
    )

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
        # ПАСТА
        ("ПАСТА БОЛОНЕЗА", "31", "Меню", "b1.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПАСТА ФИТУЧИНИ", "35", "Меню", "b2.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПАСТА ПЕНЕ", "32", "Меню", "b3.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПАСТА СОБА", "23", "Меню", "b4.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ГНЁЗДА С ГОВЯДИНОЙ", "27", "Меню", "b5.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        
        # САЛАТҲО
        ("САЛАТ ТАЙСКИЙ", "34", "Меню", "b6.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("САЛАТ TFC", "35", "Меню", "b7.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ХРУСТЯЩИЙ БАКЛАЖАН", "17", "Меню", "b8.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("САЛАТ ЦЕЗАРЬ", "25", "Меню", "b9.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("САЛАТ ЗЕЛЁНАЯ ЛУЖАЙКА", "15", "Меню", "b10.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ГРЕЧЕСКИЙ САЛАТ", "34", "Меню", "b11.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),

        # ШӮРБОҲО
        ("СУП МЕРДЖИМЕК", "15", "Меню", "b12.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("БОРЩ", "25", "Меню", "b13.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ГРИБНОЙ СУП", "26", "Меню", "b14.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЛАГМАН", "21", "Меню", "b15.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУП TFC", "28", "Меню", "b16.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЧАХОВ БИЛИ", "26", "Меню", "b17.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),

        # ҒАЗОҲОИ ГАРМ
        ("БИФШ СТЕКС", "25/35", "Меню", "b18.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КОТЛЕТ ПО-КИЕВСКИЙ", "28/38", "Меню", "b19.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КАЗАН КАБОБ", "40", "Меню", "b21.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЖАРОВНЯ ТФС (БАРАНИНА/ГОВЯДИНА)", "50", "Меню", "b22.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СТЕЙК ИЗ ФОРЕЛИ", "25", "Меню", "b23.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТАБАКА", "58", "Меню", "b24.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КОРЕЙКА БАРАНИНА", "50", "Меню", "b25.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СТЕЙК ИЗ ГОВЯДИНЫ", "50", "Меню", "b26.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),

        # ДЕСЕРТҲО
        ("ЧИЗКЕЙК", "12", "Меню", "b27.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("РАФАЭЛЛО", "12", "Меню", "b28.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("НАПОЛЕОН", "10", "Меню", "b29.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТИРАМИСУ", "12", "Меню", "b30.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ФРУКТОВАЯ НАРЕЗКА (Большая)", "75", "Меню", "b31.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ФРУКТОВАЯ НАРЕЗКА (Средняя)", "50", "Меню", "b32.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КЕШЬЮ", "45", "Меню", "b33.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ФИСТАШКИ", "45", "Меню", "b34.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),

        # НӮШОКИҲО
        ("АМЕРИКАНО", "15", "Меню", "b35.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КАПУЧИНO", "18", "Меню", "b36.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЛАТТЕ", "18", "Меню", "b37.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЭСПРЕССО", "12", "Меню", "b38.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЧАЙ (Зелёный / черный)", "5", "Меню", "b39.jpg", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),

        # ПИЦЦА
        ("ПИЦЦА ГОВЯДИНА", "65/87", "Пицца", "a1.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПИЦЦА АССОРТИ", "68/88", "Пицца", "a2.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПИЦЦА ЧЕТЫРЕ СЫРА", "61/78", "Пицца", "a3.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПИЦЦА ЧЕРНАЯ МЕТКА", "62/79", "Пицца", "a4.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПИЦЦА ТОНИ МОНТАНА", "73/90", "Пицца", "a5.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПИЦЦА TFC", "68/90", "Пицца", "a6.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПИЦЦА ПЕППЕРОНИ", "63/75", "Пицца", "a7.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ПИЦЦА КУРИНАЯ", "65/84", "Пицца", "a8.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ХАЧАПУРИ ПО-АДЖАРСКИ", "35", "Пицца", "a9.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ХАЧАПУРИ МЕГРЕЛЬСКИЙ", "40", "Пицца", "a10.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        
        # СУШИ
        ("МИНИ РОЛЛЫ С СЫРОМ", "25/35", "Суши", "a.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СИЯКИ МАКИ", "24/34", "Суши", "b.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МИНИ РОЛЛЫ ФИЛАДЕЛЬФИЯ", "26/36", "Суши", "c.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("УНАГИ КАПА МАКИ", "27/37", "Суши", "d.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЗАПЕЧЕНЫЙ САМУРАЙ", "51", "Суши", "e.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЗАПЕЧЕНЫЙ УНАГИ", "61", "Суши", "f.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЗАПЕЧЕННАЯ КАЛИФОРНИЯ С КРЕВЕТКОЙ", "59/69", "Суши", "g.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЗАПЕЧЕНЫЙ СЯКЕ", "54/64", "Суши", "h.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТЕМПУРА КРАЙЗИ", "44", "Суши", "i.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТЕМПУРА СНЕЖНЫЙ КРАБ", "45", "Суши", "j.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ОВОЩНАЯ ТЕМПУРА", "35", "Суши", "k.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТЕМПУРА ЦЕЗАРЬ", "38", "Суши", "l.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("РОЛЛ КАНАДА TFC", "60", "Суши", "m.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("РОЛЛ САНСИ", "58", "Суши", "n.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КАЛИФОРНИЯ СНЕЖНЫЙ КРАБ", "51", "Суши", "o.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("РОЛЛ ФИЛАДЕЛЬФИЯ", "58", "Суши", "p.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУШИ С КРЕВЕТКОЙ", "13", "Суши", "q.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУШИ С УГЛЕМ", "13", "Суши", "r.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУШИ С ЛОСОСЬЮ", "17", "Суши", "s.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУШИ ЗАПЕЧЕНЫЙ ЛОСОСЬ", "17", "Суши", "t.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУШИ ОСТРЫЕ С ТУНЦОМ", "12", "Суши", "u.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СУШИ С УГРЕМ", "13", "Суши", "v.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СЕТ ТЕМПУРА", "135", "Суши", "w.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СЕТ КАНАДА TFC", "160", "Суши", "x.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СЕТ ЗАПЕЧЁННЫЙ", "146", "Суши", "y.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        
        # ФАСТ ФУД
        ("НОН-ДОГ", "5/7", "Фастфуд", "1.png", "Состав: Лепешка, сосиска, помидор, огурцы.\n\nЦена: * L: 5с, XL: 7с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("БУЛОЧКА", "6/8", "Фастфуд", "2.png", "Состав: Булочка, сосиска, помидор, огурцы.\n\nЦена: * L: 6с, XL: 8с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("НОН-ДОГ", "5/7", "Фастфуд", "1.png", "Состав: Лепешка, сосиска, помидор, огурцы.\n\nЦена: * L: 5с, XL: 7с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("БУЛОЧКА", "6/8", "Фастфуд", "2.png", "Состав: Булочка, сосиска, помидор, огурцы.\n\nЦена: * L: 6с, XL: 8с", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("М-ДОГ", "10", "Фастфуд", "3.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("TFC-ДОГ", "18/30", "Фастфуд", "4.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЧИКЕН-ДОГ", "12/24", "Фастфуд", "5.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("НАЧО-ДОГ", "14/26", "Фастфуд", "6.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ЧИКЕНЧИЗ-ДОГ", "16/28", "Фастфуд", "7.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ШЕФ-ДОГ", "17/29", "Фастфуд", "8.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("АМЕРИКАНО-ДОГ", "16/25", "Фастфуд", "9.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ИТАЛИ-ДОГ", "12/20", "Фастфуд", "10.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("БИФ-ДОГ", "41", "Фастфуд", "11.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КЛАССИК БУРГЕР", "23", "Фастфуд", "12.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КЛАССИК ЧИЗБУРГЕР", "27", "Фастфуд", "13.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ДАБЛ ЧИЗБУРГЕР", "43", "Фастфуд", "14.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ДАБЛ БУРГЕР", "37", "Фастфуд", "15.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("TFC БУРГЕР", "48", "Фастфуд", "16.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ШЕФ БУРГЕР", "51/61", "Фастфуд", "17.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТОРТИЛЬЯ С КУРИЦЕЙ И С СЫРОМ", "23", "Фастфуд", "18.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТОРТИЛЬЯ С КУРИЦЕЙ", "15", "Фастфуд", "19.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТОРТИЛЬЯ МИКС", "26/36", "Фастфуд", "20.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТОРТИЛЬЯ TFC", "40", "Фастфуд", "21.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТОРТИЛЬЯ ГОВЯДИНА", "32", "Фастфуд", "22.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ТОРТИЛЬЯ В ТЕМПУРАХ", "28", "Фастфуд", "23.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СЭНДВИЧ SIMPLE", "19", "Фастфуд", "24.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СЭНДВИЧ С СЫРОМ", "23", "Фастфуд", "25.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КАРТОШКА ФРИ", "12/17", "Фастфуд", "28.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КАРТОФЕЛЬ ПО-ДЕРЕВЕНСКИ", "13/18", "Фастфуд", "29.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КАРТОФЕЛЬНЫЕ ШАРИКИ", "14/19", "Фастфуд", "30.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("НАГГЕТСЫ", "17/27", "Фастфуд", "31.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ОСТРЫЕ КРЫЛЫШКИ", "35/45", "Фастфуд", "32.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СЛАДКИЕ КРЫЛЫШКИ", "36/46", "Фастфуд", "33.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("КУРИНЫЕ НОЖКИ", "69/109", "Фастфуд", "34.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СЫРНЫЕ ПАЛОЧКИ", "28", "Фастфуд", "35.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("БАСКЕТ", "130", "Фастфуд", "36.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),

        # ЛЕТНЕЕ МЕНЮ
        ("СМУЗИ БАНАН + КИВИ", "26", "Летнее меню", "d1.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СМУЗИ БАНАН + АБРИКОС", "23", "Летнее меню", "d2.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СМУЗИ БАНАН + МАЛИНА", "26", "Летнее меню", "d3.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СМУЗИ БАНАН + ЯБЛОКО", "23", "Летнее меню", "d4.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СМУЗИ БАНАН + ДЫНЯ", "21", "Летнее меню", "d5.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("СМУЗИ БАНАН + ВИШНЯ", "21", "Летнее меню", "d6.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("ОКРОШКА (350МЛ)", "16", "Летнее меню", "d7.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("АЙРАН (500МЛ)", "6", "Летнее меню", "d8.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        # МОХИТО
        ("МОХИТО LIME", "19", "Летнее меню", "e1.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МОХИТО CLASSIC", "16", "Летнее меню", "e2.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МОХИТО FRUITE", "19", "Летнее меню", "e3.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МОХИТО PINEAPPLE", "19", "Летнее меню", "e4.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МОХИТО CHERRY", "16", "Летнее меню", "e5.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МОХИТО BLUE LAGOON", "19", "Летнее меню", "e6.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МОХИТО БАНАНОВЫЙ", "16", "Летнее меню", "e7.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МОХИТО KIWI", "19", "Летнее меню", "e8.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("МОХИТО APPLE", "16", "Летнее меню", "e9.png", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    ]
    conn.commit()
    conn.close()


init_db()

HTML = """<!DOCTYPE html>
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
    <title>Панель Админа | ТФС</title>
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
        <div class="max-w-full mx-auto px-2 py-3 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div class="flex flex-wrap items-center gap-4">
                <div class="w-12 h-12 rounded-2xl bg-white/95 flex items-center justify-center text-2xl shadow-lg text-red-600">
                    <i class="fas fa-drumstick-bite"></i>
                </div>
                <div class="flex flex-col sm:flex-row sm:items-center gap-4">
                    <div>
                        <h1 class="text-xl font-bold tracking-tight">ТФС <span class="font-normal text-white/80 text-sm">Админ</span></h1>
                        <p class="text-[9px] text-red-200/90 tracking-[0.1em] uppercase">TFC Kulob</p>
                    </div>
                    <div class="flex items-center gap-2">
                        <div class="stat-card">
                            <span id="total-orders" class="text-lg font-bold">0</span> <span class="text-[9px] uppercase opacity-60">Всего</span>
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
            <button type="button" onclick="showAddModal()"
                    class="inline-flex items-center justify-center gap-2 bg-[#e4002b] hover:bg-[#c8102e] text-white px-6 py-3.5 rounded-2xl font-semibold shadow-lg shadow-red-500/25 hover:shadow-xl active:scale-[0.98] transition-all">
                <i class="fas fa-plus"></i>
                ЗАКАЗАТЬ
            </button>
        </div>

        <div class="toolbar-glass rounded-2xl p-4 mb-4 flex flex-col sm:flex-row flex-wrap gap-3 items-stretch sm:items-center justify-between">
            <div class="relative flex-1 min-w-[200px] max-w-md">
                <i class="fas fa-search absolute left-4 top-1/2 -translate-y-1/2 text-gray-500 text-sm"></i>
                <input type="search" id="search-input" placeholder="Поиск..."
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
            ТФС Админ v2 • Dark Theme • <span id="saved-hint" class="text-emerald-500/80"></span>
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
                    <input type="search" id="foods-search-input" placeholder="Поиск по названию..."
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
            ТФС Админ v2 • Управление Меню
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
                    // Загружаем только незавершенные заказы
                    orders = JSON.parse(raw).filter(o => !(o.qabyl && o.omoda));
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
            const q = (document.getElementById('search-input')?.value || '').trim().toLowerCase();
            let list = orders.filter(o => {
                if (!q) return true;
                return (o.nom + ' ' + (o.mijoz_id || '') + ' ' + o.khurok).toLowerCase().includes(q);
            });
            list = list.filter(o => {
                const done = o.qabyl && o.omoda;
                const cooking = o.qabyl && !o.omoda;
                const pending = !o.qabyl;
                if (filterMode === 'all') return true;
                if (filterMode === 'pending') return pending;
                if (filterMode === 'cooking') return cooking;
                if (filterMode === 'done') return done;
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
                const isCompleted = order.qabyl && order.omoda;
            // Тафтиши он ки оё ҳамаи хӯрокҳо хат зада шудаанд (refund == price)
            const isFullyOOS = order.out_of_stock && (parsePrice(order.pul) > 0 && (order.refund >= parsePrice(order.pul)));
                const row = document.createElement('tr');
            row.className = (isCompleted || isFullyOOS) ? 'completed table-row' : 'table-row';

                row.innerHTML = `
                    <td class="font-mono text-gray-500">${index + 1}</td>
                    <td class="font-semibold text-white">${escapeHtml(order.nom)}</td>
                    <td class="font-bold text-yellow-400">${escapeHtml(order.phone || '—')}</td>
                    <td>
                        <span class="chip flex items-center gap-1 w-fit ${order.delivery_type === 'delivery'
                            ? 'bg-red-600/20 text-red-400 border border-red-600/30'
                            : 'bg-blue-600/20 text-blue-400 border border-blue-600/30'}"> <!-- This will be yellow in light mode -->
                            <i class="fas ${order.delivery_type === 'delivery' ? 'fa-truck' : 'fa-walking'} text-xs"></i>
                            ${order.delivery_type === 'delivery' ? 'Доставка' : 'Самовывоз'}
                        </span>
                    </td>
                    <td class="font-mono text-sm text-gray-400">#${order.id} <span class="opacity-50">(${escapeHtml(order.mijoz_id || '—')})</span></td>
                    <td class="text-gray-300">
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
                        <button type="button" onclick="toggleStatus(${order.id}, 'qabyl')"
                                class="status-btn inline-flex items-center justify-center w-10 h-10 rounded-xl text-xl ${order.qabyl ? 'bg-emerald-600/30 text-emerald-400' : 'bg-red-600/20 text-red-400 hover:bg-red-600/30'}">
                            <i class="fas ${order.qabyl ? 'fa-check' : 'fa-hourglass-start'}"></i>
                        </button>
                        <div class="text-[10px] mt-1 font-medium ${order.qabyl ? 'text-emerald-400' : 'text-red-400'}">${order.qabyl ? 'Принят' : 'Ожидание'}</div>
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
                    <td class="text-center">
                        ${order.delivery_type === 'delivery' && (order.delivery_latitude || order.delivery_address) ? `
                            <div class="flex flex-col gap-1 text-[11px]">
                                ${order.delivery_latitude ? `<div><a href="https://www.google.com/maps?q=${order.delivery_latitude},${order.delivery_longitude}" target="_blank" class="hover:scale-150 transition-transform inline-block p-1"><i class="fas fa-map-marker-alt text-red-600 text-xl"></i></a> <span class="text-blue-400 ml-1 font-mono">${parseFloat(order.delivery_latitude).toFixed(4)}, ${parseFloat(order.delivery_longitude).toFixed(4)}</span></div>` : ''}
                                ${order.delivery_address ? `<div class="text-gray-300">${escapeHtml(order.delivery_address)}</div>` : ''}
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
            }
            renderTable();
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
            if (field === 'dostavka') {
                nextValue = (parseInt(order.dostavka) || 0) + 1;
                if (nextValue > 2) nextValue = 0; // 0: Ожидание -> 1: В пути -> 2: Доставлен -> 0
            } else {
                nextValue = !order[field];
            }
            order[field] = nextValue;
            try {
                await fetch("/api/orders/update-status", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ id: id, field: field, value: nextValue })
                });
            } catch (e) {}
            saveOrders();
            renderTable();
            if (order.qabyl && order.omoda) {
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
            document.getElementById('total-orders').textContent = orders.length;
            document.getElementById('pending-accept').textContent = orders.filter(o => !o.qabyl).length;
            document.getElementById('cooking-count').textContent = orders.filter(o => o.qabyl && !o.omoda).length;
            document.getElementById('ready-count').textContent = orders.filter(o => o.omoda).length;
            
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
                                <td class="px-6 py-4 text-sm font-bold text-gray-900">${escapeHtml(h.customer)}</td>
                                <td class="px-6 py-4 text-sm font-semibold text-blue-600">${escapeHtml(h.phone)}</td>
                                <td class="px-6 py-4 text-sm text-gray-700">${escapeHtml(h.food)}</td>
                                <td class="px-6 py-4 text-sm font-black text-emerald-600">${escapeHtml(h.price)} смн</td>
                                <td class="px-6 py-4 text-[10px] font-bold uppercase text-gray-400">${h.delivery_type === 'delivery' ? '🚛 Доставка' : '🛍️ Самовывоз'}</td>
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
            if (code !== "159951.tfc") {
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
                    delivery_address: o.delivery_address || ''
                });
                if (o.id > lastSeenOrderId) lastSeenOrderId = o.id;
            }

            renderTable();

            // Хабарнома (Toast) танҳо барои заказҳои нав ва агар боркунии аввалия набошад
            if (!isInitial) {
                const last = trulyNewOrders[trulyNewOrders.length - 1];
                const idPart = last.customer_id ? ` [${last.customer_id}]` : '';
                const typeStr = last.delivery_type === 'delivery' ? 'ДОСТАВКА' : 'САМОВЫВОЗ';
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
            'Пицца': ['Пицца'],
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
            if (foodsFilterCategory === 'Пицца') return selected === 'пицца';
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
    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO orders (customer, customer_id, food, price, phone, delivery_type, delivery_latitude, delivery_longitude, delivery_address, qabyl, omoda, created) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)",
        (customer, customer_id, food, price, phone, delivery_type, delivery_latitude, delivery_longitude, delivery_address, created),
    )
    order_id = cur.lastrowid

    # Log to full history table
    cur.execute(
        "INSERT INTO full_order_history (customer, customer_id, food, price, phone, delivery_type, created) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (customer, customer_id, food, price, phone, delivery_type, created)
    )

    # Сабти маблағ дар таърихи доимӣ
    try:
        p_clean = "".join(c for c in str(price).replace(',', '.') if c.isdigit() or c == '.')
        amount = float(p_clean) if p_clean else 0.0
        cur.execute("INSERT INTO revenue_history (amount, day) VALUES (?, ?)", (amount, datetime.now().strftime("%Y-%m-%d")))
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

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, customer, customer_id, food, price, qabyl, omoda, created, phone, delivery_type, dostavka, out_of_stock, refund, delivery_latitude, delivery_longitude, delivery_address FROM orders WHERE id > ? AND (qabyl = 0 OR omoda = 0) ORDER BY id ASC",
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
    if field not in ("qabyl", "omoda", "dostavka", "out_of_stock", "food", "refund"):
        return jsonify({"ok": False, "error": "invalid_field"}), 400
    try:
        order_id = int(order_id)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid_id"}), 400

    db_value = str(value) if field == 'food' else (float(value) if field == 'refund' else int(value))
        
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Гирифтани маълумоти кунунӣ барои навсозии таърих ва пешгирӣ аз такрор
    cur.execute(f"SELECT {field if field != 'food' else 'food'}, customer_id, food, delivery_type, created, refund, price FROM orders WHERE id = ?", (order_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"ok": False, "error": "not_found"}), 404

    current_val, customer_id, food_name, del_type, created_at, old_refund, orig_price_str = row
    
    # Агар статус тағйир наёфта бошад (барои майдонҳои техникӣ), Push намефиристем
    if field not in ('food', 'refund') and int(current_val) == db_value:
        conn.close()
        return jsonify({"ok": True, "note": "no_change"})
    
    cur.execute(f"UPDATE orders SET {field} = ? WHERE id = ?", (db_value, order_id))

    # НАВСОЗИИ ТАЪРИХИ ДАРОМАД ВА АРХИВ
    if field == 'refund':
        diff = db_value - old_refund
        if diff != 0:
            # 1. Кам кардани маблағ аз таърихи даромад (График)
            # Мо маблағи манфиро илова мекунем, то суммаи умумии он рӯз дуруст шавад
            order_date = created_at[:10] if created_at else datetime.now().strftime("%Y-%m-%d")
            cur.execute("INSERT INTO revenue_history (amount, day) VALUES (?, ?)", (-diff, order_date))
            
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
        conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
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
                if ref_val >= orig_p and orig_p > 0:
                    msg = f"Извините, блюд{struck_str} нет в наличии, и мы вернем вам ваши деньги."
                elif ref_val > 0:
                    msg = f"Извините, блюд{struck_str} нет в наличии, и мы вернем вам ваши деньги."
                else:
                    msg = "Заказ принят! Пожалуйста, переведите оплату на номер 754169090."
            elif field == 'out_of_stock':
                if ref_val >= orig_p and orig_p > 0:
                    msg = f"Извините, блюд{struck_str} нет в наличии, и мы вернем вам ваши деньги."
                else:
                    msg = f"Извините, блюд{struck_str} нет в наличии, и мы вернем вам ваши деньги."
            elif field == 'omoda':
                if del_type == 'pickup':
                    msg = "Ваш заказ готов! Пожалуйста, заберите свое блюдо."
                else:
                    msg = "🎉 Ваш заказ готов!"
            elif field == 'dostavka':
                if db_value == 1:
                    msg = "Мы везем ваш заказ! 🚀🚗"
                elif db_value == 2:
                    msg = "Ваш заказ доставлен! Приятного аппетита! 🏠✅"
                else:
                    msg = "Статус доставки обновлен."
            else:
                msg = "Статус заказа обновлен."

            # Барои хабарномаҳои минбаъда хӯрокҳои нестро аз рӯйхат тоза мекунем
            display_food = food_name
            if field in ('omoda', 'dostavka'):
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
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM orders")
    # Ин фармон рақамгузории (ID)-ро аз нав ба 1 мегардонад
    cur.execute("DELETE FROM sqlite_sequence WHERE name='orders'")
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/orders/delete/<int:order_id>", methods=["DELETE"])
def api_order_delete_db(order_id):
    conn = sqlite3.connect(DB_PATH)
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

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, food, qabyl, omoda, created FROM orders WHERE customer_id = ? ORDER BY id ASC",
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

    conn = sqlite3.connect(DB_PATH)
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

    conn = sqlite3.connect(DB_PATH)
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

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM foods WHERE id = ?", (food_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return jsonify({"ok": deleted})

@app.route("/api/aktsii/list", methods=["GET"])
def api_aktsii_list():
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
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

    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("INSERT INTO aktsii (title, price, description, image_url, created) VALUES (?, ?, ?, ?, ?)",
                (title, price, description, image_url, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/aktsii/delete/<int:aktsii_id>", methods=["DELETE"])
def api_aktsii_delete(aktsii_id):
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("DELETE FROM aktsii WHERE id = ?", (aktsii_id,))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/orders/full-history", methods=["GET"])
def api_full_order_history():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT customer, customer_id, food, price, phone, delivery_type, created FROM full_order_history")
    rows = cur.fetchall()
    conn.close()
    
    history = [
        {"customer": r[0], "customer_id": r[1], "food": r[2], "price": r[3], "phone": r[4], "delivery_type": r[5], "created": r[6]}
        for r in rows
    ]
    return jsonify({"ok": True, "history": history})

@app.route("/api/orders/clear-full-history", methods=["POST"])
def api_clear_full_history():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM full_order_history")
    cur.execute("DELETE FROM sqlite_sequence WHERE name='full_order_history'")
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/stats/daily-revenue", methods=["GET"])
def api_daily_revenue():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Гирифтани маблағ ва шумораи заказҳо дар як рӯз
    cur.execute("SELECT count(*), sum(amount), day FROM revenue_history GROUP BY day")
    rows = cur.fetchall()
    conn.close()
    
    stats = [{"day": r[2], "total": round(r[1], 2), "count": r[0]} for r in rows]
    stats.sort(key=lambda x: x['day'], reverse=True)
    return jsonify({"ok": True, "stats": stats})

@app.route("/api/stats/popular-foods", methods=["GET"])
def api_popular_foods():
    conn = sqlite3.connect(DB_PATH)
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

@app.route("/api/stats/clear-history", methods=["POST"])
def api_stats_clear_history():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM revenue_history")
    # Ин фармон рақамгузории (ID)-ро аз нав ба 1 мегардонад
    cur.execute("DELETE FROM sqlite_sequence WHERE name='revenue_history'")
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/settings/get", methods=["GET"])
def api_get_setting():
    key = request.args.get("key")
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("SELECT val FROM settings WHERE key = ?", (key,)); r = cur.fetchone(); conn.close()
    return jsonify({"ok": True, "val": r[0] if r else ""})

@app.route("/api/settings/set", methods=["POST"])
def api_set_setting():
    data = request.get_json()
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO settings (key, val) VALUES (?, ?)", (data['key'], data['val']))
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
    app.run(debug=True, host="0.0.0.0", port=admin_port)
