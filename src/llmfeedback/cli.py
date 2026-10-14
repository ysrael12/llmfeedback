"""`llmfeedback serve --adapter pacote.modulo:objeto` e `llmfeedback summary`."""

from __future__ import annotations

import argparse
import importlib
import sys
from collections import Counter, defaultdict
from pathlib import Path

from llmfeedback.store import load_feedback


def load_adapter(spec: str):
    """`modulo:atributo`; se o atributo for uma classe ou função, é chamado sem argumentos."""
    module_name, _, attr = spec.partition(":")
    if not attr:
        raise SystemExit("--adapter precisa ser 'modulo:objeto'")
    sys.path.insert(0, str(Path.cwd()))
    obj = getattr(importlib.import_module(module_name), attr)
    if isinstance(obj, type) or (callable(obj) and not hasattr(obj, "generate")):
        obj = obj()
    return obj


def summary(directory: Path) -> str:
    fbs = load_feedback(directory)
    if not fbs:
        return f"nenhum feedback em {directory}"
    lines = [f"{len(fbs)} feedbacks em {directory}"]
    by_prompt: dict[str, list] = defaultdict(list)
    for fb in fbs:
        by_prompt[str(fb.meta.get("prompt_hash") or "n/d")].append(fb)
    lines.append("\npor prompt_hash:")
    for ph, items in by_prompt.items():
        avg = sum(f.rating for f in items) / len(items)
        rej = sum(f.verdict == "reprovado" for f in items) / len(items)
        lines.append(f"  {ph}: {len(items)} · nota média {avg:.1f} · reprovado {rej:.0%}")
    tags = Counter(t for fb in fbs for t in fb.tags)
    if tags:
        lines.append("\ntags: " + ", ".join(f"{t} ({n})" for t, n in tags.most_common()))
    down = Counter(s.title for fb in fbs for s in fb.sections if s.vote == "down")
    if down:
        lines.append("seções com 👎: " + ", ".join(f"{t} ({n})" for t, n in down.most_common()))
    missed = sum(1 for fb in fbs if fb.verdict == "reprovado" and fb.auto_checks.get("passed"))
    lines.append(f"\nreprovados pelo humano com checks automáticos verdes: {missed}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="llmfeedback")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve", help="sobe o revisor")
    serve.add_argument("--adapter", required=True, help="modulo:objeto que implementa o Adapter")
    serve.add_argument("--dir", default="feedback", help="pasta dos .md (default: ./feedback)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=7930)
    serve.add_argument("--title", default="llmfeedback")
    summ = sub.add_parser("summary", help="resume os feedbacks salvos")
    summ.add_argument("--dir", default="feedback")
    args = parser.parse_args(argv)

    if args.cmd == "summary":
        print(summary(Path(args.dir)))
        return
    import uvicorn

    from llmfeedback.server import create_app

    adapter = load_adapter(args.adapter)
    app = create_app(adapter, feedback_dir=Path(args.dir), title=args.title)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
