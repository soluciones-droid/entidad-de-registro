import base64
import os
import subprocess
import requests

def run_test():
    print("1. Agregando OpenSSL al PATH...")
    os.environ["PATH"] += os.pathsep + r"C:\Program Files\OpenSSL-Win64\bin"

    print("2. Generando CSR usando el script proporcionado (Powershell puro)...")
    try:
        subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", r".\scripts\generate_test_csr.ps1", 
             "-Dni", "12345678", "-GivenName", "JUAN", "-FirstSurname", "PEREZ", "-SecondSurname", "GOMEZ", "-Email", "juan@example.com"],
            check=True,
            capture_output=True,
            text=True
        )
        print("   CSR Generado exitosamente.")
    except subprocess.CalledProcessError as e:
        print("Error generando CSR:")
        print(e.stderr)
        return

    print("3. Leyendo el CSR generado...")
    try:
        with open(r"demo-artifacts\12345678-persona-natural.csr", "r") as f:
            csr_pem = f.read()
    except FileNotFoundError:
        print("No se encontro el archivo CSR generado.")
        return

    print("4. Preparando imagenes simuladas...")
    dummy_image = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00\x43\x00\xff\xd9"

    files = {
        "dni_front_image": ("front.jpg", dummy_image, "image/jpeg"),
        "selfie_image": ("selfie.jpg", dummy_image, "image/jpeg"),
        "liveness_image": ("liveness.jpg", dummy_image, "image/jpeg"),
    }
    data = {
        "dni": "12345678",
        "given_name": "JUAN",
        "first_surname": "PEREZ",
        "second_surname": "GOMEZ",
        "email": "juan@example.com",
        "certificate_profile": "natural_person",
        "csr_pem": csr_pem,
        "consent_text": "Acepto los terminos."
    }

    print("5. Enviando peticion a la RA (Puerto 8000)...")
    try:
        # Envio multipart
        res = requests.post("http://127.0.0.1:8000/api/v1/requests/multipart", data=data, files=files)
        res.raise_for_status()
        res_json = res.json()
        request_id = res_json["request_id"]
        print(f"   Peticion recibida por RA. Estado: {res_json['status']}. Request ID: {request_id}")
    except requests.exceptions.RequestException as e:
        print("   Fallo envio a RA:", e)
        if hasattr(e.response, 'text'):
            print("   RA Response:", e.response.text)
        return

    print("6. Aprobando la solicitud en la RA (esto disparara la llamada a EC en puerto 30001)...")
    headers = {"X-API-Key": "dev-ra-key"}
    approve_data = {"note": "Validacion manual OK, enviando a EC."}
    
    try:
        # Aprobacion
        app_res = requests.post(f"http://127.0.0.1:8000/api/v1/requests/{request_id}/approve", json=approve_data, headers=headers)
        
        print(f"   Solicitud devuelta desde RA: HTTP {app_res.status_code}")
        print("   Resultado RA:", app_res.text)
        
        if app_res.status_code == 200:
            print(f"\n!!!! PRUEBA EXITOSA !!!!")
            print("La Entidad Registradora logro comunicarse con la Entidad Certificadora y aprobo el request.")
        else:
            print("\n!!!! FALLO EN LA RA O EN LA EC !!!!")
            
    except requests.exceptions.RequestException as e:
        print("   Fallo la comunicacion de Aprobacion a la RA:", e)

if __name__ == "__main__":
    run_test()
