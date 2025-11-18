# ベースイメージは公式 slim を使用
FROM python:3.12-slim

# 必要な OS パッケージをインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    libomp-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

# pip をアップグレード
RUN python3 -m pip install --upgrade pip

# llama-cpp-python とその他の依存ライブラリをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir llama-cpp-python

# カスタムモデルをダウンロード
RUN wget -O /app/mania-model.Q8_K_M.gguf \
    "https://huggingface.co/yustudiojp/gguf-models/resolve/main/mania-model.Q8_K_M.gguf?download=true"

# アプリコードをコピー
COPY discord_bot.py /app/discord_bot.py
WORKDIR /app

# 実行コマンド
CMD ["python3", "discord_bot.py", "MTM1MDgwMjc0MzYxODY5OTMwNA.GD5ds-.fOSGtPQQA3w8UAemQxNEYAQcKZk6vlty9OO0Nw", "mania-model.Q8_K_M.gguf", "あなたはウェブマニアです。適切に答えて下さい。"]
