# ----------------------------------------------------
# STAGE 1: Build Environment and Dependencies
# ----------------------------------------------------

# Ollama公式イメージをベースとして使用
FROM ollama/ollama:latest

# 開発/実行に必要なPythonとパッケージマネージャーをインストール
# apkはAlpine Linuxのパッケージマネージャーです
RUN apk update && apk add --no-cache python3 py3-pip wget

# 作業ディレクトリを設定
WORKDIR /app

# 必要なPythonライブラリをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ----------------------------------------------------
# STAGE 2: Model and Application Setup
# ----------------------------------------------------

# 1. カスタムモデルのダウンロード ( mania-model.Q8_K_M.gguf )
# このファイルは、Ollamaの標準レジストリにはないため、wgetで直接ダウンロードします。
RUN wget https://mt.f5.si/mania-model.Q8_K_M.gguf

# 2. Modelfileを作成し、ローカルのGGUFファイルを指定してカスタムモデルとして登録
# ollama create [モデル名] -f [Modelfile] で実行可能になります。
RUN echo "FROM ./mania-model.Q8_K_M.gguf" > Modelfile
RUN ollama create mania -f Modelfile

# 3. フォールバック用の llama3 モデルをダウンロード
# これにより、コンテナ起動時にモデルをダウンロードする待ち時間がなくなります。
RUN ollama pull llama3

# アプリケーションのコードをコピー
COPY server.py .
COPY discord_bot.py .

# ----------------------------------------------------
# STAGE 3: Runtime
# ----------------------------------------------------

# Uvicornサーバーのポートを公開 (WebUIとして使う場合)
EXPOSE 8000

# コンテナ起動時に実行されるコマンド
# sh -c を使用して、複数のプロセスを並行して起動します。
CMD ["sh", "-c", "\
    # 1. Ollamaサービスをバックグラウンドで起動
    ollama serve & \
    # 2. サービス起動まで待機
    sleep 3 && \
    # 3. Uvicornサーバーをバックグラウンドで起動
    uvicorn server:app --host 0.0.0.0 --port 8000 & \
    # 4. Discordボットをフォアグラウンドで起動 (これがメインのプロセスになります)
    python3 discord_bot.py \
"]
