"""
Andrey AI Lab — личный сайт фрилансера по ИИ-ассистентам для бизнеса.

Основной файл приложения на Flask:
- модели SQLAlchemy (заявки, пользователь-админ),
- формы Flask-WTF с CSRF-защитой,
- публичные страницы и админ-панель,
- логирование запросов и отправки форм.
"""

import logging
import os
from datetime import datetime

import numpy as np
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, abort, Response, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin,
    login_user, login_required, logout_user, current_user
)
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from openai import OpenAI
from wtforms import StringField, TextAreaField, SubmitField, SelectField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Email, Length
from werkzeug.security import generate_password_hash, check_password_hash

from backend.rag_index import load_index, search_similar
from config import Config

# ---------------------------------------------------------------------------
# Инициализация приложения
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
csrf = CSRFProtect(app)
login_manager.login_view = 'admin_login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к админ-панели.'

# ---------------------------------------------------------------------------
# Логирование
# ---------------------------------------------------------------------------
os.makedirs(os.path.dirname(Config.LOG_FILE), exist_ok=True)

file_handler = logging.FileHandler(Config.LOG_FILE, encoding='utf-8')
file_handler.setLevel(getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO))
formatter = logging.Formatter(
    '%(asctime)s — %(levelname)s — %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)

if not any(isinstance(h, logging.FileHandler) for h in app.logger.handlers):
    app.logger.addHandler(file_handler)
app.logger.setLevel(getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO))


@app.before_request
def log_request_info():
    """Логируем каждый входящий HTTP-запрос."""
    app.logger.info('%s %s — %s', request.method, request.path, request.remote_addr)


@app.context_processor
def inject_globals():
    """Делаем часто используемые значения доступными во всех шаблонах."""
    return {
        'telegram_url': Config.TELEGRAM_URL,
    }


# ---------------------------------------------------------------------------
# Модели базы данных
# ---------------------------------------------------------------------------
class User(UserMixin, db.Model):
    """Пользователь админ-панели. В БД создаётся один администратор при старте."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class ContactMessage(db.Model):
    """Заявка из формы обратной связи."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    subject = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def subject_label(self) -> str:
        """Возвращает человекочитаемое название темы."""
        labels = {
            'consultation': 'Консультация',
            'project': 'Разработка под ключ',
            'support': 'Поддержка и доработка',
            'other': 'Другое',
        }
        return labels.get(self.subject, self.subject)


# ---------------------------------------------------------------------------
# WTForms-формы
# ---------------------------------------------------------------------------
class ContactForm(FlaskForm):
    """Форма обратной связи на странице контактов."""
    name = StringField(
        'Имя',
        validators=[DataRequired(message='Укажите имя'), Length(max=100)]
    )
    email = StringField(
        'Email',
        validators=[
            DataRequired(message='Укажите email'),
            Email(message='Некорректный email'),
            Length(max=120)
        ]
    )
    phone = StringField(
        'Телефон',
        validators=[Length(max=20, message='Слишком длинный номер')]
    )
    subject = SelectField(
        'Тема сообщения',
        choices=[
            ('', 'Выберите тему'),
            ('consultation', 'Консультация'),
            ('project', 'Разработка под ключ'),
            ('support', 'Поддержка и доработка'),
            ('other', 'Другое'),
        ],
        validators=[DataRequired(message='Выберите тему')]
    )
    message = TextAreaField(
        'Текст сообщения',
        validators=[
            DataRequired(message='Напишите сообщение'),
            Length(min=10, max=5000, message='Сообщение от 10 до 5000 символов')
        ]
    )
    consent = BooleanField(
        'Согласен на обработку персональных данных',
        validators=[DataRequired(message='Необходимо согласие на обработку персональных данных')]
    )
    submit = SubmitField('Отправить сообщение')


class LoginForm(FlaskForm):
    """Форма входа в админ-панель."""
    username = StringField(
        'Логин',
        validators=[DataRequired(message='Введите логин')]
    )
    password = PasswordField(
        'Пароль',
        validators=[DataRequired(message='Введите пароль')]
    )
    submit = SubmitField('Войти')


