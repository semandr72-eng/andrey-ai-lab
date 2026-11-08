#!/usr/bin/env bash
# Вызывается на сервере из GitHub Actions (workflow deploy.yml)
# после rsync-копирования кода в /opt/andrey-ai-lab.
set -euo pipefail

APP_DIR=/opt/andrey-ai-lab
cd "$APP_DIR"

if [ ! -x .venv/bin/pip ]; then
  echo "Виртуальное окружение не найдено: создайте его по docs/DEPLOY.md"
  exit 1
fi

.venv/bin/pip install -q -r requirements.txt

# Подгружаем секреты из .env для проверки конфигурации
set -a
. ./.env
set +a

# Проверяем, что конфигурация в порядке (ADMIN_PASSWORD задан и т.п.)
.venv/bin/python -c "from config import Config; print('config OK')"

# База SQLite: создать/мигрировать при необходимости (idempotent).
# Папку instance создаём сами — sqlite файл не создаст её автоматически.
mkdir -p instance
.venv/bin/python - <<'PY'
from app import app, db, create_admin_user
with app.app_context():
    db.create_all()
    create_admin_user()
print('database OK')
PY

sudo systemctl restart andrey-ai-lab
sleep 2
sudo systemctl is-active --quiet andrey-ai-lab

echo "Deploy OK"
