import os
import urllib.request

MODEL_URL = "https://mt.f5.si/mania-model.Q8_K_M.gguf"
MODEL_PATH = os.path.join(os.getcwd(), "mania-model.Q8_K_M.gguf")

if not os.path.exists(MODEL_PATH):
    print(f"Downloading model from {MODEL_URL} ...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print(f"Model downloaded to {MODEL_PATH}")
else:
    print(f"Model already exists at {MODEL_PATH}")
