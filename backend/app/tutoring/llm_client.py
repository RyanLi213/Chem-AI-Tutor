import requests

from app.config import LLM_MODEL, LLM_TIMEOUT, OLLAMA_URL


def generate_completion(prompt: str) -> dict:
    r = requests.post(
        OLLAMA_URL,
        json={"model": LLM_MODEL, "prompt": prompt, "stream": False},
        timeout=LLM_TIMEOUT,
    )
    # An Ollama error (e.g. model not pulled) returns JSON without "response";
    # raising here routes it to the caller's fallback instead of a KeyError crash.
    r.raise_for_status()
    data = r.json()
    return {
        "text": data["response"],
        "thinking": data.get("thinking", ""),
        "truncated": data.get("done_reason") != "stop",
        "duration_sec": data.get("eval_duration", 0) / 1e9,
    }
