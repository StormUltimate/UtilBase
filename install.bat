@echo off
chcp 65001 >nul
echo ============================================
echo   UtilBase — установка после клонирования
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo Ошибка: Python не найден. Установите Python 3.10+ и добавьте в PATH.
    pause
    exit /b 1
)

echo [1/5] Создание виртуального окружения...
if exist venv (
    echo Папка venv уже есть. Пропуск.
) else (
    python -m venv venv
    if errorlevel 1 (
        echo Не удалось создать venv.
        pause
        exit /b 1
    )
)
echo.

echo [2/5] Активация venv и установка зависимостей...
call venv\Scripts\activate
pip install --upgrade pip -q
pip install -r requirements.txt
if errorlevel 1 (
    echo Ошибка при установке пакетов.
    pause
    exit /b 1
)
echo.

echo [3/5] Файл настроек .env...
if not exist .env (
    copy .env.example .env
    echo Создан .env из .env.example. Отредактируйте .env (БД, ключи).
) else (
    echo .env уже существует.
)
echo.

echo [4/5] Переменные окружения для Flask...
set FLASK_APP=run:app
echo.

echo [5/5] Применение миграций БД...
flask db upgrade
if errorlevel 1 (
    echo Предупреждение: миграции не применены. Проверьте .env и PostgreSQL.
    echo Создайте БД: createdb utilbase
) else (
    echo Миграции применены успешно.
)
echo.

echo ============================================
echo   Установка завершена.
echo   Отредактируйте .env, затем запустите: start run.bat
echo ============================================
pause
