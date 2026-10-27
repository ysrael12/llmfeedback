"""Adaptador que revisa saídas já geradas (logs de produção) em vez de chamar um LLM.

Cada linha do JSONL é um objeto com `output` (ou `text`) e, opcionalmente, `id`, `title`,
`input` e `model` / `prompt_hash` / `total_tokens` / `latency_ms` (ou um dict `meta`).
Gerar = devolver o que já foi servido, então revisar não custa token e o humano avalia
exatamente o que o usuário recebeu.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from llmfeedback.adapter import Case, Generation
from llmfeedback.checks import Rules, run_rules

_META_KEYS = ("model", "prompt_hash", "prompt", "total_tokens", "latency_ms")


class JsonlAdapter:
    def __init__(self, path: str | Path, *, sample: int | None = None, seed: int | None = None,
                 rules: Rules | None = None, name: str | None = None) -> None:
        """`sample`: revisa só N linhas sorteadas (`seed` fixa o sorteio). `rules`: checks do `checks.json`."""
        self.path = Path(path)
        self.name = name or self.path.stem
        self.rules = rules or []
        self._rows: dict[str, dict] = {}
        lines = [ln for ln in self.path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if sample is not None and sample < len(lines):
            keep = sorted(random.Random(seed).sample(range(len(lines)), sample))
            lines = [lines[i] for i in keep]
            numbers = keep
        else:
            numbers = range(len(lines))
        for n, ln in zip(numbers, lines):
            try:
                row = json.loads(ln)
            except json.JSONDecodeError as e:
                raise ValueError(f"{self.path}: linha {n + 1} não é JSON válido ({e.msg})") from None
            if not isinstance(row, dict) or not (row.get("output") or row.get("text")):
                continue
            self._rows[str(row.get("id") or f"linha-{n + 1}")] = row

    def list_cases(self) -> list[Case]:
        return [
            Case(id=i, title=str(r.get("title") or i), description=str(r.get("input") or "")[:300])
            for i, r in self._rows.items()
        ]

    async def generate(self, case_id: str) -> Generation:
        row = self._rows[case_id]
        text = str(row.get("output") or row.get("text"))
        meta = dict(row.get("meta") or {})
        meta.update({k: row[k] for k in _META_KEYS if k in row})
        return Generation(text=text, meta=meta, checks=run_rules(text, self.rules))
