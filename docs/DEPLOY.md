# Деплой Andrey AI Lab на сервер в РФ

Сайт собирает персональные данные через форму заявок — по политике
конфиденциальности и 152-ФЗ база данных должна находиться на сервере
в России. Зарубежные VPS и GitHub Pages для этого сайта не подходят.

Кандидаты хостинга (РФ-локация): Timeweb, Selectel, reg.ru, Yandex Cloud.
Ниже пример на чистом VPS с Ubuntu 24.04.

---

## 1. DNS

У регистратора semenov-ai.ru:

```
A-запись:  semenov-ai.ru      -> <IP сервера>
```

## 2. Первичная настройка сервера

```bash
ssh root@<IP>
apt update && apt upgrade -y
apt install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx

# Пользователь для деплоя и приложения
useradd -m -s /bin/bash deploy
mkdir -p /opt/andrey-ai-lab
chown deploy:deploy /opt/andrey-ai-lab

# Ключ для GitHub Actions (приватный ключ — в секрет DEPLOY_SSH_KEY,
# публичный — в /home/deploy/.ssh/authorized_keys)
mkdir -p /home/deploy/.ssh
# вставьте публичный ключ, затем:
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh && chmod 600 /home/deploy/.ssh/authorized_keys

# Деплойному пользователю — право перезапускать сервис без пароля
echo 'deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart andrey-ai-lab, /bin/systemctl is-active andrey-ai-lab' > /etc/sudoers.d/deploy
```

## 3. Код и окружение приложения

```bash
su - deploy
cd /opt/andrey-ai-lab
python3 -m venv .venv
# код доставит GitHub Actions (workflow deploy.yml), либо вручную:
# rsync -az --exclude '.git' --exclude '.venv' --exclude 'instance' ./ deploy@<IP>:/opt/andrey-ai-lab/

# Секреты на сервере — только вручную, в файл не в git:
cat > .env <<'EOF'
SECRET_KEY=<длинная случайная строка>
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<новый сильный пароль>
GIGACHAT_CLIENT_ID=<из developers.sber.ru>
GIGACHAT_CLIENT_SECRET=<из developers.sber.ru>
EOF
chmod 600 .env
```

## 4. RAG-индекс для чат-ассистента

Индекс строится на той же машине, где работает приложение:

```bash
cd /opt/andrey-ai-lab
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m backend.build_index
```

## 5. systemd-сервис

`/etc/systemd/system/andrey-ai-lab.service`:

```ini
[Unit]
Description=Andrey AI Lab site
After=network.target

[Service]
User=deploy
Group=deploy
WorkingDirectory=/opt/andrey-ai-lab
EnvironmentFile=/opt/andrey-ai-lab/.env
ExecStart=/opt/andrey-ai-lab/.venv/bin/gunicorn -w 3 -b 127.0.0.1:8000 app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now andrey-ai-lab
```

## 6. nginx и HTTPS

`/etc/nginx/sites-available/andrey-ai-lab`:

```nginx
server {
    listen 80;
    server_name semenov-ai.ru www.semenov-ai.ru;

    client_max_body_size 16m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
ln -s /etc/nginx/sites-available/andrey-ai-lab /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d semenov-ai.ru -d www.semenov-ai.ru
```

## 7. Секреты GitHub (Settings → Secrets → Actions)

| Секрет | Что положить |
|---|---|
| `DEPLOY_HOST` | IP сервера |
| `DEPLOY_USER` | `deploy` |
| `DEPLOY_SSH_KEY` | приватный SSH-ключ, публичная часть которого в authorized_keys |

После этого каждый push в `main` деплоит сайт автоматически
(workflow `.github/workflows/deploy.yml`): rsync кода → установка
зависимостей → перезапуск сервиса.

## 8. Блог

Блог (статический, без ПДн) живёт отдельно на GitHub Pages:
`https://semandr72-eng.github.io/andrey-ai-lab-/`. Поддомен
`blog.semenov-ai.ru` можно либо направить туда (CNAME на
`semandr72-eng.github.io` + custom domain в настройках репозитория),
либо обслуживать с этого же сервера — статикой через nginx.
