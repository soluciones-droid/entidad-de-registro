# Entidad de Registro (RA) para OpenSSL + RENIEC

Este proyecto implementa una base de Entidad de Registro (Registration Authority, RA) en Python para actuar como intermediaria entre:

- una Autoridad Certificadora (CA) existente en OpenSSL
- una fuente oficial de validacion de identidad de RENIEC para biometria facial remota

La RA no reemplaza a la CA. Su funcion es:

1. recibir solicitudes de emision de certificados
2. validar identidad y evidencias
3. aplicar controles de seguridad y aprobacion
4. enviar el CSR a la CA OpenSSL para su firma
5. entregar el certificado emitido y la trazabilidad del proceso

## Alcance

La integracion con RENIEC se deja desacoplada porque el mecanismo exacto depende del acceso oficial disponible para tu organizacion:

- API privada o convenio institucional
- servicio SOAP/REST expuesto por tercero autorizado
- validacion presencial o semipresencial con contraste documental

Por eso el modulo `ReniecClient` define una interfaz segura que puedes adaptar al conector oficial que ya tengas contratado o habilitado.

## Arquitectura

- `app/main.py`: API FastAPI
- `app/models.py`: modelos de entrada y salida
- `app/security.py`: autenticacion simple por API key para operaciones sensibles
- `app/config.py`: configuracion por variables de entorno
- `app/services/reniec.py`: abstraccion de validacion RENIEC
- `app/services/openssl_ca.py`: emision de certificados usando la CA OpenSSL existente
- `app/services/registration.py`: orquestacion RA

## Flujo RA

1. El solicitante genera su par de claves y CSR.
2. La RA recibe:
   - DNI
   - nombres y apellidos
   - CSR en PEM
   - imagen frontal del DNI
   - imagen posterior del DNI
   - selfie del titular
   - imagen adicional para prueba de vida
   - evidencia de consentimiento y metadatos
3. La RA contrasta identidad y biometria facial con RENIEC o un integrador autorizado.
4. La RA valida que el subject del CSR coincida con la identidad oficial.
5. La RA marca la solicitud como:
    - `pending_manual_review`
    - `approved`
    - `rejected`
6. Si esta aprobada, la RA invoca `openssl ca` para firmar el CSR.
7. La RA devuelve el certificado y registra auditoria.

## Requisitos

- Python 3.11+
- OpenSSL instalado y accesible en PATH
- Una CA funcional en OpenSSL con:
  - `openssl.cnf`
  - base de datos de CA
  - serial
  - directorios de certificados
  - certificado y clave de CA

## Instalacion

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

## Configuracion

Copia `.env.example` a `.env` y ajusta:

```env
RA_API_KEY=super-secreta
OPENSSL_BIN=openssl
OPENSSL_CA_CONFIG=C:\ruta\ca\openssl.cnf
OPENSSL_CA_PROFILE=usr_cert
OPENSSL_CA_WORKDIR=C:\ruta\ca
EC_MODE=local
EC_API_URL=http://127.0.0.1:3000/api/ec/intake/approved-requests
EC_SOURCE_SYSTEM=ER-DEMO
EC_SHARED_SECRET=CAMBIAR-ESTE-SECRETO-EN-PRODUCCION
EC_HMAC_SECRET=CAMBIAR-HMAC-SECRET-EN-PRODUCCION
EC_HTTP_TIMEOUT=30
DATABASE_URL=sqlite:///./data/ra.db
RA_UPLOADS_DIR=.\data\uploads
RENIEC_MODE=api
RENIEC_API_URL=https://api.proveedor-biometrico.local/verify
RENIEC_API_TOKEN=change-token
RENIEC_HTTP_TIMEOUT=30
RENIEC_CLIENT_CERT_PATH=
RENIEC_CLIENT_KEY_PATH=
RENIEC_VERIFY_SSL=true
```

## Ejecucion

```bash
uvicorn app.main:app --reload
```

Primer arranque local:

```bash
pip install -e .
uvicorn app.main:app --reload
```

## Endpoints principales

