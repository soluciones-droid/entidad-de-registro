$job = Start-Job {
    Set-Location "C:\Users\user\Documents\entidad registradora"
    .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
}
Start-Sleep -Seconds 3
.\.venv\Scripts\python.exe .\scratch\test_flow.py
Stop-Job -Job $job
