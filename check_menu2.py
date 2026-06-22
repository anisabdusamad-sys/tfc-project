import psycopg2
import sys

DATABASE_URL = 'postgresql://tfcdb_4eoa_user:hIRovZCZRqkCxstsP3U98O5bRzjNLlm0@dpg-d8rnghmgvqtc73f9lmj0-a.virginia-postgres.render.com/tfcdb_4eoa'
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
cur.execute('SELECT name, price, category, subcategory FROM foods ORDER BY category, name')
rows = cur.fetchall()
with open('menu_output.txt', 'w', encoding='utf-8') as f:
    f.write(f'Total items: {len(rows)}\n')
    for r in rows:
        f.write(f"{r[0]} | {r[1]} | {r[2]} | {r[3]}\n")
conn.close()
print("Done! Check menu_output.txt")