@echo off
cd /d "%~dp0"

py -c "import customtkinter" >nul 2>&1

if errorlevel 1 (
    echo Instalando la interfaz grafica por primera vez...
    py -m pip install -r requirements.txt

    if errorlevel 1 (
        echo.
        echo No se pudo instalar CustomTkinter.
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
