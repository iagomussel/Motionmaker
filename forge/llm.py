import json
import re

import requests


class Ollama:
    def __init__(self, host="http://localhost:11434", timeout=900):
        self.host = host.rstrip("/")
        self.timeout = timeout

    def chat(self, model, system, user, json_mode=False, temperature=0.5, num_ctx=16384):
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": num_ctx},
        }
        if json_mode:
            body["format"] = "json"
        r = requests.post(f"{self.host}/api/chat", json=body, timeout=self.timeout)
        r.raise_for_status()
        return r.json()["message"]["content"]

    def chat_json(self, model, system, user, retries=2, **kw):
        last = None
        for _ in range(retries + 1):
            raw = self.chat(model, system, user, json_mode=True, **kw)
            try:
                return json.loads(raw)
            except json.JSONDecodeError as e:
                last = e
                m = re.search(r"\{.*\}", raw, re.S)
                if m:
                    try:
                        return json.loads(m.group(0))
                    except json.JSONDecodeError:
                        pass
        raise RuntimeError(f"Modelo não devolveu JSON válido: {last}")


def extract_js(text):
    """Pega o bloco ```js da resposta; se não houver, usa o texto todo."""
    m = re.search(r"```(?:js|javascript)?\s*\n(.*?)```", text, re.S)
    code = m.group(1) if m else text
    return code.strip()
