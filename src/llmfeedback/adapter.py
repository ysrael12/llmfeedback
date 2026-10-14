"""Contrato entre o llmfeedback e o seu projeto.

O projeto implementa um objeto com `list_cases()` e `generate(case_id)`; o
revisor não sabe nada do seu modelo, prompt ou dados.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class Case:
    """Algo que pode ser gerado e avaliado (um caso de eval, um cenário, um ticket)."""

    id: str
    title: str = ""
    description: str = ""


@dataclass
class Check:
    """Verificação automática feita pelo projeto (mostrada ao lado do voto humano)."""

    name: str
    ok: bool
    detail: str = ""


@dataclass
class Generation:
    """Resultado de uma geração.

    `meta` é livre, mas o revisor destaca `model`, `prompt_hash`, `total_tokens` e
    `latency_ms` quando presentes; `prompt_hash` é o que permite comparar versões de prompt.
    """

    text: str
    meta: dict[str, Any] = field(default_factory=dict)
    checks: list[Check] = field(default_factory=list)


@runtime_checkable
class Adapter(Protocol):
    """Obrigatórios: `name`, `list_cases`, `generate`.

    Opcionais (lidos com getattr): `tags: list[str]` para trocar as tags padrão e
    `display(text) -> str` para mostrar o texto como o usuário final o vê.
    """

    name: str

    def list_cases(self) -> list[Case]: ...

    async def generate(self, case_id: str) -> Generation: ...
