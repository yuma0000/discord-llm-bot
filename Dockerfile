# ----------------------------------------------------
# STAGE 1: Build Environment and Dependencies
# ----------------------------------------------------

# Debian slim をベースに Ollama イメージを統合
FROM ollama/ollama:latest

# 必要なパッケージをインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    wget \
    curl \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# tini をインストールしてプロセス管理を安定化
RUN apt-get update && apt-get install -y tini && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリ
WORKDIR /app

# Pythonライブラリをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ----------------------------------------------------
# STAGE 2: Model and Application Setup
# ----------------------------------------------------

# カスタムGGUFモデルをダウンロード
RUN wget -O /app/mania-model.Q8_K_M.gguf https://mt.f5.si/mania-model.Q8_K_M.gguf

# Modelfileを作成してカスタムモデルを登録 (存在しない場合のみ)
RUN echo "FROM /app/mania-model.Q8_K_M.gguf" > /app/Modelfile
RUN [ ! -f /root/.ollama/models/mania/model.json ] && ollama create mania -f /app/Modelfile || echo "Model already exists"

# フォールバック用の llama3 モデルを事前ダウンロード
RUN ollama pull llama3

# アプリケーションコードをコピー
COPY discord_bot.py .

# ----------------------------------------------------
# STAGE 3: Runtime
# ----------------------------------------------------

# Uvicornサーバー用ポートを公開
EXPOSE 8000

# tini をエントリーポイントにして複数プロセスを管理
ENTRYPOINT ["/usr/bin/tini", "--"]

# コンテナ起動時に Ollama, Uvicorn, Discord ボットを順番に起動
CMD ["sh", "-c", "\
    ollama serve & \
    sleep 3 && \
    uvicorn server:app --host 0.0.0.0 --port 8000 & \
    python3 discord_bot.py \
"]
