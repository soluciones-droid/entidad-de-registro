
import sqlite3
import json

def check_db():
    conn = sqlite3.connect('data/ra.db')
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT request_id, applicant_json FROM registration_requests LIMIT 5")
        rows = cursor.fetchall()
        for row in rows:
            print(f"ID: {row[0]}")
            data = json.loads(row[1])
            print(f"Data keys: {list(data.keys())}")
            print(f"Issuance Mode: {data.get('issuance_mode')}")
            print("-" * 20)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_db()
