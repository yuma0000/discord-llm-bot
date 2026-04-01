FROM python:3.12-slim

# ===== 基本設定 =====
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# ===== 必要パッケージ =====
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    inkscape \
    fonts-noto-cjk \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

RUN cp Plus50yen-de-TonJiru-ni-Henkoudekimasu.ttf ~/.local/share/fonts/ && fc-cache -fv && fc-list

# ===== Python依存関係 =====
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ===== Botコード =====
COPY . .

# ===== Railway 実行 =====
CMD ["python", "discord_bot.py"]
