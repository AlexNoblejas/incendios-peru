@echo off
REM ====================================================================
REM  Incendios en Manantay - ejecuta todo el analisis de punta a punta.
REM  Doble clic en este archivo, o desde Anaconda Prompt: EJECUTAR.bat
REM ====================================================================
cd /d "%~dp0"
echo.
echo [1/5] Instalando dependencias (la primera vez tarda unos minutos)...
python -m pip install -q -r requirements.txt
if errorlevel 1 goto error

echo [2/5] Ejecutando el notebook (descarga datos y calcula; 10-20 min)...
python -m jupyter nbconvert --to notebook --execute --inplace ^
    --ExecutePreprocessor.timeout=1800 ^
    notebooks\incendios_manantay.ipynb
if errorlevel 1 goto error

echo [3/5] Exportando las geometrias del mapa...
python scripts\exportar_mapa.py
if errorlevel 1 goto error

echo [4/5] Generando el README con las cifras reales...
python scripts\render_readme.py
if errorlevel 1 goto error

echo [5/5] Generando el dashboard HTML...
python scripts\build_dashboard.py
if errorlevel 1 goto error

echo.
echo ===================================================================
echo  LISTO. Revisa:
echo    README.md                  (los 3 hallazgos con numeros)
echo    outputs\dashboard.html     (el tablero para presentar)
echo    outputs\mapa_manantay.html (el mapa)
echo    outputs\hallazgos.json     (todas las cifras)
echo ===================================================================
pause
exit /b 0

:error
echo.
echo *** Algo fallo. Copia el mensaje de arriba y pegalo en el chat. ***
pause
exit /b 1
