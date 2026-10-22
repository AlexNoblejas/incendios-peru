@echo off
REM  Genera el terreno 3D (Copernicus DEM + Sentinel-2) y rearma el tablero.
cd /d "%~dp0"
echo Instalando lo que falte...
python -m pip install -q odc-stac rioxarray pystac-client planetary-computer
echo.
echo Generando la escena 3D (baja el DEM; 2-4 min)...
python scripts\exportar_3d.py
if errorlevel 1 goto error
echo.
echo Rearmando el tablero...
python scripts\build_dashboard.py
if errorlevel 1 goto error
echo.
echo ===================================================================
echo  LISTO: outputs\dashboard.html ahora incluye la vista 3D
echo ===================================================================
pause
exit /b 0

:error
echo.
echo *** Fallo. Copia el mensaje de arriba y pegalo en el chat. ***
pause
exit /b 1
