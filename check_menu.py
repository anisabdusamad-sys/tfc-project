import psycopg2

DATABASE_URL = 'postgresql://tfcdb_4eoa_user:hIRovZCZRqkCxstsP3U98O5bRzjNLlm0@dpg-d8rnghmgvqtc73f9lmj0-a.virginia-postgres.render.com/tfcdb_4eoa'
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
cur.execute('SELECT name, price, category, subcategory FROM foods ORDER BY category, name')
rows = cur.fetchall()
print('Total items:', len(rows))
for r in rows:
    print(f"{r[0]} | {r[1]} | {r[2]} | {r[3]}")
conn.close()