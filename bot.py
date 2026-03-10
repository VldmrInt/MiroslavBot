import logging
import json
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, JobQueue

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Пути
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROXIES_DIR = os.path.join(BASE_DIR, 'proxies')
IMAGES_DIR = os.path.join(BASE_DIR, 'images')
DATA_FILE = os.path.join(BASE_DIR, 'data', 'users.json')

# Создаём директории
os.makedirs(PROXIES_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'data'), exist_ok=True)


def load_users_data() -> dict:
    """Загружает данные пользователей из JSON"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_users_data(data: dict) -> None:
    """Сохраняет данные пользователей в JSON"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_user_data(user_id: int) -> dict:
    """Получает данные пользователя или создаёт новые"""
    data = load_users_data()
    if str(user_id) not in data:
        data[str(user_id)] = {
            'username': '',
            'proxy_count': 0,
            'last_proxy': None,
            'last_proxy_time': None,
            'rating_asked': False
        }
        save_users_data(data)
    return data[str(user_id)]


def update_user_data(user_id: int, **kwargs) -> None:
    """Обновляет данные пользователя"""
    data = load_users_data()
    if str(user_id) in data:
        data[str(user_id)].update(kwargs)
    else:
        data[str(user_id)] = kwargs
    save_users_data(data)


def load_proxies_config() -> dict:
    """Загружает конфигурацию прокси из users.json"""
    config_file = os.path.join(PROXIES_DIR, 'users.json')
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки users.json: {e}")
    return {}


def load_proxies_for_user(username: str) -> list:
    """Загружает прокси для пользователя"""
    config = load_proxies_config()
    
    # Проверяем, относится ли пользователь к vip
    vip_users = config.get('vip_users', [])
    if username and username in vip_users and 'vip' in config:
        return config['vip']
    
    # Иначе используем default
    if 'default' in config:
        return config['default']
    
    return []


def get_next_proxy(username: str) -> str:
    """Получает следующий прокси с равномерным распределением (общий индекс для всех)"""
    global current_proxy_index
    
    proxies = load_proxies_for_user(username)
    if not proxies:
        return "Нет доступных прокси"
    
    proxy = proxies[current_proxy_index]
    current_proxy_index = (current_proxy_index + 1) % len(proxies)
    return proxy


# Общий индекс прокси для всех пользователей
current_proxy_index = 0


