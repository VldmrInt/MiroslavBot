#!/usr/bin/env python3
"""
MiroslavBot — раздача прокси для Telegram.
Полная версия с нуля.

Формат прокси в proxies/users.json:
  https://t.me/socks?server=HOST&port=PORT&user=USER&pass=PASS
  https://t.me/proxy?server=HOST&port=PORT&secret=SECRET

Бот автоматически использует первый SOCKS5-прокси из списка для своего
собственного подключения к Telegram API (актуально при блокировке в РФ).
"""

import json
import logging
import os
import sys
from datetime import datetime
from urllib.parse import parse_qs, urlparse

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

# ---------------------------------------------------------------------------
# Логирование
# ---------------------------------------------------------------------------

_log_path = "/app/bot.log" if os.path.isdir("/app") else "bot.log"
_handlers: list = [logging.StreamHandler(sys.stdout)]
try:
    _handlers.append(logging.FileHandler(_log_path, encoding="utf-8"))
except OSError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=_handlers,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Пути
# ---------------------------------------------------------------------------

_IN_DOCKER = os.path.isdir("/app/data")
DATA_DIR = "/app/data" if _IN_DOCKER else "./data"
PROXIES_FILE = "/app/proxies/users.json" if _IN_DOCKER else "./proxies/users.json"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Состояние ротации прокси (в памяти; сбрасывается при рестарте)
# ---------------------------------------------------------------------------

_proxy_index: int = 0

# ---------------------------------------------------------------------------
# Работа с данными пользователей
# ---------------------------------------------------------------------------

def _load_users() -> dict:
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Ошибка чтения users.json: %s", exc)
        return {}


def _save_users(data: dict) -> None:
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.error("Ошибка записи users.json: %s", exc)


def _get_user(user_id: int) -> dict:
    data = _load_users()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {
            "username": None,
            "proxy_count": 0,
            "last_proxy": None,
            "last_proxy_time": None,
        }
        _save_users(data)
    return data[uid]


def _update_user(user_id: int, **kwargs) -> None:
    data = _load_users()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {
            "username": None,
            "proxy_count": 0,
            "last_proxy": None,
            "last_proxy_time": None,
        }
    data[uid].update(kwargs)
    _save_users(data)

# ---------------------------------------------------------------------------
# Работа с прокси
# ---------------------------------------------------------------------------

def _load_proxies() -> list:
    try:
        with open(PROXIES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Ошибка чтения proxies/users.json: %s", exc)
        return []


def _parse_link(link: str):
    """
    Разбирает ссылку вида:
      https://t.me/socks?server=...&port=...&user=...&pass=...
      https://t.me/proxy?server=...&port=...&secret=...
    Возвращает словарь с компонентами или None при ошибке.
    """
    try:
        parsed = urlparse(link.strip())
        params = parse_qs(parsed.query)

        def _get(key):
            vals = params.get(key)
            return vals[0] if vals else None

        if "/socks" in parsed.path:
            return {
                "type": "socks5",
                "server": _get("server"),
                "port": int(_get("port") or 0),
                "user": _get("user"),
                "pass": _get("pass"),
            }
        if "/proxy" in parsed.path:
            return {
                "type": "mtproto",
                "server": _get("server"),
                "port": int(_get("port") or 0),
                "secret": _get("secret"),
            }
    except Exception as exc:
        logger.warning("Не удалось разобрать ссылку '%s': %s", link, exc)
    return None


def _link_to_socks5_url(link: str):
    """
    Преобразует t.me/socks ссылку в socks5://user:pass@server:port
    для использования ботом при подключении к Telegram API.
    MTProto-ссылки не поддерживаются как SOCKS5 — возвращает None.
    """
    info = _parse_link(link)
    if not info or info["type"] != "socks5":
        return None
    server = info.get("server") or ""
    port = info.get("port") or 1080
    user = info.get("user") or ""
    pwd = info.get("pass") or ""
    if user and pwd:
        return f"socks5://{user}:{pwd}@{server}:{port}"
    return f"socks5://{server}:{port}"


def _get_bot_proxy():
    """
    Определяет прокси для собственного подключения бота к Telegram API.
    Приоритет:
      1. Переменная окружения BOT_PROXY_URL (явное переопределение)
      2. Первый SOCKS5-прокси из proxies/users.json
    """
    env_val = os.environ.get("BOT_PROXY_URL", "").strip()
    if env_val:
        logger.info("Бот использует прокси из BOT_PROXY_URL: %s", env_val)
        return env_val

    for link in _load_proxies():
        url = _link_to_socks5_url(link)
        if url:
            logger.info("Бот использует прокси из списка: %s", url)
            return url

    logger.warning(
        "SOCKS5-прокси для бота не найден. "
        "Если Telegram заблокирован, задайте BOT_PROXY_URL."
    )
    return None


def _next_proxy():
    """Выбирает следующий прокси по round-robin. Возвращает ссылку как есть."""
    global _proxy_index
    pool = _load_proxies()
    if not pool:
        return None
    proxy = pool[_proxy_index % len(pool)]
    _proxy_index = (_proxy_index + 1) % len(pool)
    return proxy


def _issue_proxy(user_id: int, username):
    """
    Выдаёт следующий прокси пользователю, сохраняет в JSON.
    Возвращает (ссылка_или_None, номер_запроса).
    """
    proxy = _next_proxy()
    user = _get_user(user_id)
    count = user["proxy_count"] + 1

    _update_user(
        user_id,
        username=username,
        proxy_count=count,
        last_proxy=proxy,
        last_proxy_time=datetime.now().isoformat(),
    )
    logger.info(
        "Пользователь %s (%d) получил прокси: %s (запрос #%d)",
        username or "unknown",
        user_id,
        proxy,
        count,
    )
    return proxy, count

# ---------------------------------------------------------------------------
# Тексты
# ---------------------------------------------------------------------------

_INSTRUCTIONS = (
    "📖 *Инструкция по настройке прокси в Telegram*\n\n"
    "*🖥 Windows / macOS / Linux*\n"
    "1\\. Откройте Telegram → Настройки → Конфиденциальность и безопасность → Тип подключения\n"
    "2\\. Выберите *Использовать прокси* → *SOCKS5*\n"
    "3\\. Введите сервер, порт, логин и пароль из ссылки\n"
    "4\\. Нажмите *Сохранить*\n\n"
    "*📱 Android*\n"
    "1\\. Настройки → Конфиденциальность и безопасность → Настройки прокси\n"
    "2\\. Нажмите *Добавить прокси* → *SOCKS5*\n"
    "3\\. Заполните поля → *Готово*\n\n"
    "*🍎 iOS*\n"
    "1\\. Настройки → Конфиденциальность и безопасность → Использовать прокси\n"
    "2\\. Нажмите *Добавить прокси* → *SOCKS5*\n"
    "3\\. Заполните поля → *Сохранить*\n\n"
    "💡 *Совет:* Нажмите на ссылку прямо в Telegram — приложение автоматически предложит добавить прокси\\!"
)

_STATUS = (
    "✅ *Как понять, что прокси включён*\n\n"
    "• Если этот бот отвечает — прокси работает ✅\n"
    "• Сообщения доставляются без задержек — всё в порядке ✅\n"
    "• В настройках прокси отображается зелёная галочка и время задержки ✅\n\n"
    "⚠️ *Важные замечания:*\n"
    "• Прокси и VPN *несовместимы* — если включён VPN, отключите его\n"
    "• Работа прокси зависит от вашего интернет\\-провайдера\n"
    "• На некоторых мобильных операторах прокси может не работать — попробуйте через Wi\\-Fi"
)

# ---------------------------------------------------------------------------
# Клавиатуры
# ---------------------------------------------------------------------------

def _proxy_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Получить другой прокси", callback_data="new_proxy")],
        [InlineKeyboardButton(
            "📖 Инструкция по настройке прокси в Telegram",
            callback_data="show_instructions",
        )],
        [InlineKeyboardButton(
            "✅ Как понять, что прокси включён",
            callback_data="show_status",
        )],
    ])


