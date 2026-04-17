
import sqlite3

def check_schema():
    db_path = 'C:/Users/user/Documents/BD_ER/ra.db'
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in c.fetchall()]
    print(f"Tablas encontradas: {tables}")
    
    if 'capture_sessions' in tables:
        c.execute("PRAGMA table_info(capture_sessions)")
        cols = [r[1] for r in c.fetchall()]
        print(f"Columnas en capture_sessions: {cols}")
    else:
        print("ALERTA: La tabla 'capture_sessions' NO existe.")
    
    conn.close()

if __name__ == "__main__":
    check_schema()
