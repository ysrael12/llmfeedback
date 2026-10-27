---
description: Human review of LLM outputs with llmfeedback. With no argument it starts the reviewer; with "analisar" it reads the feedback and plans improvements
argument-hint: "[analisar]"
---

# llmfeedback

Argument: `$ARGUMENTS`

Adjust for the project: ADAPTER=`package.module:Object`, DIR=`feedback`, PORT=`7930`.

## If the argument is `analisar`

Do not start anything. Run `llmfeedback summary --dir DIR` and read **all** of `DIR/*.md`
(YAML frontmatter + "Comentário geral" + "Texto avaliado"). Then:

1. Group by `tags`, by sections with `vote: down`, by `meta.prompt_hash` and `meta.model`.
   Compare average rating and % rejected across `prompt_hash` (did the prompt improve or get worse?).
2. For each recurring problem, quote 1–2 real excerpts of the evaluated text and the human comment.
3. Rejected by the human with `auto_checks.passed: true` = blind spot: propose a new automated
   check (regex, required section) as a rule in `checks.json` (types `must_contain`,
   `must_not_contain`, `required_sections`), which CI enforces with
   `llmfeedback check --rules checks.json --jsonl outputs.jsonl`.
4. Propose concrete changes with the file (prompt, post-processing, checks).
   Do not apply them: present the plan and wait for approval.
5. After applying: run the project's automated evaluation and ask for a new human round.

## Otherwise (start the reviewer)

1. `llmfeedback serve --adapter ADAPTER --dir DIR --port PORT` in the background.
2. Wait for `curl -sf localhost:PORT/health`.
3. Return the link `http://localhost:PORT` and explain in one line: 👍/👎 per section, rating,
   tags and comment; "Salvar feedback" writes `DIR/<date>_<case>.md`.
4. Remind them that `/llmfeedback analisar` reads the feedback and plans the improvements.

The reviewer has no login: keep it on 127.0.0.1 and use an SSH tunnel for remote access.
