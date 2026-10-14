"""Divisão do texto em seções pelos cabeçalhos Markdown (`#` a `###`)."""

from __future__ import annotations

import re

_HEADING = re.compile(r"^\s*#{1,3}\s+(.+?)\s*$")


def split_sections(text: str, intro_title: str = "Intro") -> list[tuple[str, str]]:
    """Texto → [(título, corpo)]; o que vem antes do primeiro cabeçalho vira `intro_title`."""
    parts: list[tuple[str, str]] = []
    title, buf = intro_title, []
    for line in (text or "").splitlines():
        m = _HEADING.match(line)
        if m:
            if "".join(buf).strip():
                parts.append((title, "\n".join(buf).strip()))
            title, buf = m.group(1).strip().strip("*").strip(), []
        else:
            buf.append(line)
    if "".join(buf).strip() or not parts:
        parts.append((title, "\n".join(buf).strip()))
    return parts
