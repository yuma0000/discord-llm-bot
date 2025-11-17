worker ollama create mania -f mania-model.Q8_K_M.gguf
worker ollama run mania

web: sh -c "ollama serve & sleep 3 && uvicorn server:app --host 0.0.0.0 --port 8000 & python3 discord_bot.py"
