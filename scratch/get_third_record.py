
import sqlite3
import json

def get_third_record():
    db_path = 'C:/Users/user/Documents/BD_ER/ra.db'
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # OFFSET 2 gets the 3rd record
    c.execute('SELECT request_id, status, created_at, applicant_json FROM registration_requests ORDER BY created_at DESC LIMIT 1 OFFSET 2')
    row = c.fetchone()
    if not row:
        print("No se encontró el tercer registro.")
        return
    
    request_id, status, created_at, app_json = row
    app = json.loads(app_json)
    
    print(f"--- DETALLES DEL TERCER REGISTRO ---")
    print(f"ID del Trámite: {request_id}")
    print(f"Estado: {status}")
    print(f"Fecha: {created_at}")
    print(f"Nombre: {app.get('given_name')} {app.get('first_surname')} {app.get('second_surname') or ''}")
    print(f"DNI: {app.get('dni')}")
    print(f"Email: {app.get('email')}")
    print(f"Modalidad: {app.get('issuance_mode')}")
    print(f"¿Tiene CSR?: {'SÍ' if app.get('csr_pem') else 'NO'}")
    print(f"------------------------------------")
    conn.close()

if __name__ == "__main__":
    get_third_record()
