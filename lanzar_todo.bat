@echo off
echo Lanzando API Python (puerto 8000)...
start "API Presupuestor" cmd /k "cd /d %~dp0api && uvicorn main:app --reload --port 8000"
timeout /t 2 /nobreak > nul

echo Lanzando Next.js (puerto 3000)...
start "Frontend Presupuestor" cmd /k "cd /d %~dp0frontend && npm run dev"
timeout /t 5 /nobreak > nul

echo Abriendo browser...
start chrome http://localhost:3000
