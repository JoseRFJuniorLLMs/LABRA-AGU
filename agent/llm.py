"""
Cliente LLM LOCAL (OpenAI-compatible) para o orquestrador agêntico.

Mesma configuração do parser (`LABRA_LLM_*`); por padrão LM Studio + gemma-4-e4b.
LGPD: o modelo corre LOCAL — dados de processo (CPF, sigilo) NUNCA saem da
máquina. Usa só a biblioteca-padrão (urllib), sem dependências. Degrada
graciosamente: se o servidor estiver em baixo, `available()` devolve False e o
agente usa o planeador determinístico.
"""
import json
import os
import urllib.request

BASE_URL = os.environ.get("LABRA_LLM_BASE_URL", "http://localhost:1234/v1")
MODEL = os.environ.get("LABRA_LLM_MODEL", "gemma-4-e4b")
API_KEY = os.environ.get("LABRA_LLM_API_KEY", "local")


class LocalLLM:
    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.base = (base_url or BASE_URL).rstrip("/")
        self.model = model or MODEL

    def _headers(self):
        return {"Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}"}

    def available(self, timeout: float = 3.0) -> bool:
        """True se o servidor local responde (modelo carregado)."""
        try:
            req = urllib.request.Request(self.base + "/models",
                                         headers=self._headers())
            urllib.request.urlopen(req, timeout=timeout)
            return True
        except Exception:
            return False

    def chat(self, messages, temperature: float = 0.2,
             max_tokens: int = 1400) -> str:
        body = json.dumps({"model": self.model, "messages": messages,
                           "temperature": temperature,
                           "max_tokens": max_tokens}).encode("utf-8")
        req = urllib.request.Request(self.base + "/chat/completions",
                                     data=body, headers=self._headers())
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read())
        return data["choices"][0]["message"]["content"]

    def chat_json(self, messages, **kw) -> dict:
        """Pede ao modelo e extrai o primeiro objeto JSON da resposta
        (modelos pequenos costumam embrulhar o JSON em texto)."""
        txt = self.chat(messages, **kw)
        i, j = txt.find("{"), txt.rfind("}")
        if i >= 0 and j > i:
            try:
                return json.loads(txt[i:j + 1])
            except json.JSONDecodeError:
                return {}
        return {}
