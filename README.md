# MiroslavBot — Telegram Proxy Bot

Бот для раздачи прокси в Telegram с поддержкой VIP-пользователей.

## Возможности

- Выдача прокси прямыми ссылками (`https://t.me/socks?...`) — подключение в один клик
- VIP-список с отдельным пулом прокси (по Telegram username)
- Независимые счётчики round-robin для VIP и обычных пользователей
- Автоматическое использование SOCKS5-прокси для собственного подключения к Telegram API (работает при блокировке в РФ)
- Подсказки для пользователей: инструкция по настройке и проверка статуса
- Логирование всех запросов
- Docker-контейнеризация

## Быстрый старт

### Docker Compose (рекомендуется)

```bash
cp .env.example .env
nano .env              # вставьте BOT_TOKEN
nano proxies/users.json  # заполните реальными прокси
docker compose up -d
```

### Без Docker

```bash
pip install -r requirements.txt
export BOT_TOKEN="ваш_токен_бота"
python bot.py
```

## Настройка прокси

Все настройки хранятся в `proxies/users.json`:

```json
{
  "vip_users": ["ivanov", "petrov"],
  "default": [
    "https://t.me/socks?server=45.150.37.167&port=12335&user=user1&pass=passStrong123",
    "https://t.me/socks?server=45.150.37.167&port=12336&user=user2&pass=passStrong456"
  ],
  "vip": [
    "https://t.me/socks?server=45.150.37.167&port=12338&user=vip1&pass=vipPass111"
  ]
}
```

| Поле | Описание |
|------|----------|
| `vip_users` | Telegram-username, которые получают VIP-прокси |
| `default` | Прокси для обычных пользователей |
| `vip` | Прокси для VIP-пользователей |

### Поддерживаемые форматы ссылок

- **SOCKS5:** `https://t.me/socks?server=HOST&port=PORT&user=USER&pass=PASS`
- **MTProto:** `https://t.me/proxy?server=HOST&port=PORT&secret=SECRET`

VIP- и обычные пользователи используют **независимые** счётчики, поэтому запросы одной группы не влияют на очерёдность в другой.

## Прокси для самого бота

Бот автоматически использует первый SOCKS5-прокси из списка `default` для своего подключения к Telegram API. Это необходимо в России, где Telegram (включая API) заблокирован.

Порядок выбора прокси для бота:
1. Переменная окружения `BOT_PROXY_URL` (если задана)
2. Первая SOCKS5-ссылка из `default` в `proxies/users.json`

MTProto-ссылки не могут быть использованы ботом — только SOCKS5.

## Переменные окружения

| Переменная | Описание | Обязательна |
|------------|----------|-------------|
| `BOT_TOKEN` | Токен бота от @BotFather | Да |
| `BOT_PROXY_URL` | Явный прокси для бота (`socks5://user:pass@host:port`) | Нет |

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие и кнопка получения прокси |
| `/proxy` | Получить прокси напрямую |

## Docker

### Docker Compose

```bash
# Запустить
docker compose up -d

# Логи
docker compose logs -f

# Остановить
docker compose down

# Пересобрать после изменений
docker compose up -d --build
```

### Ручная сборка

```bash
docker build -t miroslav-bot .
docker run -d --restart unless-stopped \
  -e BOT_TOKEN="ваш_токен" \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/proxies:/app/proxies \
  miroslav-bot
```

### Тома

| Том | Описание |
|-----|----------|
| `./data:/app/data` | Данные пользователей (`users.json`) |
| `./proxies:/app/proxies` | Конфигурация прокси |

## Запуск в фоне (без Docker)

```bash
# Linux / macOS
BOT_TOKEN="ваш_токен" nohup python3 bot.py > bot.log 2>&1 &

# Остановить
ps aux | grep bot.py
kill <PID>
```

## Логи

Все запросы сохраняются в `bot.log` (в Docker — также через `docker compose logs`).
