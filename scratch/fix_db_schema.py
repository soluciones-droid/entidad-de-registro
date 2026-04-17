
import sqlite3

def check_columns():
    conn = sqlite3.connect('data/ra.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(registration_requests)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"Current columns: {columns}")
    
    required = [
        "request_id", "created_at", "updated_at", "status", "applicant_json", 
        "reniec_result_json", "review_note", "certificate_pem", 
        "dni_front_path", "dni_back_path", "selfie_path", "liveness_path", 
        "issuance_mode"
    ]
    
    missing = [c for c in required if c not in columns]
    if missing:
        print(f"Missing columns: {missing}")
        for col in missing:
            print(f"Adding column: {col}")
            try:
                # Type mapping for simplicity
                type_map = {
                    "issuance_mode": "VARCHAR(20) DEFAULT 'local'",
                    "dni_front_path": "VARCHAR(500)",
                    "dni_back_path": "VARCHAR(500)",
                    "selfie_path": "VARCHAR(500)",
                    "liveness_path": "VARCHAR(500)"
                }
                col_type = type_map.get(col, "TEXT")
                cursor.execute(f"ALTER TABLE registration_requests ADD COLUMN {col} {col_type}")
                print(f"Column {col} added successfully.")
            except Exception as e:
                print(f"Error adding {col}: {e}")
    else:
        print("No columns missing.")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    check_columns()
