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


# --- regras em arquivo: o que o humano apontou vira gate no CI -----------------------------
#
# `checks.json` é uma lista de regras versionada no git; o agente acrescenta uma por ponto cego:
#   [{"name": "sem-travessao", "type": "must_not_contain", "patterns": ["[—–]"]},
#    {"name": "estrutura", "type": "required_sections", "titles": ["Resumo", "Próximos passos"]}]

Rules = list[dict]

_RULE_TYPES = ("must_contain", "must_not_contain", "required_sections")


def load_rules(path) -> Rules:
    """Lê e valida o `checks.json`; erro de formato aborta (um gate quebrado não pode passar calado)."""
    import json
    from pathlib import Path

    rules = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(rules, list):
        raise ValueError("checks.json deve ser uma lista de regras")
    for r in rules:
        kind = r.get("type") if isinstance(r, dict) else None
        key = "titles" if kind == "required_sections" else "patterns"
        if kind not in _RULE_TYPES or not isinstance(r.get(key), list):
            raise ValueError(f"regra inválida: {r!r} (type {_RULE_TYPES}, com '{key}')")
        for p in r[key] if key == "patterns" else []:
            re.compile(p)
    return rules


def run_rules(text: str, rules: Rules) -> list[Check]:
    out: list[Check] = []
    for r in rules:
        label = r.get("name") or r["type"]
        if r["type"] == "required_sections":
            c = required_sections(text, r["titles"])
            out.append(Check(label, c.ok, c.detail))
            continue
        fn = must_contain if r["type"] == "must_contain" else must_not_contain
        bad = [c for c in fn(text, r["patterns"]) if not c.ok]
        out.append(Check(label, not bad, "; ".join(f"{c.name} {c.detail}".strip() for c in bad)))
    return out
