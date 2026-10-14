"""Markdown mínimo → HTML seguro. O texto vem de um LLM: escapa primeiro, formata depois."""

from __future__ import annotations

import html
import re

from markupsafe import Markup

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_CODE = re.compile(r"`([^`]+)`")


def _inline(s: str) -> str:
    s = _CODE.sub(r"<code>\1</code>", s)
    s = _BOLD.sub(r"<strong>\1</strong>", s)
    return _ITALIC.sub(r"<em>\1</em>", s)


def markdown_safe(text: str | None) -> Markup:
    out: list[str] = []
    in_list: str | None = None

    def close() -> None:
        nonlocal in_list
        if in_list:
            out.append(f"</{in_list}>")
            in_list = None

    for raw in html.escape(text or "", quote=False).splitlines():
        line = raw.strip()
        if not line:
            close()
            continue
        if m := re.match(r"^#{1,6}\s+(.+)$", line):
            close()
            out.append(f"<h4>{_inline(m.group(1))}</h4>")
        elif m := re.match(r"^[-*]\s+(.+)$", line):
            if in_list != "ul":
                close()
                out.append("<ul>")
                in_list = "ul"
            out.append(f"<li>{_inline(m.group(1))}</li>")
        elif m := re.match(r"^\d+[.)]\s+(.+)$", line):
            if in_list != "ol":
                close()
                out.append("<ol>")
                in_list = "ol"
            out.append(f"<li>{_inline(m.group(1))}</li>")
        else:
            close()
            out.append(f"<p>{_inline(line)}</p>")
    close()
    return Markup("\n".join(out))