# ---------------------------------------------------------------------------
# Данные кейсов
# ---------------------------------------------------------------------------
CASES = [
    {
        'slug': 'reclamation-rag-bot',
        'number': '01',
        'title': 'RAG-бот для отдела рекламации',
        'short': 'Отвечает сотрудникам по базе знаний, снижает нагрузку на операторов и ускоряет обработку претензий.',
        'tags': ['RAG', 'Python', 'LangChain', 'Telegram'],
        'github': 'https://github.com/semandr72-eng/reclamation-rag-bot',
        'image': 'case-reclamation.svg',
        'details': (
            'Чат-бот на базе Retrieval-Augmented Generation для отдела рекламации производственной компании. '
            'Загружает инструкции, регламенты и историю обращений, после чего моментально отвечает клиентам '
            'в Telegram на вопросы о гарантии, возвратах и сроках. '
            'Если бот не уверен в ответе — переводит диалог на human-агента с полным контекстом.'
        ),
    },
    {
        'slug': 'ai-hr-assistant',
        'number': '02',
        'title': 'ИИ-ассистент для HR',
        'short': 'Отвечает сотрудникам по корпоративной базе знаний, кэширует ответы и оценивает качество RAG-пайплайна.',
        'tags': ['HR', 'RAG', 'FastAPI', 'ChromaDB', 'OpenAI', 'GigaChat'],
        'github': 'https://github.com/semandr72-eng/ai-hr--company-assistant',
        'image': 'case-hr.svg',
        'details': (
            'Готовый AI-ассистент для сотрудников и специалистов отдела по работе с персоналом. '
            'Построен на RAG-архитектуре: ищет по корпоративной базе знаний и генерирует ответы на основе найденных документов. '
            'Использует FastAPI, ChromaDB для векторного поиска и sentence-transformers для эмбеддингов. '
            'Поддерживает OpenAI GPT и российскую модель GigaChat. '
            'Реализовано кэширование ответов на SQLite для снижения нагрузки на LLM и ускорения повторных запросов. '
            'Включает оценку качества RAGAS по метрикам Faithfulness и Answer Relevance.'
        ),
    },
    {
        'slug': 'smm-assistant-bot',
        'number': '03',
        'title': 'SMM-ассистент для контент-менеджеров',
        'short': 'Генерирует посты, хэштеги и идеи контента по заданному тону и тематике бренда.',
        'tags': ['SMM', 'GPT', 'Automation', 'Content'],
        'github': 'https://github.com/semandr72-eng/smm-assistant-bot',
        'image': 'case-smm.svg',
        'details': (
            'Инструмент для команды SMM: создаёт черновики постов, подбирает хэштеги и предлагает форматы визуала '
            'на основе описания продукта и целевой аудитории. '
            'Контент-менеджер остаётся редактором, но рутинная генерация идей уходит боту.'
        ),
    },
    {
        'slug': 'bond-ai-bot',
        'number': '04',
        'title': 'BondAI — поиск облигаций на Мосбирже',
        'short': 'Помогает инвесторам подбирать облигации по параметрам: доходность, срок, надежность эмитента.',
        'tags': ['Finance', 'Moscow Exchange', 'Python', 'Data'],
        'github': 'https://github.com/semandr72-eng/bond--ai--bot',
        'image': 'case-bond.svg',
        'details': (
            'Telegram-бот для частных инвесторов, который фильтрует облигаги Московской биржи '
            'по заданным критериям: доходность к погашению, дюрация, кредитный рейтинг, отрасль. '
            'Выдаёт краткую сводку и ссылки на карточки инструментов, экономя время на ручной анализ.'
        ),
    },
    {
        'slug': 'orderhunter',
        'number': '05',
        'title': 'OrderHunter — многоагентная система поиска заказов',
        'short': 'Агенты мониторят площадки, фильтруют тендеры и передают релевантные заявки на проверку эксперту.',
        'tags': ['Multi-agent', 'Human-in-the-loop', 'In Progress'],
        'github': None,
        'image': 'case-orderhunter.svg',
        'details': (
            'Система из нескольких специализированных агентов: сборщик заявок с площадок, фильтр по критериям заказчика, '
            'ранжирование по приоритету и передача лучших вариантов человеку для финального решения. '
            'Проект находится в активной разработке; сейчас прототипируется архитектура взаимодействия агентов.'
        ),
    },
    {
        'slug': 'rag-assistant-logging',
        'number': '06',
        'title': 'RAG-ассистент с логированием и метриками',
        'short': 'Отвечает по базе знаний, кэширует ответы и фиксирует каждое обращение в SQLite: кто, когда, что спросил и сколько ждал ответа.',
        'tags': ['RAG', 'Logging', 'SQLite', 'ChromaDB', 'Telegram', 'VPS'],
        'github': 'https://github.com/semandr72-eng/rag-assistant-logging',
        'image': 'case-logging.svg',
        'details': (
            'Telegram-бот на базе RAG (ChromaDB + OpenAI), развёрнутый на VPS в Нидерландах и работающий 24/7. '
            'Ключевая особенность — полный цикл логирования: каждый запрос пишется в SQLite '
            '(вопрос, ответ, user_id, источник, время ответа в мс, признак ответа из кэша). '
            'Пользователь может запросить статистику командой /stats и выгрузить свои логи в CSV через /logs — '
            'при этом каждый видит только свои данные. '
            'По итогам тестов: почти треть обращений обслуживается кэшем мгновенно и без затрат на API, '
            'среднее время ответа ~3,5 секунды. '
            'Попробовать бота: <a class="bot-link" href="https://t.me/semenov_rag_assistant_bot">👉 @semenov_rag_assistant_bot</a> в Telegram.'
        ),
    },
    {
        'slug': 'ai-curator-platform',
        'number': '07',
        'title': 'ИИ-куратор образовательной платформы',
        'short': 'RAG-ассистент для онлайн-курса: отвечает на учебные и организационные вопросы, подстраивает ответ под уровень студента и подсказывает дедлайны из LMS.',
        'tags': ['EdTech', 'RAG', 'Streamlit', 'ChromaDB', 'DeepSeek', 'OpenAI'],
        'github': 'https://github.com/semandr72-eng/Ai-curator',
        'image': 'case-curator.svg',
        'details': (
            'RAG-ассистент для онлайн-курса, который закрывает сопровождение студентов между вебинарами. '
            'Отвечает на учебные вопросы по материалам курса и на организационные — по регламентам платформы, '
            'а также подсказывает ближайшие дедлайны, подтягивая данные из LMS. '
            'Ответ подстраивается под уровень студента: новичку объясняет базовые термины, опытному — сразу по делу. '
            'Интерфейс собран на Streamlit, векторный поиск — на Chroma, генерация — через DeepSeek или OpenAI API.'
        ),
    },
    {
        'slug': 'faq-assistant-portfolio',
        'number': '08',
        'title': 'ИИ-ассистент для сайта-портфолио',
        'short': 'Чат-виджет с RAG на FAISS: отвечает посетителям на вопросы об услугах, кейсах и ценах строго по базе знаний — прямо на сайте и в Telegram-боте.',
        'tags': ['RAG', 'FastAPI', 'FAISS', 'OpenAI', 'Telegram', 'Widget'],
        'github': 'https://github.com/semandr72-eng/faq-assistant',
        'image': 'case-faq.svg',
        'details': (
            'Чат-виджет, который работает первой линией на сайте-портфолио: отвечает посетителям на вопросы '
            'об услугах, кейсах и ценах строго по базе знаний, не выдумывая за её пределами. '
            'Тот же ассистент доступен и в Telegram-боте — диалоги ведутся в привычном для клиента канале. '
            'Бэкенд на FastAPI, векторный индекс — FAISS, генерация ответов — через OpenAI API. '
            'Виджет установлен на этом сайте: иконка чата в правом нижнем углу.'
        ),
    },
]

