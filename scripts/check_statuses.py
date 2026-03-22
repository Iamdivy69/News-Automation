import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(db_url)

def check_statuses():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT DISTINCT status FROM articles"))
        print("Distinct statuses in articles table:")
        for row in result:
            print(row[0])

if __name__ == "__main__":
    check_statuses()
