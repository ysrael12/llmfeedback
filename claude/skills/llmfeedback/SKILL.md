---
name: llmfeedback
description: Use when the project has (or should have) human review of LLM outputs with llmfeedback — connecting the application to the reviewer (adapter or production JSONL), starting the UI, reading the Markdown feedback, finding blind spots, comparing prompt versions, proposing prompt changes and creating checks.json for CI. Triggers: "llmfeedback", "review model outputs", "human feedback", "blind spot", "checks.json", "compare prompts", "CI gate for LLM", "revisar saídas do modelo", "ponto cego".
---

# llmfeedback

Human reviewer for LLM outputs. The human gives 👍/👎 per section, a 1–5 rating, tags and a comment; each review becomes **one `.md` file** (YAML frontmatter + comment + evaluated text) in `feedback/`. You (the agent) read those files, find patterns and propose fixes. There is no database: the feedback is the database.

Core idea: **what the human rejects while the automated checks passed is a blind spot**, and every blind spot becomes a rule in `checks.json` enforced by CI.

The reviewer UI, the `analisar` argument of `/llmfeedback` and the section markers in the feedback files (`## Comentário geral`, `## Texto avaliado`) are in Portuguese; keep those strings as they are.

## Before acting: find out which stage the project is in

```bash
llmfeedback --help          # installed? (pip install git+https://github.com/<user>/llmfeedback)
ls feedback/ checks.json    # are there feedbacks / rules already?
```

| Situation | Go to |
|---|---|
| No adapter and no logs | 1. Connect |
| `feedback/*.md` exist and the user wants to improve | 3. Analyze |
| The user wants to lock in regressions in CI | 4. CI gate |
| The user just wants to review | 2. Start the reviewer |

## 1. Connect the application (pick one)

**A. Adapter** — reviews what your prompt produces *today* (calls the LLM on demand). Create `my_project/review_adapter.py`:

```python
from llmfeedback import Case, Generation
from llmfeedback.checks import must_not_contain

class MyAdapter:
    name = "my-app"                          # required
    tags = ["wrong fact", "tone", "verbose"]  # optional: replaces the default tags

    def list_cases(self):                    # required
        return [Case(id="late-order", title="Late order", description="...")]

    async def generate(self, case_id):       # required
        text = await my_function(case_id)    # call the SAME function production uses
        return Generation(
            text=text,                        # Markdown; each #–### becomes a votable section
            meta={"model": "...", "prompt_hash": PROMPT_HASH, "prompt": PROMPT_TEXT},
            checks=must_not_contain(text, [r"[—–]"]),
        )
```

Rules that matter:
- `generate` must call the **same production code**; an adapter that reimplements the prompt reviews something else.
- `prompt_hash` must be **derived from the prompt text** (e.g. `sha256(prompt)[:16]`) or from the git commit. A hand-written hash that nobody remembers to bump hides the change.
- `meta["prompt"]` is optional: the text is written once to `feedback/prompts/<hash>.md` and enables the diff between versions in `summary`.
- Optional `display(text) -> str` shows the text the way the end user sees it.
- Ready-made examples: `examples/static_adapter.py` (no LLM) and `examples/openai_compatible_adapter.py` (OpenAI, DeepSeek, vLLM, Ollama).

**B. Production JSONL** — reviews outputs that were already served, with no token cost and no adapter. One output per line; only `output` (or `text`) is required:

```jsonl
{"id": "ord-4521", "input": "...", "output": "## Resumo\n...", "model": "x", "prompt_hash": "v3"}
```

Optional: `id`, `title`, `input`, `model`, `prompt_hash`, `prompt`, `total_tokens`, `latency_ms` (or a `meta` dict). A line that is not valid JSON aborts with `erro: ... linha N`; fix the file, do not skip the line.

## 2. Start the reviewer

```bash
llmfeedback serve --adapter my_project.review_adapter:MyAdapter --dir feedback --port 7930
llmfeedback serve --jsonl logs.jsonl --sample 30 --seed 1 --rules checks.json --dir feedback
```

