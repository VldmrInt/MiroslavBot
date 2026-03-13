# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Создаём директории с правильными правами
RUN mkdir -p proxies images data

# Переменная окружения для токена бота
ENV BOT_TOKEN=""

# Запуск бота
CMD ["python", "bot.py"]
