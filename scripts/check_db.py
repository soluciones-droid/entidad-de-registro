import sqlite3
import json

conn = sqlite3.connect('data/ra.db')
rows = conn.execute('SELECT request_id, status, applicant_json, certificate_pem, reniec_result_json FROM registration_requests ORDER BY created_at DESC LIMIT 5').fetchall()

for r in rows:
    req_id = r[0]
    status = r[1]
    applicant = json.loads(r[2])
    has_cert = r[3] is not None
    reniec = json.loads(r[4])
    
    mode = applicant.get('issuance_mode')
    has_csr = applicant.get('csr_pem') is not None
    
    print(f"ID: {req_id} | Status: {status} | Name: {applicant.get('given_name')} | Mode: {mode} | Has CSR: {has_csr}")
