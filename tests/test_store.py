from llmfeedback import Feedback, SectionVote, load_feedback, save_feedback
from llmfeedback.sections import split_sections

TEXT = "Intro curta.\n\n## Veredito\nPostura **boa**.\n\n## Riscos\n<script>alert(1)</script>\n---\nfim"


def _fb(**kw):
    base = dict(case="Caso 01", rating=4, tags=["jargão técnico"],
                sections=[SectionVote("Veredito", "up", "ok"), SectionVote("Riscos", "down", "a: --- b")],
                comment="geral\n---\ndepois", text=TEXT, adapter="t", meta={"prompt_hash": "abc", "model": "m"})
    base.update(kw)
    return Feedback(**base)


def test_split_sections():
    assert [t for t, _ in split_sections(TEXT)] == ["Intro", "Veredito", "Riscos"]
    assert split_sections("") == [("Intro", "")]


def test_ida_e_volta(tmp_path):
    fb = _fb()
    path = save_feedback(fb, tmp_path)
    assert path.name.endswith("_caso-01.md")
    assert "verdict: reprovado" in path.read_text(encoding="utf-8")
    [back] = load_feedback(tmp_path)
    assert back.id == fb.id and back.tags == ["jargão técnico"] and back.meta == {"prompt_hash": "abc", "model": "m"}
    assert back.sections[1].comment == "a: --- b" and back.comment == fb.comment and back.text == TEXT


def test_verdict():
    assert _fb(sections=[SectionVote("A", "up")]).verdict == "aprovado"
    assert _fb(sections=[SectionVote("A", "up")], rating=2).verdict == "reprovado"


def test_arquivo_invalido_ignorado(tmp_path):
    (tmp_path / "x.md").write_text("lixo", encoding="utf-8")
    save_feedback(_fb(), tmp_path)
    assert len(load_feedback(tmp_path)) == 1
