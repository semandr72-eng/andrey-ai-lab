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

sudo systemctl restart andrey-ai-lab
sleep 2
sudo systemctl is-active --quiet andrey-ai-lab

echo "Deploy OK"