BENEFITS = [
    {
        'number': '01',
        'title': 'Экономия времени до 50%',
        'text': 'Рутинные вопросы клиентов уходят боту: менеджеры фокусируются на продажах и сложных кейсах.'
    },
    {
        'number': '02',
        'title': 'Экономия денег',
        'text': 'Один чат-бот заменяет часть нагрузки на операторов и снижает затраты на первую линию поддержки.'
    },
    {
        'number': '03',
        'title': 'Ни одной потерянной заявки',
        'text': 'Бот принимает обращения круглосуточно, фиксирует контакты и передаёт их в CRM или менеджеру.'
    },
    {
        'number': '04',
        'title': 'Работа 24/7',
        'text': 'Клиенты получают мгновенные ответы вечером, ночью и в выходные — без простоя бизнеса.'
    },
    {
        'number': '05',
        'title': 'Логирование диалогов',
        'text': 'Все разговоры сохраняются: вы видите, что спрашивают клиенты, и можете анализировать запросы.'
    },
]

WORK_STEPS = [
    {
        'number': '01',
        'title': 'Бесплатный разбор задачи за 15 минут',
        'text': 'Обсуждаем процесс, который можно отдать ИИ, и понимаем, какой результат вам нужен.'
    },
    {
        'number': '02',
        'title': 'Точная цена и срок до старта',
        'text': 'Готовлю предложение с этапами, бюджетом и сроками — без скрытых платежей.'
    },
    {
        'number': '03',
        'title': 'Прототип за 1–2 дня',
        'text': 'Быстро собираю работающий прототип, чтобы вы могли протестировать его на реальных вопросах клиентов.'
    },
]


