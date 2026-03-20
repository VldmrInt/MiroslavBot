FROM python:3.11-slim

WORKDIR /app

# Зависимости устанавливаем отдельным слоем для кэширования
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Непривилегированный пользователь
RUN useradd --no-create-home --shell /bin/false botuser

# Исходный код
COPY --chown=botuser:botuser . .

# Директории для постоянных данных
RUN mkdir -p /app/data /app/proxies \
    && chown -R botuser:botuser /app

USER botuser

ENV BOT_TOKEN=""
ENV BOT_PROXY_URL=""

CMD ["python", "bot.py"]
