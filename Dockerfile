FROM python:3.12-slim

# ===== 基本設定 =====
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# ===== 必要パッケージ =====
COPY Plus50yen-de-TonJiru-ni-Henkoudekimasu.ttf .
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    inkscape \
    fonts-noto-cjk \
    && cp Plus50yen-de-TonJiru-ni-Henkoudekimasu.ttf /usr/share/fonts/ \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

# ===== Python依存関係 =====
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ===== Botコード =====
COPY . .

# ===== Railway 実行 =====
CMD ["python", "discord_bot.py"]