- `GET /health`
- `POST /api/v1/requests`
- `POST /api/v1/requests/multipart`
- `GET /api/v1/requests/{request_id}`
- `POST /api/v1/requests/{request_id}/approve`
- `POST /api/v1/requests/{request_id}/reject`

## Ejemplo de solicitud

```json
{
  "dni": "12345678",
  "given_name": "JUAN",
  "first_surname": "PEREZ",
  "second_surname": "GOMEZ",
  "email": "juan@example.com",
  "certificate_profile": "natural_person",
  "csr_pem": "-----BEGIN CERTIFICATE REQUEST-----\n...\n-----END CERTIFICATE REQUEST-----",
  "consent_text": "Autorizo el tratamiento de mis datos para la emision del certificado digital.",
  "biometric_evidence": {
    "mode": "facial_remote",
    "dni_front_image_b64": "BASE64_IMAGEN_DNI_FRENTE",
    "dni_back_image_b64": "BASE64_IMAGEN_DNI_REVERSO",
    "selfie_image_b64": "BASE64_SELFIE",
    "liveness_image_b64": "BASE64_IMAGEN_LIVENESS",
    "device_id": "android-01",
    "capture_ip": "203.0.113.10"
  }
}
```

## Subject esperado en el CSR

Para reducir fraude, la RA ahora espera que el CSR contenga al menos:

- `CN=<NOMBRES Y APELLIDOS OFICIALES>`
- `serialNumber=<DNI>`

Ejemplo:

```text
subject=CN=JUAN PEREZ GOMEZ,serialNumber=12345678
```

Si el `CN` o el `serialNumber` no coinciden con la identidad validada, la RA no emitira el certificado.

## Generacion de CSR de prueba

El repositorio incluye una plantilla OpenSSL y un script PowerShell para generar un `CSR` compatible con la RA:

- plantilla: `openssl/request_persona_natural.cnf`
- script: `scripts/generate_test_csr.ps1`

Ejemplo:

```powershell
.\scripts\generate_test_csr.ps1 `
  -Dni 12345678 `
  -GivenName JUAN `
  -FirstSurname PEREZ `
  -SecondSurname GOMEZ `
  -Email juan@example.com
```

Esto genera:

- clave privada PEM
- CSR
- archivo `.cnf` resultante

El `CN` generado sera `JUAN PEREZ GOMEZ` y el `serialNumber` sera `12345678`.

## Carga de imagenes para RENIEC

Para acercarse al flujo real de RENIEC, la RA ahora soporta `multipart/form-data` con imagenes `JPG/JPEG`:

- `dni_front_image`
- `dni_back_image` opcional
- `selfie_image`
- `liveness_image` opcional

Las evidencias se almacenan en `RA_UPLOADS_DIR` y los metadatos del tramite se guardan en la base de datos.

## Ejemplo de prueba multipart

Puedes probar la RA localmente con `RENIEC_MODE=mock` y archivos `JPG/JPEG`.

Paso sugerido:

1. Generar el `CSR` con `scripts/generate_test_csr.ps1`.
2. Levantar la RA con `uvicorn app.main:app --reload`.
3. Enviar la solicitud `multipart`.
4. Aprobar la solicitud con `X-API-Key`.

Ejemplo con `curl`:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/requests/multipart" \
  -F "dni=12345678" \
  -F "given_name=JUAN" \
  -F "first_surname=PEREZ" \
  -F "second_surname=GOMEZ" \
  -F "email=juan@example.com" \
  -F "certificate_profile=natural_person" \
  -F "csr_pem=<C:/ruta/request.csr" \
  -F "consent_text=Autorizo el tratamiento de mis datos para la emision del certificado digital." \
  -F "device_id=android-01" \
  -F "capture_ip=203.0.113.10" \
  -F "dni_front_image=@C:/ruta/dni-front.jpg;type=image/jpeg" \
  -F "dni_back_image=@C:/ruta/dni-back.jpg;type=image/jpeg" \
  -F "selfie_image=@C:/ruta/selfie.jpg;type=image/jpeg" \
  -F "liveness_image=@C:/ruta/liveness.jpg;type=image/jpeg"
```

