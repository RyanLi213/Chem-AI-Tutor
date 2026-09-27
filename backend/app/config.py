import os

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3:1.7b")
LLM_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "100"))