def _start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Получить прокси", callback_data="get_proxy")],
    ])

# ---------------------------------------------------------------------------
# Обработчики команд и кнопок
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    _update_user(user.id, username=user.username)
    logger.info("Пользователь %s (%d) запустил бота", user.username, user.id)

    await update.message.reply_text(
        "👋 Привет\\! Этот бот выдаёт прокси для Telegram\\.\n\n"
        "⚠️ *Внимание:* Бот не работает в браузерной версии Telegram "
        "\\(web\\.telegram\\.org\\)\\. Используйте мобильное приложение или "
        "десктопный клиент\\.\n\n"
        "Нажмите кнопку ниже, чтобы получить прокси\\.",
        parse_mode="MarkdownV2",
        reply_markup=_start_keyboard(),
    )


async def cmd_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    proxy, count = _issue_proxy(user.id, user.username)

    if not proxy:
        await update.message.reply_text(
            "❌ Прокси\\-серверы временно недоступны\\. Попробуйте позже\\.",
            parse_mode="MarkdownV2",
        )
        return

    await update.message.reply_text(
        f"🌐 *Ваш прокси \\#{count}:*\n\n"
        f"`{proxy}`\n\n"
        "Нажмите на ссылку — Telegram предложит добавить прокси автоматически\\.",
        parse_mode="MarkdownV2",
        reply_markup=_proxy_keyboard(),
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user = query.from_user
    data = query.data

    if data in ("get_proxy", "new_proxy"):
        proxy, count = _issue_proxy(user.id, user.username)

        if not proxy:
            await query.edit_message_text(
                "❌ Прокси\\-серверы временно недоступны\\. Попробуйте позже\\.",
                parse_mode="MarkdownV2",
            )
            return

        await query.edit_message_text(
            f"🌐 *Ваш прокси \\#{count}:*\n\n"
            f"`{proxy}`\n\n"
            "Нажмите на ссылку — Telegram предложит добавить прокси автоматически\\.",
            parse_mode="MarkdownV2",
            reply_markup=_proxy_keyboard(),
        )

    elif data == "show_instructions":
        await query.message.reply_text(
            _INSTRUCTIONS,
            parse_mode="MarkdownV2",
        )

    elif data == "show_status":
        await query.message.reply_text(
            _STATUS,
            parse_mode="MarkdownV2",
        )

# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

def main() -> None:
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        logger.error("Переменная окружения BOT_TOKEN не задана!")
        sys.exit(1)

    bot_proxy = _get_bot_proxy()

    builder = ApplicationBuilder().token(token)
    if bot_proxy:
        builder = builder.proxy(bot_proxy).get_updates_proxy(bot_proxy)

    app = builder.build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("proxy", cmd_proxy))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Бот запущен%s", f" (прокси: {bot_proxy})" if bot_proxy else "")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
