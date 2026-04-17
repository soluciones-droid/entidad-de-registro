
import urllib.request
import os

url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
dest = "cloudflared.exe"

print(f"Descargando desde {url}...")
try:
    urllib.request.urlretrieve(url, dest)
    if os.path.exists(dest):
        print(f"¡Éxito! Archivo guardado como {dest} ({os.path.getsize(dest)} bytes)")
    else:
        print("Error: El archivo no se guardó.")
except Exception as e:
    print(f"Error durante la descarga: {e}")
