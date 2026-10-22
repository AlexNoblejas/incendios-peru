@echo off
cd /d "%~dp0"
echo Instalando dependencias...
python -m pip install -q -r requirements.txt
echo.
echo Probando las fuentes que necesitan internet...
python scripts\probar_fuentes.py
echo.
pause
