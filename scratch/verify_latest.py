
import sqlite3
import json

def verify_latest():
    conn = sqlite3.connect('data/ra.db')
    c = conn.cursor()
    c.execute('SELECT request_id, status, created_at, applicant_json FROM registration_requests ORDER BY created_at DESC LIMIT 1')
    row = c.fetchone()
    if not row:
        print("No se encontraron solicitudes.")
        return
    
    request_id, status, created_at, applicant_json = row
    payload = json.loads(applicant_json)
    
    print(f"--- DETALLES DE LA SOLICITUD ---")
    print(f"ID: {request_id}")
    print(f"Estado: {status}")
    print(f"Fecha: {created_at}")
    print(f"Solicitante: {payload.get('given_name')} {payload.get('first_surname')}")
    print(f"Modo de Emisión: {payload.get('issuance_mode')}")
    print(f"CSR Presente: {'SÍ' if payload.get('csr_pem') else 'NO (Modo HSM/Remoto)'}")
    print(f"Email: {payload.get('email')}")
    print(f"--------------------------------")

if __name__ == "__main__":
    verify_latest()
