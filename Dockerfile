FROM ollama/ollama:latest

WORKDIR /app

# OS依存ライブラリとPythonビルドツール
RUN apt-get update && apt-get install -y \
    python3-pip build-essential libffi-dev libssl-dev wget tini \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python3 -m pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# カスタムモデルのダウンロード
RUN wget -O /app/mania-model.Q8_K_M.gguf https://mt.f5.si/mania-model.Q8_K_M.gguf
RUN echo "FROM /app/mania-model.Q8_K_M.gguf" > /app/Modelfile
RUN [ ! -f /root/.ollama/models/mania/model.json ] && ollama create mania -f /app/Modelfile || echo "Model already exists"
RUN ollama pull llama3

COPY discord_bot.py .

EXPOSE 8000 11434

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sh", "-c", "ollama serve & sleep 3 && uvicorn server:app --host 0.0.0.0 --port 8000 & python3 discord_bot.py"]
