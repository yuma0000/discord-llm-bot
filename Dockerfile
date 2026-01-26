FROM python:3.12-slim

# ===== 基本設定 =====
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# ===== 必要パッケージ =====
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    inkscape \
    && rm -rf /var/lib/apt/lists/* \
    && apt install -y fonts-noto-cjk \
    fc-cache -fv

# ===== Python依存関係 =====
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ===== Botコード =====
COPY . .

# ===== Railway 実行 =====
CMD ["python", "discord_bot.py"]
