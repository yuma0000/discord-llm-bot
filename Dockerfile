FROM ollama/ollama:latest

# Python3 を追加
RUN apk update && apk add python3 py3-pip

WORKDIR /app

# Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリ本体
COPY server.py .
COPY discord_bot.py .

RUN ollama pull mania

EXPOSE 8000

CMD ["sh", "-c", "\
    ollama serve & \
    sleep 3 && \
    uvicorn server:app --host 0.0.0.0 --port 8000 & \
    python3 discord_bot.py \
"]
