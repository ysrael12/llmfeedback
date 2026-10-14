---
description: Revisão humana de saídas de LLM com llmfeedback. Sem argumento sobe o revisor; com "analisar" lê os feedbacks e planeja melhorias
argument-hint: "[analisar]"
---

# llmfeedback

Argumento: `$ARGUMENTS`

Ajuste para o projeto: ADAPTER=`pacote.modulo:Objeto`, DIR=`feedback`, PORT=`7930`.

## Se o argumento for `analisar`

Não suba nada. Rode `llmfeedback summary --dir DIR` e leia **todos** os `DIR/*.md`
(frontmatter YAML + "Comentário geral" + "Texto avaliado"). Então:

1. Agrupe por `tags`, por seção com `vote: down`, por `meta.prompt_hash` e `meta.model`.
   Compare nota média e % reprovado entre `prompt_hash` (o prompt melhorou ou piorou?).
2. Para cada problema recorrente, cite 1–2 trechos reais do texto avaliado e o comentário humano.
3. Reprovado pelo humano com `auto_checks.passed: true` = ponto cego: proponha um check
   automático novo (regex, seção obrigatória) no adaptador ou nos casos de avaliação.
4. Proponha mudanças concretas com arquivo (prompt, pós-processamento, checks).
   Não aplique: apresente o plano e espere aprovação.
5. Depois de aplicar: rode a avaliação automática do projeto e peça nova rodada humana.

## Caso contrário (subir o revisor)

1. `llmfeedback serve --adapter ADAPTER --dir DIR --port PORT` em background.
2. Aguarde `curl -sf localhost:PORT/health`.
3. Devolva o link `http://localhost:PORT` e explique em uma linha: 👍/👎 por seção, nota,
   tags e comentário; "Salvar feedback" grava `DIR/<data>_<caso>.md`.
4. Lembre que `/llmfeedback analisar` lê os feedbacks e planeja as melhorias.

O revisor não tem login: deixe em 127.0.0.1 e use túnel SSH para acesso remoto.
