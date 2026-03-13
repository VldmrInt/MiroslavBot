# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Создаём непривилегированного пользователя и необходимые директории
RUN useradd --no-create-home --shell /bin/false botuser

# Копируем исходный код
COPY --chown=botuser:botuser . .

# Создаём директории с правильными правами (после COPY, чтобы не затереть содержимое)
RUN mkdir -p proxies images data \
    && chown -R botuser:botuser /app

# Переключаемся на непривилегированного пользователя
USER botuser

# Переменная окружения для токена бота
ENV BOT_TOKEN=""

# Запуск бота
CMD ["python", "bot.py"]