# ---------------------------------------------------------------------------
# Flask-Login loader
# ---------------------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


# ---------------------------------------------------------------------------
# Сервисные функции
# ---------------------------------------------------------------------------
def get_case_by_slug(slug: str):
    """Возвращает кейс по slug или None."""
    return next((c for c in CASES if c['slug'] == slug), None)


def create_admin_user():
    """Создаёт администратора при первом запуске, если его ещё нет в БД."""
    admin = User.query.filter_by(username=Config.ADMIN_USERNAME).first()
    if not admin:
        admin = User(
            username=Config.ADMIN_USERNAME,
            password_hash=generate_password_hash(Config.ADMIN_PASSWORD)
        )
        db.session.add(admin)
        db.session.commit()
        app.logger.info('Создан администратор: %s', Config.ADMIN_USERNAME)


# ---------------------------------------------------------------------------
# Чат-ассистент с RAG (OpenAI + FAISS)
# ---------------------------------------------------------------------------
load_dotenv()

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
if not openai_client:
    app.logger.warning('OPENAI_API_KEY не задан — чат-ассистент будет недоступен')

INDEX_PATH = os.path.join(Config.BASE_DIR, 'data', 'faiss_index.bin')
META_PATH = os.path.join(Config.BASE_DIR, 'data', 'faqs_metadata.npy')

try:
    # Индекс загружается один раз при старте приложения
    faiss_index, faq_metadata = load_index(INDEX_PATH, META_PATH)
    app.logger.info('RAG-индекс загружен: %s фрагментов', len(faq_metadata))
except RuntimeError as e:
    faiss_index, faq_metadata = None, None
    app.logger.warning('Не удалось загрузить RAG-индекс: %s', e)


def embed_query(text: str) -> np.ndarray:
    """Превращает текст в вектор через OpenAI text-embedding-3-small."""
    response = openai_client.embeddings.create(
        model='text-embedding-3-small',
        input=[text],
    )
    return np.array([response.data[0].embedding], dtype='float32')


# ---------------------------------------------------------------------------
# Публичные маршруты
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    """Главная страница сайта."""
    return render_template(
        'index.html',
        benefits=BENEFITS,
        cases=CASES,
        steps=WORK_STEPS
    )


@app.route('/cases/')
def cases():
    """Страница со списком кейсов."""
    return render_template('cases.html', cases=CASES)


@app.route('/cases/<slug>/')
def case_detail(slug: str):
    """Отдельная страница кейса."""
    case = get_case_by_slug(slug)
    if not case:
        abort(404)
    return render_template('case_detail.html', case=case)


@app.route('/about/')
def about():
    """Страница «Обо мне»."""
    return render_template('about.html')


@app.route('/privacy/')
def privacy():
    """Политика конфиденциальности."""
    return render_template('privacy.html')


@app.route('/contact/', methods=['GET', 'POST'])
def contact():
    """Страница с формой обратной связи."""
    form = ContactForm()

    if form.validate_on_submit():
        msg = ContactMessage(
            name=form.name.data.strip(),
            email=form.email.data.strip(),
            phone=form.phone.data.strip() if form.phone.data else None,
            subject=form.subject.data,
            message=form.message.data.strip()
        )
        db.session.add(msg)
        db.session.commit()

        app.logger.info(
            'Новая заявка от %s (%s), тема: %s',
            msg.name, msg.email, msg.subject_label()
        )
        flash('Спасибо! Сообщение отправлено — я свяжусь с вами в ближайшее время.', 'success')
        return redirect(url_for('contact'))

    return render_template('contact.html', form=form)


@app.route('/chat', methods=['POST'])
@csrf.exempt
def chat():
    """Чат-ассистент с RAG: эмбеддинг вопроса -> поиск в FAISS -> ответ gpt-4.1-mini."""
    if not openai_client or faiss_index is None:
        return jsonify({'error': 'Чат-ассистент временно недоступен'}), 503

    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({'error': 'Пустое сообщение'}), 400

    try:
        query_vec = embed_query(message)
        similar_items = search_similar(faiss_index, faq_metadata, query_vec, k=3)

        context_text = '\n\n'.join(
            f"Q: {item['question']}\nA: {item['answer']}" for item in similar_items
        )

        system_prompt = (
            'Ты ассистент Андрей AI Lab — сайта Андрея, который создаёт ИИ-ассистентов '
            'и чат-ботов для бизнеса. Отвечай кратко и по делу на русском языке, '
            'только на основе предоставленного контекста. '
            'Если информации нет в контексте — честно скажи об этом '
            'и предложи написать в Telegram @a7onoff72.'
        )

        completion = openai_client.chat.completions.create(
            model='gpt-4.1-mini',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': f'Вопрос посетителя: {message}\n\nКонтекст:\n{context_text}'},
            ],
            temperature=0.2,
        )
        answer = completion.choices[0].message.content.strip()
    except Exception as e:
        app.logger.error('Ошибка чат-ассистента: %s', e)
        return jsonify({'error': 'Не удалось получить ответ. Попробуйте позже или напишите в Telegram @a7onoff72'}), 503

    app.logger.info('Чат-ассистент: вопрос — %.100s', message)
    return jsonify({'answer': answer})


