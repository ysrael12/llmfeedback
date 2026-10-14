"""Revisor HTMX: gera pelo adaptador, mostra seção a seção e grava o voto em `.md`."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from llmfeedback import store
from llmfeedback.adapter import Adapter
from llmfeedback.render import markdown_safe
from llmfeedback.sections import split_sections

DEFAULT_TAGS = [
    "fato errado",
    "número sem fonte",
    "inventou dado",
    "tom inadequado",
    "jargão técnico",
    "seção faltando",
    "prolixo",
    "formatação",
]

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
TEMPLATES.env.filters["md"] = markdown_safe


def create_app(
    adapter: Adapter,
    *,
    feedback_dir: Path,
    tags: list[str] | None = None,
    display: Callable[[str], str] | None = None,
    title: str = "llmfeedback",
) -> FastAPI:
    """`display` transforma o texto antes de mostrar (ex.: o mesmo pós-processamento que
    o usuário final vê); o `.md` guarda sempre o texto cru gerado."""
    # O adaptador pode trazer as próprias tags e o próprio `display`.
    tags = tags or getattr(adapter, "tags", None) or DEFAULT_TAGS
    show = display or getattr(adapter, "display", None) or (lambda t: t)
    feedback_dir = Path(feedback_dir)
    app = FastAPI(title=title, docs_url=None, redoc_url=None, openapi_url=None)
    runs: dict[str, dict[str, Any]] = {}  # geração em memória até o voto; o form só manda o id
    base = {"title": title, "adapter": adapter.name}

    def cases() -> dict[str, Any]:
        return {c.id: c for c in adapter.list_cases()}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request, "index.html",
            {**base, "cases": list(cases().values()), "feedbacks": store.load_feedback(feedback_dir)[:30]},
        )

    @app.post("/generate/{case_id}", response_class=HTMLResponse)
    async def generate(request: Request, case_id: str) -> HTMLResponse:
        case = cases().get(case_id)
        if case is None:
            raise HTTPException(404, "caso desconhecido")
        gen = await adapter.generate(case_id)
        run_id = uuid.uuid4().hex[:12]
        sections = split_sections(gen.text)
        runs[run_id] = {"case": case, "gen": gen, "titles": [t for t, _ in sections]}
        shown = [(t, show(b)) for t, b in sections]
        return TEMPLATES.TemplateResponse(
            request, "_report.html",
            {**base, "run_id": run_id, "case": case, "sections": shown, "gen": gen, "tags": tags},
        )

    @app.post("/feedback", response_class=HTMLResponse)
    async def feedback(request: Request, run_id: str = Form(...), rating: int = Form(...)) -> HTMLResponse:
        run = runs.pop(run_id, None)
        if run is None:
            raise HTTPException(410, "geração expirou — gere de novo")
        form = await request.form()
        gen = run["gen"]
        fb = store.Feedback(
            case=run["case"].id,
            rating=max(1, min(5, rating)),
            tags=[t for t in form.getlist("tags") if t in tags],
            sections=[
                store.SectionVote(title, str(form.get(f"vote_{i}", "")), str(form.get(f"comment_{i}", "")).strip())
                for i, title in enumerate(run["titles"])
            ],
            comment=str(form.get("comment", "")).strip(),
            text=gen.text,
            adapter=adapter.name,
            meta=dict(gen.meta),
            auto_checks={
                "passed": all(c.ok for c in gen.checks),
                "failed": [f"{c.name}: {c.detail}" if c.detail else c.name for c in gen.checks if not c.ok],
            },
            reviewer=str(form.get("reviewer", "")).strip(),
        )
        path = store.save_feedback(fb, feedback_dir)
        return TEMPLATES.TemplateResponse(request, "_saved.html", {**base, "fb": fb, "path": path.name})

    @app.get("/feedback/{fb_id}", response_class=HTMLResponse)
    async def show_feedback(request: Request, fb_id: str) -> HTMLResponse:
        path = feedback_dir / f"{Path(fb_id).name}.md"
        if not path.is_file():
            raise HTTPException(404)
        fb = store.parse_feedback(path.read_text(encoding="utf-8"))
        return TEMPLATES.TemplateResponse(request, "_saved.html", {**base, "fb": fb, "path": path.name})

    return app
