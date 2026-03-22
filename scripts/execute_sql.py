import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.environ.get("DATABASE_URL")

def execute_sql_file(file_path):
    print(f"Executing {file_path}...")
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            with open(file_path, 'r') as f:
                cur.execute(f.read())
        conn.close()
        print(f"Successfully executed {file_path}")
    except Exception as e:
        print(f"Error executing {file_path}: {e}")

if __name__ == "__main__":
    execute_sql_file("database/create_posts_table.sql")
    execute_sql_file("database/set_test_articles.sql")
