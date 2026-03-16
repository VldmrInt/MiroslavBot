import logging
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

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
DATA_FILE = os.path.join(BASE_DIR, 'data', 'users.json')

# Создаём директории
os.makedirs(PROXIES_DIR, exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'data'), exist_ok=True)

# Раздельные индексы для VIP- и обычных прокси (предотвращают взаимное сбивание счётчика).
# Бот работает на asyncio (однопоточный event loop), поэтому чтения/записи без await
# между ними атомарны — дополнительная блокировка не требуется.
proxy_indices: dict = {'vip': 0, 'default': 0}


def load_users_data() -> dict:
    """Загружает данные пользователей из JSON"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки данных пользователей: {e}")
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
            'last_proxy_time': None
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


def get_next_proxy(username: str) -> str:
    """Получает следующий прокси с равномерным распределением.

    VIP- и обычные пользователи используют независимые счётчики, поэтому
    запросы одной группы не влияют на очерёдность в другой.
    """
    config = load_proxies_config()

    vip_users = config.get('vip_users', [])
    is_vip = bool(username and username in vip_users and 'vip' in config)

    if is_vip:
        proxies = config['vip']
        list_key = 'vip'
    else:
        proxies = config.get('default', [])
        list_key = 'default'

    if not proxies:
        return "Нет доступных прокси"

    idx = proxy_indices[list_key]
    proxy = proxies[idx]
    proxy_indices[list_key] = (idx + 1) % len(proxies)
    return proxy


async def _issue_proxy(
    user_id: int,
    username: str,
    context: ContextTypes.DEFAULT_TYPE,
) -> tuple[str, int]:
    """Выдаёт прокси, обновляет статистику пользователя.

    Возвращает кортеж (proxy, proxy_count).
    """
    proxy = get_next_proxy(username)

    user_data = get_user_data(user_id)
    proxy_count = user_data.get('proxy_count', 0) + 1
    update_user_data(
        user_id,
        proxy_count=proxy_count,
        last_proxy=proxy,
        last_proxy_time=datetime.now().isoformat(),
    )

    logger.info(f"Пользователь {username} ({user_id}) получил прокси: {proxy} (запрос #{proxy_count})")

    if proxy_count == 1:
        await send_instructions(user_id, context.bot)

    return proxy, proxy_count


async def send_instructions(user_id: int, bot) -> None:
    """Отправляет текстовые инструкции по настройке прокси"""

    instructions_text = (
        "📖 <b>Инструкция по настройке прокси в Telegram</b>\n\n"

        "⚡️ <b>Быстрый способ</b>\n"
        "Нажмите на ссылку-прокси и нажмите <b>Подключить</b> — прокси активируется автоматически без ручной настройки.\n\n"

        "❌ <b>Прокси не работает в web-версии Telegram (web.telegram.org)</b> — используйте только приложение.\n\n"

        "🖥 <b>Windows / macOS / Linux</b>\n"
        "1. Откройте <b>Настройки</b> → <b>Расширенные</b>\n"
        "2. Нажмите <b>Тип подключения</b> → <b>Использовать прокси</b>\n"
        "3. Нажмите <b>Добавить прокси</b>\n"
        "4. Выберите тип <b>SOCKS5</b> или <b>MTProto</b>\n"
        "5. Введите IP-адрес и порт из вашего прокси\n"
        "6. Нажмите <b>Сохранить</b> и <b>Включить</b>\n"
        "🔴 Выключить: Настройки → Расширенные → Тип подключения → <b>Нет прокси</b>\n"
        "🔄 Сменить: в списке прокси выберите другой или нажмите <b>Добавить прокси</b>\n\n"

        "📱 <b>Android</b>\n"
        "1. Откройте <b>Настройки</b> → <b>Данные и хранилище</b>\n"
        "2. Нажмите <b>Настройки прокси</b>\n"
        "3. Включите тумблер <b>Использовать прокси</b>\n"
        "4. Нажмите <b>Добавить прокси</b>\n"
        "5. Введите IP-адрес и порт из вашего прокси\n"
        "6. Нажмите <b>Готово</b> и <b>Подключить</b>\n"
        "🔴 Выключить: Настройки → Данные и хранилище → Настройки прокси → выключить тумблер\n"
        "🔄 Сменить: нажмите на текущий прокси → измените данные\n\n"

        "🍎 <b>iOS</b>\n"
        "1. Откройте <b>Настройки</b> → <b>Данные и хранилище</b>\n"
        "2. Нажмите <b>Прокси</b>\n"
        "3. Включите тумблер <b>Использовать прокси</b>\n"
        "4. Нажмите <b>Добавить прокси</b>\n"
        "5. Введите IP-адрес и порт из вашего прокси\n"
        "6. Нажмите <b>Сохранить</b> и <b>Подключить</b>\n"
        "🔴 Выключить: Настройки → Данные и хранилище → Прокси → выключить тумблер\n"
        "🔄 Сменить: нажмите на текущий прокси → измените данные"
    )

    status_and_warnings_text = (
        "✅ <b>Как понять, что прокси включён</b>\n\n"
        "После успешного подключения вы увидите:\n"
        "• Зелёную точку или иконку щита 🛡 рядом с именем в настройках\n"
        "• Статус «Подключено» в разделе настроек прокси\n"
        "• Telegram работает там, где без прокси был недоступен\n\n"

        "⚠️ <b>Важные предупреждения</b>\n\n"

        "🔶 <b>Прокси может конфликтовать с VPN</b>\n"
        "Если у вас включён VPN, прокси может не работать или работать некорректно. "
        "Отключите VPN перед использованием прокси.\n\n"

        "🔶 <b>Прокси может не работать по независящим от нас причинам</b>\n"
        "Доступность прокси зависит от интернет-провайдера, страны и настроек сети. "
        "Мы не можем гарантировать бесперебойную работу в любой ситуации. "
        "Если прокси не работает — попробуйте получить новый.\n\n"

        "🔶 <b>Прокси — не панацея для мобильного интернета</b>\n"
        "На мобильном интернете и при включённых «белых списках» у провайдера "
        "прокси может не давать нужного эффекта. В таких случаях рекомендуем "
        "использовать VPN или другие инструменты обхода блокировок."
    )

    messages = [
        ("инструкции по настройке", instructions_text),
        ("статус и предупреждения", status_and_warnings_text),
    ]
    for label, text in messages:
        try:
            await bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Ошибка отправки инструкций ({label}): {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    user = update.effective_user
    user_id = user.id
    username = user.username or ''

    # Сохраняем никнейм
    get_user_data(user_id)
    update_user_data(user_id, username=username)

    keyboard = [[InlineKeyboardButton("✅ Понятно, продолжить", callback_data='acknowledge_proxy')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        '⚠️ Важно!\n\n'
        'Прокси работает только с приложением Telegram:\n'
        '• Windows\n'
        '• Linux\n'
        '• macOS\n'
        '• Android\n'
        '• iOS\n\n'
        '❌ Прокси НЕ работает с web-версией Telegram (web.telegram.org).\n\n'
        'Нажмите кнопку ниже, чтобы продолжить.',
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

    # Подтверждение предупреждения — показываем кнопку получения прокси
    if query.data == 'acknowledge_proxy':
        keyboard = [[InlineKeyboardButton("Получить прокси", callback_data='new_proxy')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_text(
                text='Добро пожаловать! Нажмите кнопку, чтобы получить прокси.',
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.warning(f"Ошибка обновления сообщения после подтверждения: {e}")
        return

    # Выдача прокси
    if query.data == 'new_proxy':
        proxy, proxy_count = await _issue_proxy(user_id, username, context)

        keyboard = [[InlineKeyboardButton("Получить новый прокси", callback_data='new_proxy')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await query.edit_message_text(text=f"Ваш прокси: {proxy}", reply_markup=reply_markup)
        except Exception as e:
            logger.warning(f"Ошибка обновления сообщения: {e}")


async def proxy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /proxy"""
    user = update.effective_user
    user_id = user.id
    username = user.username or ''

    proxy, _ = await _issue_proxy(user_id, username, context)
    await update.message.reply_text(f"Ваш прокси: {proxy}")


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