async def send_rating_request(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет запрос на оценку прокси через сутки"""
    job = context.job
    user_id = job.data['user_id']
    proxy = job.data['proxy']
    
    keyboard = [
        [InlineKeyboardButton("⭐ Отлично", callback_data=f'rating_good_{user_id}')],
        [InlineKeyboardButton("⭐⭐ Хорошо", callback_data=f'rating_ok_{user_id}')],
        [InlineKeyboardButton("⭐⭐⭐ Плохо", callback_data=f'rating_bad_{user_id}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"Как работает прокси {proxy}? Оцените качество:",
            reply_markup=reply_markup
        )
        logger.info(f"Запрос оценки отправлен пользователю {user_id}")
    except Exception as e:
        logger.error(f"Не удалось отправить запрос оценки {user_id}: {e}")


async def send_instructions(user_id: int, bot) -> None:
    """Отправляет 3 картинки-инструкции"""
    image_files = ['instruction1.jpg', 'instruction2.jpg', 'instruction3.jpg']
    
    for img in image_files:
        img_path = os.path.join(IMAGES_DIR, img)
        if os.path.exists(img_path):
            try:
                with open(img_path, 'rb') as photo:
                    await bot.send_photo(chat_id=user_id, photo=photo)
            except Exception as e:
                logger.error(f"Ошибка отправки {img}: {e}")
        else:
            logger.warning(f"Картинка {img} не найдена в папке images/")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    user = update.effective_user
    user_id = user.id
    username = user.username or ''
    
    # Сохраняем никнейм
    user_data = get_user_data(user_id)
    user_data['username'] = username
    update_user_data(user_id, username=username)
    
    keyboard = [[InlineKeyboardButton("Получить прокси", callback_data='new_proxy')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        'Добро пожаловать! Нажмите кнопку, чтобы получить прокси.',
        reply_markup=reply_markup
    )
    
    logger.info(f"Пользователь {username} ({user_id}) начал работу с ботом")


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    
    try:
        await query.answer()
    except Exception as e:
        logger.warning(f"Ошибка ответа на callback: {e}")
        return
    
    user = query.from_user
    user_id = user.id
    username = user.username or ''
    
    # Обработка оценки
    if query.data.startswith('rating_'):
        rating = query.data.split('_')[1]
        try:
            if rating == 'good':
                await query.edit_message_text("Спасибо! Рады, что всё работает! ✅")
                logger.info(f"Пользователь {user_id} оценил прокси как отличный")
            elif rating == 'ok':
                await query.edit_message_text("Хорошо, будем стараться лучше! 👍")
                logger.info(f"Пользователь {user_id} оценил прокси как хороший")
            elif rating == 'bad':
                await query.edit_message_text("Приносим извинения. Попробуйте получить новый прокси! 🔄")
                logger.info(f"Пользователь {user_id} оценил прокси как плохой")
        except Exception as e:
            logger.warning(f"Ошибка обновления сообщения оценки: {e}")
        
        # Обновляем флаг, что оценка получена
        update_user_data(user_id, rating_asked=True)
        return
    
    # Выдача прокси
    if query.data == 'new_proxy':
        proxy = get_next_proxy(username)
        
        # Обновляем данные пользователя
        user_data = get_user_data(user_id)
        proxy_count = user_data.get('proxy_count', 0) + 1
        update_user_data(
            user_id,
            proxy_count=proxy_count,
            last_proxy=proxy,
            last_proxy_time=datetime.now().isoformat()
        )
        
        # Логируем запрос
        logger.info(f"Пользователь {username} ({user_id}) получил прокси: {proxy} (запрос #{proxy_count})")
        
        keyboard = [[InlineKeyboardButton("Получить новый прокси", callback_data='new_proxy')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(text=f"Ваш прокси: {proxy}", reply_markup=reply_markup)
        except Exception as e:
            logger.warning(f"Ошибка обновления сообщения: {e}")
            return

        # Если это первый прокси - отправляем инструкции
        if proxy_count == 1:
            await send_instructions(user_id, context.bot)
        
        # Планируем запрос оценки через сутки
        job_queue = context.application.job_queue
        if job_queue:
            run_at = datetime.now() + timedelta(days=1)
            job_queue.run_once(
                send_rating_request,
                when=run_at,
                data={'user_id': user_id, 'proxy': proxy},
                name=f"rating_{user_id}_{proxy_count}"
            )
            logger.info(f"Запланирован запрос оценки для {user_id} на {run_at}")


async def proxy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /proxy"""
    user = update.effective_user
    user_id = user.id
    username = user.username or ''
    
    proxy = get_next_proxy(username)
    
    # Обновляем данные
    user_data = get_user_data(user_id)
    proxy_count = user_data.get('proxy_count', 0) + 1
    update_user_data(
        user_id,
        proxy_count=proxy_count,
        last_proxy=proxy,
        last_proxy_time=datetime.now().isoformat()
    )
    
    # Логируем
    logger.info(f"Пользователь {username} ({user_id}) получил прокси: {proxy} (запрос #{proxy_count})")
    
    await update.message.reply_text(f"Ваш прокси: {proxy}")

    # Если первый прокси - инструкции
    if proxy_count == 1:
        await send_instructions(user_id, context.bot)
    
    # Планируем оценку через сутки
    job_queue = context.application.job_queue
    if job_queue:
        run_at = datetime.now() + timedelta(days=1)
        job_queue.run_once(
            send_rating_request,
            when=run_at,
            data={'user_id': user_id, 'proxy': proxy},
            name=f"rating_{user_id}_{proxy_count}"
        )


def main() -> None:
    """Запуск бота"""
    token = os.environ.get('BOT_TOKEN', '')
    if not token or token == 'YOUR_BOT_TOKEN':
        logger.error("Не задан токен бота! Установите переменную окружения BOT_TOKEN")
        return
    
    application = Application.builder().token(token).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("proxy", proxy_command))
    application.add_handler(CallbackQueryHandler(button))
    
    logger.info("Бот запущен")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()