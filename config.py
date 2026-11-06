"""
Конфигурация проекта Andrey AI Lab.
Все чувствительные и изменяемые параметры вынесены сюда.
"""
import os


class Config:
    # Flask. В production задавайте SECRET_KEY переменной окружения;
    # без него генерируется случайный ключ и сессии сбрасываются при перезапуске.
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(32).hex()

    # База данных SQLite
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'site.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Лимиты запросов
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

    # Telegram для кнопки «Обсудить задачу»
    TELEGRAM_URL = os.environ.get(
        'TELEGRAM_URL',
        'https://t.me/a7onoff72'
    )

    # Администратор. Пароль — только через переменные окружения (.env на сервере,
    # не коммитьте его в git).
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
    if not ADMIN_PASSWORD:
        raise RuntimeError(
            'ADMIN_PASSWORD не задан. Укажите его в .env или переменных окружения.'
        )

    # Логирование
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.path.join(BASE_DIR, 'logs', 'app.log')
