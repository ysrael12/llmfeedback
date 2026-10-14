"""Checks genéricos para usar no adaptador (o que o humano apontou vira regra automática)."""

from __future__ import annotations

import re

from llmfeedback.adapter import Check
from llmfeedback.sections import split_sections


def must_contain(text: str, patterns: list[str]) -> list[Check]:
    out = []
    for p in patterns:
        ok = re.search(p, text or "") is not None
        out.append(Check(f"contem:{p}", ok, "" if ok else "não encontrado"))
    return out


def must_not_contain(text: str, patterns: list[str]) -> list[Check]:
    out = []
    for p in patterns:
        m = re.search(p, text or "")
        out.append(Check(f"nao_contem:{p}", m is None, m.group(0) if m else ""))
    return out


def required_sections(text: str, titles: list[str]) -> Check:
    """As seções existem e aparecem nesta ordem (comparação por prefixo, sem caixa)."""
    found = [t.lower() for t, _ in split_sections(text)]
    pos = []
    for name in titles:
        idx = next((i for i, t in enumerate(found) if t.startswith(name.lower())), None)
        if idx is None:
            return Check("secoes", False, f"falta '{name}'")
        pos.append(idx)
    return Check("secoes", pos == sorted(pos), "" if pos == sorted(pos) else "ordem errada")
