"""Feedback como banco em Markdown: um `.md` por avaliação.

Frontmatter YAML com os campos consultáveis (caso, prompt_hash, votos, tags) e
corpo com o comentário geral e o texto avaliado. Legível por humanos, versionável
no git e fácil de um agente de IA ler.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

_SAFE_ID = re.compile(r"[^a-z0-9_-]+")
_TEXT_MARK = "## Texto avaliado"
_COMMENT_MARK = "## Comentário geral"
_NO_COMMENT = "_(sem comentário)_"


@dataclass
class SectionVote:
    title: str
    vote: str  # "up" | "down" | ""
    comment: str = ""


@dataclass
class Feedback:
    case: str
    rating: int
    tags: list[str] = field(default_factory=list)
    sections: list[SectionVote] = field(default_factory=list)
    comment: str = ""
    text: str = ""
    adapter: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
    auto_checks: dict[str, Any] = field(default_factory=dict)
    reviewer: str = ""
    created_at: str = ""
    id: str = ""

    @property
    def verdict(self) -> str:
        """Reprovado se a nota for ≤ 2 ou alguma seção levou 👎."""
        down = any(s.vote == "down" for s in self.sections)
        return "reprovado" if self.rating <= 2 or down else "aprovado"


def _unique_path(directory: Path, base: str) -> Path:
    """`base.md`, ou `base-2.md`, `base-3.md`… se já existir (nada é sobrescrito)."""
    path, n = directory / f"{base}.md", 1
    while path.exists():
        n += 1
        path = directory / f"{base}-{n}.md"
    return path


def _prompt_path(directory: Path, prompt_hash: str) -> Path:
    return directory / "prompts" / f"{_SAFE_ID.sub('_', str(prompt_hash))[:64]}.md"


def load_prompt(directory: Path, prompt_hash: str) -> str | None:
    """Texto do prompt guardado para este hash, ou None."""
    path = _prompt_path(Path(directory), prompt_hash)
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _body(fb: Feedback) -> str:
    return (
        f"# Feedback {fb.id}\n\n{_COMMENT_MARK}\n\n{fb.comment.strip() or _NO_COMMENT}\n\n"
        f"{_TEXT_MARK}\n\n{fb.text.strip()}\n"
    )


def save_feedback(fb: Feedback, directory: Path) -> Path:
    now = datetime.now(timezone.utc)
    fb.created_at = fb.created_at or now.isoformat(timespec="seconds")
    slug = _SAFE_ID.sub("-", fb.case.lower()).strip("-") or "caso"
    directory.mkdir(parents=True, exist_ok=True)
    path = _unique_path(directory, fb.id or f"{now:%Y-%m-%d_%H%M%S}_{slug}")
    fb.id = path.stem
    meta = asdict(fb)
    meta.pop("text")
    # o texto do prompt (meta["prompt"]) vai uma vez só para prompts/<hash>.md, não para cada feedback
    prompt = meta["meta"].pop("prompt", None)
    if prompt and meta["meta"].get("prompt_hash"):
        ppath = _prompt_path(directory, meta["meta"]["prompt_hash"])
        if not ppath.exists():
            ppath.parent.mkdir(parents=True, exist_ok=True)
            ppath.write_text(str(prompt), encoding="utf-8")
    meta["verdict"] = fb.verdict
    # o comentário vai também no frontmatter: YAML escapa qualquer conteúdo, então o parse
    # não depende de o texto conter (ou não) os cabeçalhos do corpo
    front = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=1000)
    path.write_text(f"---\n{front}---\n\n{_body(fb)}", encoding="utf-8")
    return path


def parse_feedback(text: str) -> Feedback:
    if not text.startswith("---\n"):
        raise ValueError("sem frontmatter")
    end = text.index("\n---\n", 4)
    meta = yaml.safe_load(text[4:end]) or {}
    body = text[end + 5 :].lstrip("\n")
    meta.pop("verdict", None)
    sections = [SectionVote(**s) for s in meta.pop("sections", None) or []]
    if "comment" in meta:  # formato atual
        fb = Feedback(**meta, sections=sections)
        prefix = _body(fb).rstrip("\n") + "\n\n"  # fb.text ainda vazio: sobra só o cabeçalho
        fb.text = body[len(prefix):].rstrip("\n") if body.startswith(prefix) else ""
        return fb
    # formato antigo (0.1.0): comentário só no corpo
    evaluated = body.split(f"{_TEXT_MARK}\n\n", 1)[1].rstrip("\n") if _TEXT_MARK in body else ""
    comment = ""
    if _COMMENT_MARK in body:
        comment = body.split(f"{_COMMENT_MARK}\n\n", 1)[1].split(f"\n\n{_TEXT_MARK}", 1)[0].strip()
        comment = "" if comment == _NO_COMMENT else comment
    return Feedback(**meta, sections=sections, text=evaluated, comment=comment)


def load_feedback(directory: Path) -> list[Feedback]:
    """Todos os feedbacks, mais recentes primeiro. Arquivo inválido é ignorado."""
    out = []
    for path in sorted(Path(directory).glob("*.md"), reverse=True):
        try:
            out.append(parse_feedback(path.read_text(encoding="utf-8")))
        except (ValueError, yaml.YAMLError, TypeError):
            continue
    return out