- Use `--adapter` **or** `--jsonl`, never both. `--sample N` draws N lines (`--seed` makes it repeatable): prefer a sample over reviewing everything.
- Run it in the background, wait for `curl -sf localhost:7930/health` and hand over the link `http://localhost:7930`.
- Tell the user in one line: 👍/👎 per section, rating, tags, comment; "Salvar feedback" writes `feedback/<date>_<case>.md`.
- **A single worker only** (generations live in memory, expire after 1 h, max 200). No login: keep it on `127.0.0.1`; remote access only through an SSH tunnel.
- Verdict `reprovado` (rejected) = rating ≤ 2 **or** any section with 👎.
- If a vote returns 410, the generation expired: generate the case again.

Do not try to review in the human's place. Your role starts once the `.md` files exist.

## 3. Analyze the feedback

```bash
llmfeedback summary --dir feedback
```

It shows average rating and % rejected **per `prompt_hash`**, the most frequent tags, sections with 👎, the diff between consecutive prompt versions (if `meta["prompt"]` was recorded) and how many were rejected with green checks. Then read **all** the `feedback/*.md` files (not just the summary) and:

1. Group by `tags`, by sections with `vote: down`, by `meta.prompt_hash` and `meta.model`. Compare across `prompt_hash`: did the prompt improve or get worse? With few feedbacks per hash (fewer than ~5), say the comparison is weak instead of concluding.
2. For each recurring problem, quote 1–2 real excerpts from the "Texto avaliado" and the human comment. Without a quote, do not claim it.
3. **Blind spot** = `verdict: reprovado` with `auto_checks.passed: true`. For each one, propose a new rule (section 4).
4. Propose concrete changes, with file and excerpt (prompt, post-processing, checks). **Do not apply them:** present the plan and wait for approval.
5. After approval and applying: run the project's automated eval, generate a new `prompt_hash` and ask for a new human round (back to section 2). Only compare ratings across rounds that use the same set of cases.

Feedback file format (to read without tooling):

```markdown
---
case: late-order
rating: 2
tags: [wrong fact]
sections: [{title: Resumo, vote: down, comment: "..."}]
comment: "The deadline is missing."
meta: {model: x, prompt_hash: 92838cb2afe583f9}
auto_checks: {passed: true, failed: []}
verdict: reprovado
---
# Feedback 2026-10-14_141749_late-order
## Comentário geral ...
## Texto avaliado ...
```

Files in the old format (0.1.0) are still readable. If two feedbacks fell in the same second, the second one is `...-2.md`.

## 4. CI gate with checks.json

Every blind spot becomes a rule versioned in git:

```json
[
  {"name": "no-em-dash", "type": "must_not_contain", "patterns": ["[—–]"]},
  {"name": "has-deadline", "type": "must_contain", "patterns": ["\\d+ dias"]},
  {"name": "structure", "type": "required_sections", "titles": ["Resumo", "Próximos passos"]}
]
```

- Types: `must_contain` and `must_not_contain` (use `patterns`, which are **regex**) and `required_sections` (uses `titles`).
- Test the rule before handing it over: it must **fail** on the rejected text and **pass** on the approved ones.
- Run: `llmfeedback check --rules checks.json --jsonl outputs.jsonl` → exits 1 if any output fails (`FALHA <id>: <rule>`); use this command as a CI step.
- An invalid `checks.json` (unknown type, broken regex) **aborts** with `erro: ...`; it never "passes silently". Fix the file.
- The checks only evaluate text. Anything that needs judgment stays with the human.

## Pitfalls

- Do not edit the feedback `.md` files by hand: they are the record of the human evaluation.
- Do not commit `feedback/` with customers' personal data unless the user decides to; warn if the production JSONL contains it.
- Do not suggest `--adapter` and `--jsonl` together, nor multiple workers.
- If `llmfeedback` is not installed and the package is used from source, run with `PYTHONPATH=src` (on Windows/Git Bash, `"src;."`).
- Never invent ratings, tags or comments to "illustrate" real feedback.
