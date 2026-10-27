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


def test_mesmo_segundo_nao_sobrescreve(tmp_path):
    a, b = save_feedback(_fb(), tmp_path), save_feedback(_fb(comment="outro"), tmp_path)
    assert a != b and len(load_feedback(tmp_path)) == 2
    assert {f.comment for f in load_feedback(tmp_path)} == {"geral\n---\ndepois", "outro"}


def test_comentario_com_cabecalhos_do_corpo(tmp_path):
    save_feedback(_fb(comment="x\n\n## Texto avaliado\n\ny"), tmp_path)
    [back] = load_feedback(tmp_path)
    assert back.comment == "x\n\n## Texto avaliado\n\ny" and back.text == TEXT


def test_formato_antigo_ainda_le(tmp_path):
    old = ("---\ncase: c\nrating: 3\n---\n\n# Feedback id\n\n## Comentário geral\n\nvelho\n\n"
           "## Texto avaliado\n\ntexto\n")
    (tmp_path / "a.md").write_text(old, encoding="utf-8")
    [fb] = load_feedback(tmp_path)
    assert fb.comment == "velho" and fb.text == "texto"


def test_prompt_guardado_uma_vez_e_diff_no_summary(tmp_path):
    from llmfeedback.cli import summary

    for i, (h, text) in enumerate([("v1", "Seja breve.\nSem jargão."), ("v2", "Seja breve.\nSem jargão.\nCite números.")]):
        fb = Feedback(case="c", rating=4, text="t", meta={"prompt_hash": h, "prompt": text},
                      created_at=f"2026-01-0{i + 1}T00:00:00+00:00", id=f"fb{i}")
        save_feedback(fb, tmp_path)
        save_feedback(Feedback(case="c", rating=5, text="t", meta={"prompt_hash": h, "prompt": "outro"}, id=f"x{i}",
                               created_at=f"2026-01-0{i + 1}T00:00:01+00:00"), tmp_path)
    assert (tmp_path / "prompts" / "v1.md").read_text(encoding="utf-8") == "Seja breve.\nSem jargão."  # 1ª versão vence
    assert all("prompt" not in f.meta for f in load_feedback(tmp_path))
    out = summary(tmp_path)
    assert "mudança de prompt v1 → v2" in out and "+Cite números." in out
