worker ollama/ollama:latest
worker apk update && apk add python3 py3-pip
worker pip install --no-cache-dir -r requirements.txt
worker wget https://mt.f5.si/mania-model.Q8_K_M.gguf
worker ollama create mania -f mania-model.Q8_K_M.gguf
worker ollama pull llama3

worker ["sh", "-c", "\
    ollama serve & \
    sleep 3 && \
    uvicorn server:app --host 0.0.0.0 --port 8000 & \
    python3 discord_bot.py \
"]

web: python discord_bot.py