# ---------------------------------------------------------------------------
# Админ-панель
# ---------------------------------------------------------------------------
@app.route('/admin/', methods=['GET', 'POST'])
def admin_login():
    """Страница входа в админ-панель."""
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=True)
            app.logger.info('Администратор %s вошёл в систему', user.username)
            flash('Вы успешно вошли в админ-панель.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('admin_dashboard'))

        app.logger.warning(
            'Неудачная попытка входа: логин=%s, ip=%s',
            form.username.data, request.remote_addr
        )
        flash('Неверный логин или пароль.', 'error')

    return render_template('admin/login.html', form=form)


@app.route('/admin/dashboard/')
@login_required
def admin_dashboard():
    """Главная страница админ-панели со списком заявок."""
    page = request.args.get('page', 1, type=int)
    messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template('admin/dashboard.html', messages=messages)


@app.route('/admin/messages/<int:message_id>/read/', methods=['POST'])
@login_required
def admin_mark_read(message_id: int):
    """Отметить заявку как прочитанную / непрочитанную."""
    msg = ContactMessage.query.get_or_404(message_id)
    msg.is_read = not msg.is_read
    db.session.commit()
    app.logger.info('Заявка #%s отмечена как %s', message_id, 'прочитана' if msg.is_read else 'непрочитана')
    flash('Статус заявки обновлён.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/messages/<int:message_id>/delete/', methods=['POST'])
@login_required
def admin_delete_message(message_id: int):
    """Удалить заявку."""
    msg = ContactMessage.query.get_or_404(message_id)
    db.session.delete(msg)
    db.session.commit()
    app.logger.info('Заявка #%s удалена', message_id)
    flash('Заявка удалена.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/logout/')
@login_required
def admin_logout():
    """Выход из админ-панели."""
    app.logger.info('Администратор %s вышел из системы', current_user.username)
    logout_user()
    flash('Вы вышли из админ-панели.', 'success')
    return redirect(url_for('admin_login'))


# ---------------------------------------------------------------------------
# SEO-служебные страницы
# ---------------------------------------------------------------------------
@app.route('/robots.txt')
def robots_txt():
    """Файл robots.txt для поисковых роботов."""
    content = (
        "User-agent: *\n"
        "Disallow: /admin/\n"
        "Allow: /\n"
        f"Sitemap: {request.url_root.rstrip('/')}{url_for('sitemap_xml')}\n"
    )
    return Response(content, mimetype='text/plain')


@app.route('/sitemap.xml')
def sitemap_xml():
    """XML-карта сайта для поисковых систем."""
    base_url = request.url_root.rstrip('/')

    pages = [
        {'loc': url_for('index', _external=True), 'priority': '1.0'},
        {'loc': url_for('cases', _external=True), 'priority': '0.8'},
        {'loc': url_for('about', _external=True), 'priority': '0.7'},
        {'loc': url_for('contact', _external=True), 'priority': '0.8'},
        {'loc': url_for('privacy', _external=True), 'priority': '0.3'},
    ]

    for case in CASES:
        pages.append({
            'loc': url_for('case_detail', slug=case['slug'], _external=True),
            'priority': '0.6'
        })

    urls = []
    today = datetime.utcnow().strftime('%Y-%m-%d')
    for page in pages:
        urls.append(
            f"  <url>\n"
            f"    <loc>{page['loc']}</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <priority>{page['priority']}</priority>\n"
            f"  </url>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + '\n'.join(urls) +
        '\n</urlset>\n'
    )
    return Response(xml, mimetype='application/xml')


# ---------------------------------------------------------------------------
# Обработка ошибок
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(error):
    app.logger.warning('Страница не найдена: %s', request.path)
    return render_template('errors/404.html'), 404


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_admin_user()
    app.run(host='0.0.0.0', port=5000, debug=True)