Ejemplo con PowerShell:

```powershell
$form = @{
  dni = "12345678"
  given_name = "JUAN"
  first_surname = "PEREZ"
  second_surname = "GOMEZ"
  email = "juan@example.com"
  certificate_profile = "natural_person"
  csr_pem = Get-Content "C:\ruta\request.csr" -Raw
  consent_text = "Autorizo el tratamiento de mis datos para la emision del certificado digital."
  device_id = "android-01"
  capture_ip = "203.0.113.10"
  dni_front_image = Get-Item "C:\ruta\dni-front.jpg"
  dni_back_image = Get-Item "C:\ruta\dni-back.jpg"
  selfie_image = Get-Item "C:\ruta\selfie.jpg"
  liveness_image = Get-Item "C:\ruta\liveness.jpg"
}

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/requests/multipart" `
  -Form $form
```

Para consultar o aprobar la solicitud debes enviar `X-API-Key` con el valor de `RA_API_KEY`.

Ejemplo de aprobacion:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/requests/REQUEST_ID/approve" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-ra-key" \
  -d "{\"note\":\"Validacion biometrica y documental conforme.\"}"
```

## Integracion HTTP del proveedor biometrico

En modo `RENIEC_MODE=api`, la RA envia un `POST` JSON al proveedor biometrico con:

- datos del titular
- `device_id`
- `capture_ip`
- imagen frontal del DNI en base64
- imagen posterior del DNI en base64 si existe
- selfie en base64
- imagen de liveness en base64 si existe

Si RENIEC o el integrador exige autenticacion mutua TLS, configura:

- `RENIEC_CLIENT_CERT_PATH`
- `RENIEC_CLIENT_KEY_PATH`

Si el proveedor entrega certificado y clave en un solo archivo PEM, usa solo `RENIEC_CLIENT_CERT_PATH`.

## Integracion remota con la EC

La RA ahora soporta dos modos de emision:

- `EC_MODE=local`: firma local con `openssl ca`
- `EC_MODE=remote`: envia la solicitud aprobada a la EC por HTTP

En modo remoto, la RA envia un `POST` JSON a `EC_API_URL` con los headers:

- `x-er-shared-secret`
- `x-er-signature`
- `x-er-timestamp`
- `x-er-nonce`

La firma `x-er-signature` se calcula como `HMAC-SHA256` del body JSON usando `EC_HMAC_SECRET`.

Variables requeridas:

- `EC_API_URL`
- `EC_SOURCE_SYSTEM`
- `EC_SHARED_SECRET`
- `EC_HMAC_SECRET`
- `EC_HTTP_TIMEOUT`

Si la EC responde `certificate_pem`, la solicitud pasa a `issued`. Si solo acepta el intake y no devuelve certificado en ese momento, la RA la deja en estado `approved`.

## Notas de seguridad

- Nunca generes la clave privada del usuario en la RA.
- El CSR debe venir desde el titular o su HSM/token.
- La RA debe comparar el resultado biometrico remoto antes de aprobar la firma.
- Protege la clave privada de la CA fuera de la RA si es posible.
- Usa doble control para aprobacion en produccion.
- Registra auditoria inmutable.
- No uses el modo `mock` de RENIEC fuera de laboratorio.
- Implementa prueba de vida y controles antifraude si la politica de certificacion lo exige.

## Integracion real con RENIEC

La RA ya tiene un conector HTTP base para integrarse con un proveedor autorizado. La respuesta esperada del servicio debe devolver:

- coincidencia de DNI
- nombres oficiales
- estado de identidad
- coincidencia facial
- resultado de liveness
- score de similitud
- codigo de transaccion de verificacion

## Siguientes pasos recomendados

1. conectar el cliente RENIEC real para biometria facial remota
2. cambiar `DATABASE_URL` a PostgreSQL para produccion
3. agregar firmas de auditoria
4. incorporar colas y aprobacion en dos pasos
5. agregar migraciones con Alembic
