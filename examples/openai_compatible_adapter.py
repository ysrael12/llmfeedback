"""Adaptador para qualquer API compatível com OpenAI (OpenAI, DeepSeek, vLLM, Ollama…).

    export LLM_BASE_URL=https://api.deepseek.com/v1 LLM_API_KEY=... LLM_MODEL=deepseek-v4-flash
    llmfeedback serve --adapter examples.openai_compatible_adapter:Adapter

Casos em `examples/cases/*.json`: {"id", "description", "input", "must_not_contain": [...]}.
O system prompt fica em `examples/system_prompt.md`; o hash dele vai para cada feedback,
então dá para comparar a nota entre versões do prompt. Requer `pip install httpx`.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import httpx

from llmfeedback import Case, Generation
from llmfeedback.checks import must_not_contain

HERE = Path(__file__).parent


class Adapter:
    name = "openai-compatible"

    def __init__(self) -> None:
        self.base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
        self.key = os.environ["LLM_API_KEY"]
        self.system = (HERE / "system_prompt.md").read_text(encoding="utf-8")

    def _cases(self) -> dict[str, dict]:
        return {d["id"]: d for d in (json.loads(p.read_text(encoding="utf-8")) for p in sorted((HERE / "cases").glob("*.json")))}

    def list_cases(self):
        return [Case(id=c["id"], title=c["id"], description=c.get("description", "")) for c in self._cases().values()]

    async def generate(self, case_id):
        case = self._cases()[case_id]
        started = time.monotonic()
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.key}"},
                json={"model": self.model, "messages": [
                    {"role": "system", "content": self.system},
                    {"role": "user", "content": case["input"]},
                ]},
            )
            r.raise_for_status()
            data = r.json()
        text = data["choices"][0]["message"]["content"]
        return Generation(
            text=text,
            meta={
                "model": data.get("model", self.model),
                "prompt_hash": hashlib.sha256(self.system.encode()).hexdigest()[:16],
                "total_tokens": (data.get("usage") or {}).get("total_tokens"),
                "latency_ms": round((time.monotonic() - started) * 1000),
            },
            checks=must_not_contain(text, case.get("must_not_contain", [])),
        )
