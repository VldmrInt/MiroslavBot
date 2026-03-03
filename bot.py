import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загружаем список прокси из файла
def load_proxies():
    try:
        with open('proxies.txt', 'r') as f:
            proxies = [line.strip() for line in f.readlines() if line.strip()]
        return proxies
    except FileNotFoundError:
        logger.error("Файл proxies.txt не найден!")
        return []

# Глобальные переменные для хранения прокси и текущего индекса
proxies = load_proxies()
current_proxy_index = 0

# Функция для получения следующего прокси с равномерным распределением
def get_next_proxy():
    global current_proxy_index
    if not proxies:
        return "Нет доступных прокси"
    proxy = proxies[current_proxy_index]
    current_proxy_index = (current_proxy_index + 1) % len(proxies)
    return proxy

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[InlineKeyboardButton("Получить новый прокси", callback_data='new_proxy')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text('Добро пожаловать! Нажмите кнопку, чтобы получить прокси.', reply_markup=reply_markup)

# Обработчик нажатий на кнопки
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    if query.data == 'new_proxy':
        proxy = get_next_proxy()
        keyboard = [[InlineKeyboardButton("Получить новый прокси", callback_data='new_proxy')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=f"Ваш прокси: {proxy}", reply_markup=reply_markup)

# Обработчик команды /proxy
async def proxy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    proxy = get_next_proxy()
    await update.message.reply_text(f"Ваш прокси: {proxy}")

def main() -> None:
    # Создаем Application и передаем ему токен вашего бота
    application = Application.builder().token("YOUR_BOT_TOKEN").build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("proxy", proxy_command))
    application.add_handler(CallbackQueryHandler(button))
    
    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()