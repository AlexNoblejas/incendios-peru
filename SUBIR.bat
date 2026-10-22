@echo off
REM ====================================================================
REM  Sube el repo a GitHub. Antes crea el repositorio VACIO en
REM  https://github.com/new  con el nombre: incendios-peru
REM  (publico, SIN README y SIN .gitignore)
REM ====================================================================
cd /d "%~dp0"
set REPO=https://github.com/AlexNoblejas/incendios-peru.git

echo Conectando con %REPO%
git remote remove origin 2>nul
git remote add origin %REPO%
git branch -M main

echo.
echo Subiendo... (si pide usuario y clave, usa tu usuario de GitHub y un
echo token personal como contrasena: github.com/settings/tokens)
git push -u origin main
if errorlevel 1 goto error

echo.
echo ===================================================================
echo  LISTO: https://github.com/AlexNoblejas/incendios-peru
echo ===================================================================
pause
exit /b 0

:error
echo.
echo *** Fallo el push. Copia el mensaje de arriba y pegalo en el chat. ***
pause
exit /b 1
