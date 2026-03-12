# Telegram Proxy Bot

Бот для равномерного распределения прокси с сегментацией пользователей.

## Возможности

- ✅ Выдача прокси с равномерным распределением
- ✅ Сегментация пользователей по никнейму (персональные списки прокси)
- ✅ Логирование всех запросов
- ✅ Напоминание об оценке через сутки
- ✅ Инструкции после первого получения прокси

## Установка

1. Установите зависимости:
```
pip install -r requirements.txt
```

2. Создайте файл `proxies/users.json` с настройками прокси (см. раздел ниже).

3. Установите токен бота через переменную окружения:
```
export BOT_TOKEN="ваш_токен_бота"
```

## Настройка прокси

Все настройки прокси хранятся в файле `proxies/users.json`:

```json
{
  "vip_users": ["ivanov", "petrov", "sidorov"],
  "default": [
    "обычный прокси1:порт",
    "обычный прокси2:порт"
  ],
  "vip": [
    "вип прокси1:порт",
    "вип прокси2:порт"
  ]
}
```

- `vip_users` — список username, которые получают VIP-прокси (например, `ivanov`)
- `default` — прокси для обычных пользователей
- `vip` — прокси для VIP-пользователей

### Примеры

1) Добавить VIP-пользователя: просто включите его `username` в `vip_users`.
2) Добавить прокси: добавьте строку `host:port` в нужный массив (`default` или `vip`).

> Пример:
> ```json
> {
>   "vip_users": ["ivanov", "petrov"],
>   "default": ["ip1:port1"],
>   "vip": ["10.0.0.1:8080"]
> }
> ```

## Инструкции

Добавьте 3 изображения в папку `images/`:
- `instruction1.jpg` — первая картинка
- `instruction2.jpg` — вторая картинка  
- `instruction3.jpg` — третья картинка

Они автоматически отправятся пользователю после получения первого прокси.

## Использование

Запустите бота:
```
python bot.py
```

В Telegram:
- `/start` — начать работу
- `/proxy` — получить прокси
- Кнопка «Получить прокси» — получить прокси с клавиатуры

Через сутки после получения прокси бот спросит оценку работы.

## Запуск без Docker (в фоне)

### Linux / macOS
Запустите бота в фоне с помощью `nohup` или `&`:

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

### Сборка образа

```bash
docker build -t telegram-proxy-bot .
```

### Запуск контейнера

```bash
docker run -e BOT_TOKEN="ваш_токен" telegram-proxy-bot
```

### Использование Docker Compose

Создайте файл `docker-compose.yml`:

```yaml
version: '3.8'
services:
  bot:
    build: .
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
    volumes:
      - ./data:/app/data
      - ./proxies:/app/proxies
      - ./images:/app/images
```

Запустите:

```bash
docker-compose up
```

### Переменные окружения

- `BOT_TOKEN` — токен вашего Telegram-бота (обязательно)

### Тома (Volumes)

Для сохранения данных между перезапусками монтируются:
- `./data` — данные пользователей
- `./proxies` — конфигурация прокси
- `./images` — картинки инструкций

## Логи

Все запросы сохраняются в файл `bot.log`.