import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(db_url)

def fix_constraint():
    try:
        with engine.connect() as conn:
            # Drop the old constraint
            print("Dropping existing constraint...")
            conn.execute(text("ALTER TABLE articles DROP CONSTRAINT IF EXISTS articles_status_check"))
            
            # Add the new constraint with all required statuses
            print("Adding updated constraint...")
            conn.execute(text("""
                ALTER TABLE articles 
                ADD CONSTRAINT articles_status_check 
                CHECK (status IN (
                    'new', 'merged', 'summarised', 'pending', 'approved', 'rejected', 
                    'publish_approved', 'published', 'discarded', 'archived'
                ))
            """))
            conn.commit()
            print("Constraint successfully updated!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_constraint()
