@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist venv\Scripts\activate.bat (
    echo Сначала выполните install.bat
    pause
    exit /b 1
)

call venv\Scripts\activate

:: Открыть браузер через 4 секунды (чтобы сервер успел стартовать)
start /min cmd /c "timeout /t 4 /nobreak >nul && start http://127.0.0.1:5000"

python run.py
if errorlevel 1 (
    echo.
    echo Завершено с ошибкой. Код: %errorlevel%
)
echo.
echo Нажмите любую клавишу для закрытия окна...
pause >nul
