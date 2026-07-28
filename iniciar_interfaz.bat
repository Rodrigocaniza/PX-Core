@echo off
cd /d "%~dp0"

py -c "import customtkinter, openpyxl, reportlab" >nul 2>&1

if errorlevel 1 (
    echo Instalando o actualizando componentes de BC Gestion...
    py -m pip install -r requirements.txt

    if errorlevel 1 (
        echo.
        echo No se pudieron instalar los componentes necesarios.
        echo Revisa la conexion a internet e intenta nuevamente.
        pause
        exit /b 1
    )
)

py interfaz.py

if errorlevel 1 (
    echo.
    echo La interfaz se cerro con un error.
    pause
)
