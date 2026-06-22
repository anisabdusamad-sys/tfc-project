import psycopg2
from datetime import datetime

DATABASE_URL = 'postgresql://tfcdb_4eoa_user:hIRovZCZRqkCxstsP3U98O5bRzjNLlm0@dpg-d8rnghmgvqtc73f9lmj0-a.virginia-postgres.render.com/tfcdb_4eoa'
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Missing items to add
missing_items = [
    # Горячее
    ("ФИСТАШКИ БАРАНИНА", "45", "Меню", "", "", now),
    
    # Напитки (Чай)
    ("ЧАЙ С лимоном", "10", "Меню", "", "", now),
    ("ЧАЙ С лимон и имбирем", "15", "Меню", "", "", now),
    ("ЧАЙ ФРУКТОВЫЙ", "20", "Меню", "", "", now),
    ("ЧАЙ ФРУКТОВАЯ ЭКЗОТИКА", "24", "Меню", "", "", now),
]

for item in missing_items:
    name, price, cat, sub, img, created = item
    try:
        cur.execute("""
            INSERT INTO foods (name, price, category, subcategory, image_url, created)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (name) DO NOTHING
        """, (name, price, cat, sub, img, created))
        print(f"Added: {name} - {price}с")
    except Exception as e:
        print(f"Error adding {name}: {e}")

# Update СТЕЙК ИЗ ГОВЯДИНЫ price from 50 to 28
cur.execute("UPDATE foods SET price = '28' WHERE name = 'СТЕЙК ИЗ ГОВЯДИНЫ'")
print("Updated СТЕЙК ИЗ ГОВЯДИНЫ price to 28с")

conn.commit()
conn.close()
print("\nDone! All missing items added.")