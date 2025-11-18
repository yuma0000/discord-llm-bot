FROM python:3.12-slim

# ビルドに必要なパッケージ
RUN apt-get update && apt-get install -y \
    build-essential cmake git libomp-dev wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依存関係
COPY requirements.txt .
RUN python3 -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# カスタムモデルのダウンロード
RUN wget -q -O mania-model.Q8_K_M.gguf \
    "https://huggingface.co/yustudiojp/gguf-models/resolve/main/mania-model.Q8_K_M.gguf?download=true"

# アプリ本体
COPY discord_bot.py .

CMD ["python3", "discord_bot.py", "MTM1MDgwMjc0MzYxODY5OTMwNA.GD5ds-.fOSGtPQQA3w8UAemQxNEYAQcKZk6vlty9OO0Nw", "mania-model.Q8_K_M.gguf", "あなたはウェブマニアです。適切に答えて下さい。"]
