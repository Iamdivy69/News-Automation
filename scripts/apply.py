import psycopg2

with open('add_summaries_table.sql') as f:
    sql = f.read()

conn = psycopg2.connect("host=127.0.0.1 port=5432 dbname=news_system user=postgres")
with conn:
    with conn.cursor() as cur:
        cur.execute(sql)

print("SQL applied successfully!")
