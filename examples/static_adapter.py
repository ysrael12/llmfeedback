"""Adaptador de demonstração, sem LLM: `llmfeedback serve --adapter examples.static_adapter:StaticAdapter`."""

from llmfeedback import Case, Generation
from llmfeedback.checks import must_not_contain

TEXTS = {
    "boas-vindas": "## Resumo\nSeu pedido **#123** foi aprovado — chega em 2 dias.\n\n## Próximos passos\n1. Confirme o endereço.\n2. Acompanhe pelo app.",
    "incidente": "## Situação\nHouve uma falha no servidor de pagamentos (HTTP 502) por 14 minutos.\n\n## Impacto\n- 3% das compras falharam.\n- Nenhum dado foi perdido.",
}


class StaticAdapter:
    name = "static-demo"
    tags = ["fato errado", "jargão técnico", "tom inadequado", "formatação"]

    def list_cases(self):
        return [Case(id=k, title=k, description="texto fixo de exemplo") for k in TEXTS]

    async def generate(self, case_id):
        text = TEXTS[case_id]
        return Generation(
            text=text,
            meta={"model": "nenhum", "prompt_hash": "demo-v1"},
            checks=must_not_contain(text, ["[—–]", r"\bHTTP \d{3}\b"]),
        )
