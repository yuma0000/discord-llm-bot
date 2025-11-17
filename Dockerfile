FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# 基本パッケージ
RUN apt update && apt install -y \
    curl wget git python3 python3-pip unzip sudo

# VSCode Web (code-server) インストール
RUN curl -fsSL https://code-server.dev/install.sh | sh

# code-server を外部アクセス可能に
EXPOSE 8080

# 認証なしで起動
CMD ["code-server", "--bind-addr", "0.0.0.0:8080", "/workspace", "--auth", "none"]
