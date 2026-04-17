from sqlalchemy import create_engine, text
import os

# Updated path from .env
db_url = "sqlite:///c:/Users/user/Documents/BD_ER/ra.db"
engine = create_engine(db_url)

with engine.connect() as conn:
    # Check tables
    result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
    print("Tables in DB:", [row[0] for row in result])
    
    try:
        result = conn.execute(text("SELECT session_id, status, selfie_path, expires_at FROM capture_sessions ORDER BY expires_at DESC LIMIT 5"))
        print("\nSessions:")
        for row in result:
            print(f"ID: {row[0]}, Status: {row[1]}, Path: {row[2]}, Expires: {row[3]}")
    except Exception as e:
        print(f"\nError querying sessions: {e}")
