"""Клиент GigaChat для чат-ассистента (генерация ответов).

Авторизация — через переменные окружения (см. .env.example):
- GIGACHAT_CREDENTIALS — Authorization key (base64) из личного кабинета developers.sber.ru, либо
- GIGACHAT_CLIENT_ID + GIGACHAT_CLIENT_SECRET — пара, из которой ключ собирается сам.
Опционально: GIGACHAT_SCOPE (по умолчанию GIGACHAT_API_PERS),
GIGACHAT_MODEL (по умолчанию GigaChat-2).

Эмбеддинги не отсюда: поиск по индексу — локальная модель fastembed
(см. backend/embeddings.py), данные не покидают сервер.
"""
import base64
import os
from typing import Optional

from gigachat import GigaChat

DEFAULT_SCOPE = 'GIGACHAT_API_PERS'
DEFAULT_CHAT_MODEL = 'GigaChat-2'


def get_credentials() -> Optional[str]:
    """Возвращает Authorization key для GigaChat или None, если не настроено."""
    credentials = os.getenv('GIGACHAT_CREDENTIALS')
    if credentials:
        return credentials.strip()

    client_id = os.getenv('GIGACHAT_CLIENT_ID')
    client_secret = os.getenv('GIGACHAT_CLIENT_SECRET')
    if client_id and client_secret:
        pair = f'{client_id.strip()}:{client_secret.strip()}'
        return base64.b64encode(pair.encode('utf-8')).decode('ascii')
    return None


def get_chat_model() -> str:
    return os.getenv('GIGACHAT_MODEL', DEFAULT_CHAT_MODEL)


def create_client() -> Optional[GigaChat]:
    """Создаёт клиента GigaChat; None, если данные авторизации не заданы."""
    credentials = get_credentials()
    if not credentials:
        return None
    return GigaChat(
        credentials=credentials,
        scope=os.getenv('GIGACHAT_SCOPE', DEFAULT_SCOPE),
        model=get_chat_model(),
        verify_ssl_certs=os.getenv('GIGACHAT_VERIFY_SSL', '0') == '1',
        timeout=60,
    )
