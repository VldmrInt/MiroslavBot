# Telegram Proxy Bot

Бот для равномерного распределения прокси с сегментацией пользователей.

## Возможности

- ✅ Выдача прокси с равномерным распределением
- ✅ VIP-список прокси для выбранных пользователей (по Telegram username)
- ✅ Независимые счётчики раздачи для VIP и обычных пользователей
- ✅ Логирование всех запросов
- ✅ Напоминание об оценке через сутки
- ✅ Инструкции после первого получения прокси

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Создайте файл `proxies/users.json` с настройками прокси (см. раздел ниже).

3. Установите токен бота через переменную окружения:
```bash
export BOT_TOKEN="ваш_токен_бота"
```

## Настройка прокси

Все настройки прокси хранятся в файле `proxies/users.json`:

```json
{
  "vip_users": ["ivanov", "petrov", "sidorov"],
  "default": [
    {
      "type": "mtproto",
      "server": "1.2.3.4",
      "port": 443,
      "secret": "ee367f90de5ca35a5939d8b49f5a3e0f62"
    },
    {
      "type": "socks5",
      "server": "5.6.7.8",
      "port": 1080,
      "username": "user",
      "password": "pass"
    },
    "ip1:port1"
  ],
  "vip": [
    {
      "type": "mtproto",
      "server": "10.0.0.1",
      "port": 443,
      "secret": "dd1234567890abcdef1234567890abcd"
    }
  ]
}
```

- `vip_users` — список username, которые получают VIP-прокси (например, `ivanov`)
- `default` — прокси для обычных пользователей
- `vip` — прокси для VIP-пользователей

### Форматы записей прокси

Каждый элемент массива `default` / `vip` может быть:

#### MTProto (`type: "mtproto"`)
```json
{
  "type": "mtproto",
  "server": "1.2.3.4",
  "port": 443,
  "secret": "ee367f90de5ca35a5939d8b49f5a3e0f62"
}
```
Бот отправит пользователю блок с деталями и ссылку `https://t.me/proxy?…`, по которой прокси подключится одним касанием.

#### SOCKS5 (`type: "socks5"`)
```json
{
  "type": "socks5",
  "server": "5.6.7.8",
  "port": 1080,
  "username": "user",
  "password": "pass"
}
```
Поля `username` и `password` опциональны. Бот отправит ссылку `https://t.me/socks?…`.

#### Устаревший строковый формат
```json
"ip1:port1"
```
Строка отображается пользователю как есть. Поддерживается для обратной совместимости.

VIP- и обычные пользователи используют **независимые** счётчики раздачи, поэтому
запросы одной группы не влияют на очерёдность в другой.

## Инструкции

Добавьте 3 изображения в папку `images/`:
- `instruction1.jpg` — первая картинка
- `instruction2.jpg` — вторая картинка  
- `instruction3.jpg` — третья картинка

Они автоматически отправятся пользователю после получения первого прокси.

## Использование

Запустите бота:
```bash
python bot.py
```

В Telegram:
- `/start` — начать работу
- `/proxy` — получить прокси
- Кнопка «Получить прокси» — получить прокси с клавиатуры

Через сутки после получения прокси бот спросит оценку работы.

## Запуск без Docker (в фоне)

### Linux / macOS
Запустите бота в фоне с помощью `nohup`:

```bash
BOT_TOKEN="ваш_токен" nohup python3 bot.py > bot.log 2>&1 &
```

Остановить можно, найдя PID и убив процесс:

```bash
ps aux | grep bot.py
kill <PID>
```

### Windows (PowerShell)
Запуск в фоне:

```powershell
Start-Process -NoNewWindow -FilePath python -ArgumentList "bot.py" -RedirectStandardOutput "bot.log" -RedirectStandardError "bot.log"
```

Чтобы остановить, найдите процесс и завершите его:

```powershell
Get-Process python | Where-Object {$_.Path -like "*bot.py*"} | Stop-Process
```

## Запуск через Docker

### Быстрый старт (Docker Compose)

1. Скопируйте `.env.example` в `.env` и укажите токен бота:
```bash
cp .env.example .env
# Отредактируйте .env, вставив ваш BOT_TOKEN
```

2. Запустите:
```bash
docker compose up -d
```

3. Посмотреть логи:
```bash
docker compose logs -f
```

4. Остановить:
```bash
docker compose down
```

### Сборка и запуск вручную

```bash
docker build -t telegram-proxy-bot .
docker run -d --restart unless-stopped \
  -e BOT_TOKEN="ваш_токен" \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/proxies:/app/proxies \
  -v $(pwd)/images:/app/images \
  telegram-proxy-bot
```

### Переменные окружения

| Переменная | Описание | Обязательна |
|------------|----------|-------------|
| `BOT_TOKEN` | Токен вашего Telegram-бота | Да |

### Тома (Volumes)

Для сохранения данных между перезапусками монтируются:
- `./data` — данные пользователей
- `./proxies` — конфигурация прокси
- `./images` — картинки инструкций

## Логи

Все запросы сохраняются в файл `bot.log`.
