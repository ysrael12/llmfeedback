"""`llmfeedback serve --adapter pacote.modulo:objeto` e `llmfeedback summary`."""

from __future__ import annotations

import argparse
import importlib
import sys
from collections import Counter, defaultdict
from pathlib import Path

from llmfeedback.store import load_feedback, load_prompt


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
    lines += _prompt_diffs(directory, by_prompt)
    tags = Counter(t for fb in fbs for t in fb.tags)
    if tags:
        lines.append("\ntags: " + ", ".join(f"{t} ({n})" for t, n in tags.most_common()))
    down = Counter(s.title for fb in fbs for s in fb.sections if s.vote == "down")
    if down:
        lines.append("seções com 👎: " + ", ".join(f"{t} ({n})" for t, n in down.most_common()))
    missed = sum(1 for fb in fbs if fb.verdict == "reprovado" and fb.auto_checks.get("passed"))
    lines.append(f"\nreprovados pelo humano com checks automáticos verdes: {missed}")
    return "\n".join(lines)


def _prompt_diffs(directory: Path, by_prompt: dict[str, list]) -> list[str]:
    """Diff entre versões consecutivas do prompt (ordem do primeiro feedback de cada uma)."""
    import difflib

    order = sorted(
        (ph for ph in by_prompt if ph != "n/d"),
        key=lambda ph: min(f.created_at for f in by_prompt[ph]),
    )
    out: list[str] = []
    for old, new in zip(order, order[1:]):
        a, b = load_prompt(directory, old), load_prompt(directory, new)
        if a is None or b is None:
            continue
        diff = list(difflib.unified_diff(a.splitlines(), b.splitlines(), old, new, lineterm="", n=1))
        out.append(f"\nmudança de prompt {old} → {new}:")
        out += [f"  {line}" for line in diff] or ["  (sem diferença de texto)"]
    return out


def check(jsonl: Path, rules_path: Path) -> int:
    """Roda as regras sobre cada saída do JSONL; devolve o código de saída (0 ok, 1 falhas)."""
    import asyncio

    from llmfeedback.checks import load_rules
    from llmfeedback.jsonl import JsonlAdapter

    adapter = JsonlAdapter(jsonl, rules=load_rules(rules_path))
    cases = adapter.list_cases()
    if not cases:
        print(f"nenhuma saída em {jsonl}")
        return 1
    failed = 0
    for case in cases:
        gen = asyncio.run(adapter.generate(case.id))
        bad = [c for c in gen.checks if not c.ok]
        failed += bool(bad)
        for c in bad:
            print(f"FALHA {case.id}: {c.name}" + (f" ({c.detail})" if c.detail else ""))
    print(f"{len(cases) - failed}/{len(cases)} saídas passaram")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="llmfeedback")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve", help="sobe o revisor")
    serve.add_argument("--adapter", help="modulo:objeto que implementa o Adapter")
    serve.add_argument("--jsonl", help="em vez de --adapter: revisa saídas já geradas deste arquivo JSONL")
    serve.add_argument("--sample", type=int, help="com --jsonl: revisa só N linhas sorteadas")
    serve.add_argument("--seed", type=int, help="com --sample: fixa o sorteio")
    serve.add_argument("--rules", help="com --jsonl: checks.json aplicado a cada saída")
    serve.add_argument("--dir", default="feedback", help="pasta dos .md (default: ./feedback)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=7930)
    serve.add_argument("--title", default="llmfeedback")
    summ = sub.add_parser("summary", help="resume os feedbacks salvos")
    summ.add_argument("--dir", default="feedback")
    chk = sub.add_parser("check", help="gate de CI: roda o checks.json sobre um JSONL (sai 1 se algo falhar)")
    chk.add_argument("--rules", default="checks.json")
    chk.add_argument("--jsonl", required=True)
    args = parser.parse_args(argv)

    if args.cmd == "summary":
        print(summary(Path(args.dir)))
        return
    try:
        if args.cmd == "check":
            sys.exit(check(Path(args.jsonl), Path(args.rules)))
        _serve(args)
    except (ValueError, OSError) as e:  # arquivo ausente, JSONL ou checks.json inválido
        raise SystemExit(f"erro: {e}") from None


def _serve(args: argparse.Namespace) -> None:
    if bool(args.adapter) == bool(args.jsonl):
        raise SystemExit("use --adapter OU --jsonl")
    import uvicorn

    from llmfeedback.server import create_app

    if args.jsonl:
        from llmfeedback.checks import load_rules
        from llmfeedback.jsonl import JsonlAdapter

        rules = load_rules(args.rules) if args.rules else None
        adapter = JsonlAdapter(args.jsonl, sample=args.sample, seed=args.seed, rules=rules)
    else:
        adapter = load_adapter(args.adapter)
    app = create_app(adapter, feedback_dir=Path(args.dir), title=args.title)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
