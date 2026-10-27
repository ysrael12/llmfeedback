from fastapi.testclient import TestClient

from llmfeedback import Case, Check, Generation, load_feedback
from llmfeedback.checks import must_contain, must_not_contain, required_sections
from llmfeedback.cli import load_adapter, summary
from llmfeedback.server import create_app

TEXT = "Intro.\n\n## Veredito\nPostura **boa**.\n\n## Riscos\n<script>alert(1)</script>"


class FakeAdapter:
    name = "fake"

    def list_cases(self):
        return [Case("c1", "Caso um", "desc")]

    async def generate(self, case_id):
        return Generation(TEXT, {"model": "m1", "prompt_hash": "p1", "total_tokens": 10}, [Check("regra", True)])


def test_fluxo_completo(tmp_path):
    client = TestClient(create_app(FakeAdapter(), feedback_dir=tmp_path))
    assert "Caso um" in client.get("/").text
    r = client.post("/generate/c1")
    assert r.status_code == 200 and "<strong>boa</strong>" in r.text and "<script>alert" not in r.text
    assert "prompt p1" in r.text
    run_id = r.text.split('name="run_id" value="')[1].split('"')[0]
    r = client.post("/feedback", data={"run_id": run_id, "rating": "5", "tags": ["prolixo", "nao-existe"],
                                       "vote_1": "up", "vote_2": "down", "comment_2": "<b>x</b>"})
    assert r.status_code == 200 and "&lt;b&gt;" in r.text
    [fb] = load_feedback(tmp_path)
    assert fb.tags == ["prolixo"] and [s.vote for s in fb.sections] == ["", "up", "down"]
    assert fb.verdict == "reprovado" and fb.meta["prompt_hash"] == "p1" and fb.auto_checks["passed"]
    assert client.get(f"/feedback/{fb.id}").status_code == 200
    assert client.post("/feedback", data={"run_id": run_id, "rating": "5"}).status_code == 410
    assert client.post("/generate/x").status_code == 404
    out = summary(tmp_path)
    assert "p1: 1" in out and "checks automáticos verdes: 1" in out


def test_display_e_tags_do_adaptador(tmp_path):
    a = FakeAdapter()
    a.tags = ["só esta"]
    a.display = lambda t: t.replace("boa", "ÓTIMA")
    r = TestClient(create_app(a, feedback_dir=tmp_path)).post("/generate/c1")
    assert "ÓTIMA" in r.text and "só esta" in r.text and "prolixo" not in r.text


def test_checks():
    assert all(c.ok for c in must_contain(TEXT, [r"boa"]))
    assert not must_not_contain(TEXT, [r"script"])[0].ok
    assert required_sections(TEXT, ["Veredito", "Riscos"]).ok
    assert not required_sections(TEXT, ["Riscos", "Veredito"]).ok


def test_load_adapter():
    a = load_adapter("examples.static_adapter:StaticAdapter")
    assert a.name == "static-demo" and len(a.list_cases()) == 2


def test_runs_expiram_e_ficam_limitados(tmp_path, monkeypatch):
    import llmfeedback.server as srv

    monkeypatch.setattr(srv, "MAX_RUNS", 3)
    client = TestClient(create_app(FakeAdapter(), feedback_dir=tmp_path))
    ids = [client.post("/generate/c1").text.split('name="run_id" value="')[1].split('"')[0] for _ in range(6)]
    assert client.post("/feedback", data={"run_id": ids[0], "rating": "5"}).status_code == 410
    assert client.post("/feedback", data={"run_id": ids[-1], "rating": "5"}).status_code == 200


def test_jsonl_e_gate(tmp_path):
    import json

    from llmfeedback.checks import load_rules
    from llmfeedback.cli import check
    from llmfeedback.jsonl import JsonlAdapter

    log = tmp_path / "prod.jsonl"
    log.write_text("\n".join(json.dumps(r) for r in [
        {"id": "a", "input": "pedido", "output": "## Resumo\nok", "model": "m", "prompt_hash": "p9"},
        {"output": "## Resumo\nruim — travessão"},
    ]), encoding="utf-8")
    rules = tmp_path / "checks.json"
    rules.write_text(json.dumps([{"name": "sem-travessao", "type": "must_not_contain", "patterns": ["—"]}]),
                     encoding="utf-8")
    ad = JsonlAdapter(log, rules=load_rules(rules))
    assert [c.id for c in ad.list_cases()] == ["a", "linha-2"]
    import asyncio
    g = asyncio.run(ad.generate("a"))
    assert g.meta == {"model": "m", "prompt_hash": "p9"} and g.checks[0].ok
    assert not asyncio.run(ad.generate("linha-2")).checks[0].ok
    assert check(log, rules) == 1
    assert len(JsonlAdapter(log, sample=1, seed=1).list_cases()) == 1
