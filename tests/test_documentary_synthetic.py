"""PDFs sintéticos e corrupções estruturais com bruto íntegro."""
from copy import deepcopy
from pathlib import Path

import pymupdf
import pytest

from corpus_documental.audit import Audit
from corpus_documental.cli import main
from corpus_documental.composition import make_segment
from corpus_documental.models import Config
from corpus_documental.normalization import normalize_document
from corpus_documental.structure import editorial_amendments
from corpus_documental.pipeline import process
from corpus_documental.storage import load_corpus
from corpus_documental.validation import validate


def test_synthetic_pdf_indentation_splits_a_single_native_block(tmp_path):
    source = tmp_path/"indent.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=612, height=792)
        page.insert_text((50, 100), "Capítulo 1 - Ensaio", fontsize=20)
        page.insert_text((50, 150), "1.1 Composição", fontsize=16)
        page.insert_text((72.5, 200), "Primeiro parágrafo termina aqui.", fontsize=15)
        page.insert_text((72.5, 218.75), "Outro parágrafo visual começa aqui e continua", fontsize=15)
        page.insert_text((50, 236), "na linha seguinte preservando o seu recuo original.", fontsize=15)
        pdf.save(source)
    out = tmp_path/"corpus"
    process(source, out, Config(pages=(0,)))
    data = load_corpus(out)
    assert [p["text_clean"] for p in data["paragraphs"]] == [
        "Primeiro parágrafo termina aqui.",
        "Outro parágrafo visual começa aqui e continua na linha seguinte preservando o seu recuo original."]
    first, second = data["paragraphs"]
    assert first["source_spans"][0]["block_id"] == second["source_spans"][0]["block_id"]


def test_synthetic_pdf_wide_justified_gaps_stay_inside_quote(tmp_path):
    source = tmp_path/"justified.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=612, height=792)
        page.insert_text((50, 100), "Capítulo 1 - Ensaio", fontsize=20)
        page.insert_text((50, 150), "1.1 Composição", fontsize=16)
        page.insert_textbox(pymupdf.Rect(50, 180, 550, 280),
            "Um corpo narrativo suficientemente longo estabelece a margem e o tamanho tipográfico principal do capítulo. Sua origem deve continuar localizável.", fontsize=15)
        for pos, text in [((70, 350), "Uma citação suficientemente longa estabelece a largura desta composição visual."),
                          ((70, 363), "pega "), ((122, 363), "acidentalmente "), ((220, 363), "aquela-coisa."),
                          ((70, 376), "A citação termina aqui.")]:
            page.insert_text(pos, text, fontname="tiit", fontsize=11.25)
        pdf.save(source)
    out = tmp_path/"corpus"
    report = process(source, out, Config(pages=(0,)))
    data = load_corpus(out)
    quote = next(p for p in data["paragraphs"] if "pega acidentalmente aquela-coisa" in p["text_clean"])
    assert quote["classification"] == "block_quote"
    assert quote["text_clean"].endswith("A citação termina aqui.")
    assert not any(p["text_clean"] == "acidentalmente" for p in data["paragraphs"])
    assert report["checks"]["errors"] == []


def test_visual_reordering_keeps_noncontiguous_raw_provenance():
    from test_reading_flow import line, document
    page, paragraphs, elements, events, report = document([
        line("Uma frase anterior ocupa a largura inteira da linha.", [77,100,535,116]),
        line("sociedade ", [268,117,331,133]),
        line("Quando ", [155,117,206,133]),
        line("uma ", [222,117,252,133]),
        line("experimenta.", [348,117,426,133]),
    ])
    assert len(paragraphs) == 1
    paragraph = paragraphs[0]
    assert paragraph["text_clean"].endswith("Quando uma sociedade experimenta.")
    assert len(paragraph["source_spans"]) > 1
    assert page["text_raw"].index("sociedade") < page["text_raw"].index("Quando")
    assert report["checks"]["errors"] == []
    assert report["documentary_quality"]["blockers"] == []


def test_quality_detects_merged_visual_paragraph_despite_raw_integrity(reviewed_story, tmp_path, monkeypatch):
    import corpus_documental.structure as module
    original = module.paragraph_segments

    def legacy_segments(block, metrics):
        segments, decisions = original(block, metrics)
        if any(d["reason"] == "first_line_indent_after_short_terminal_line" for d in decisions):
            return [make_segment(block, block["lines"])], []
        return segments, decisions

    monkeypatch.setattr(module, "paragraph_segments", legacy_segments)
    report = process(reviewed_story["source"], tmp_path/"legacy", reviewed_story["config"],
                     raw_pages_path=reviewed_story["previous"]/"pages_raw.jsonl")
    assert report["raw_integrity"]["status"] == "passed" and report["checks"]["errors"] == []
    assert report["status"] == "blocked"
    assert "merged_visual_paragraphs" in {e["code"] for e in report["documentary_quality"]["blockers"]}


@pytest.mark.parametrize("mutation,code", [("graphic", "graphic_visible_geometry"), ("call", "unresolved_note_call"), ("map", "normalization_map_source"), ("quote", "unclassified_formatted_quote"), ("bbox", "source_geometry_mismatch")])
def test_documentary_corruption_closes_gate_with_preserved_raw(reviewed_story, mutation, code):
    data = deepcopy(reviewed_story["data"])
    if mutation == "graphic":
        graphic = next(e for e in data["elements"] if e["kind"] == "layout_artifact")
        graphic["bbox"][3] = 9999
    elif mutation == "call":
        next(e for e in data["elements"] if e["kind"] == "note_call")["target_note_id"] = None
    elif mutation == "map":
        data["paragraphs"][0]["normalization_map"][0]["source_refs"][0]["char_start"] += 1
    elif mutation == "quote":
        quote = next(p for p in data["paragraphs"] if p["classification"] == "block_quote")
        quote["classification"] = "paragraph"
        quote["composition_evidence"] = {}
    else:
        data["paragraphs"][0]["source_spans"][0]["bbox"][0] += 10
    report = validate(**data)
    assert report["raw_integrity"]["status"] == "passed"
    assert report["status"] == "blocked" and not report["chunking_gate"]["allowed"]
    assert code in {e["code"] for e in report["documentary_quality"]["blockers"]}


def test_hyphen_requires_corroboration_and_preserves_compound():
    config, audit = Config(pages=(0,), join_hyphens=True), Audit()
    text, _, _ = normalize_document("hifeni-\nzação", config, audit, "p")
    assert text == "hifeni- zação"
    joined, changes, _ = normalize_document("hifeni-\nzação", config, audit, "q", word_evidence={"hifenização"})
    assert joined == "hifenização" and changes
    compound, _, _ = normalize_document("aquela-coisa-\nconhecida", config, audit, "r", word_evidence={"aquela-coisa-conhecida"})
    assert compound == "aquela-coisa-conhecida"
    assert any(e["code"] == "hyphenation_candidate" and not e["applied"] for e in audit.events)


def test_enclitic_line_break_preserves_lexical_hyphen_and_provenance():
    raw = "O efeito final revela-\nse grotesco."
    audit = Audit()
    clean, changes, normalization_map = normalize_document(
        raw, Config(pages=(0,), reviewed_line_hyphens=("revela-se",)), audit, "para_revela_se")

    assert raw == "O efeito final revela-\nse grotesco."
    assert clean == "O efeito final revela-se grotesco."
    assert [change["operation"] for change in changes] == ["join_reviewed_hyphen_layout"]
    assert changes[0]["deleted_text_raw_ranges"] == [[22, 23]]
    assert any(event["code"] == "reviewed_hyphen_preserved" for event in audit.events)
    assert not any(event["code"] == "hyphenation_candidate" for event in audit.events)
    assert normalization_map[-1]["text_raw_start"] == 23
    assert normalization_map[-1]["text_raw_end"] == len(raw)

    ambiguous, _, _ = normalize_document("A palavra anali-\nse permanece ambígua.",
                                         Config(pages=(0,)), Audit(), "ambigua")
    assert ambiguous == "A palavra anali- se permanece ambígua."


def test_editorial_amendment_stays_separate_from_documentary_text():
    raw = "são pré-\nrequisi-tos para a criatividade"
    span = {"page_index": 0, "block_id": "b", "block_char_start": 0,
            "block_char_end": len(raw), "char_start": 100, "char_end": 100+len(raw),
            "bbox": [10, 10, 200, 30], "pdf_page_label": None, "printed_page_number": None}
    config = Config(pages=(0,), reviewed_line_hyphens=("pré-requisi-tos",),
                    editorial_amendments=("pré-requisi-tos=pré-requisitos",))
    clean, changes, mapping = normalize_document(raw, config, Audit(), "p", [span])
    amendments = editorial_amendments(clean, "p", mapping, [span], config.editorial_amendments)

    assert clean == "são pré-requisi-tos para a criatividade"
    assert changes[0]["operation"] == "join_reviewed_hyphen_layout"
    assert changes[0]["deleted_text_raw_ranges"] == [[8, 9]]
    assert len(amendments) == 1
    amendment = amendments[0]
    assert amendment["documentary_text"] == "pré-requisi-tos"
    assert amendment["proposed_text"] == "pré-requisitos"
    assert amendment["status"] == "proposed_unverified"
    assert amendment["applied_to_text_clean"] is False
    assert len(amendment["source_refs"]) == 2


def test_reviewed_text_layer_mismatch_requires_explicit_source_block(tmp_path):
    source = tmp_path / "mismatch.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=612, height=792)
        page.insert_text((50, 100), "Um parágrafo completo preservado no fluxo documental.", fontsize=11)
        page.insert_text((300, 740), "Ó", fontsize=21)
        pdf.save(source)
    output = tmp_path / "reviewed-mismatch"
    process(source, output, Config(
        pages=(0,), reviewed_text_layer_mismatches=("p000000_b00001=clipped_text_object",)))
    data = load_corpus(output)
    mismatch = next(e for e in data["elements"] if e["kind"] == "text_layer_render_mismatch")
    assert mismatch["text_raw"] == "Ó"
    assert mismatch["text_layer_render_mismatch"]["subtype"] == "clipped_text_object"
    assert mismatch["text_layer_render_mismatch"]["included_in_reading_flow"] is False
    assert mismatch["quality_status"] == "automated"
    assert not any(any(s["block_id"] == "p000000_b00001" for s in p["source_spans"])
                   for p in data["paragraphs"])

    with pytest.raises(ValueError, match="BLOCO=SUBTIPO"):
        Config(pages=(0,), reviewed_text_layer_mismatches=("todos",)).validate(1)


def test_gate_approved_only_when_implemented_checks_have_no_pending_cases(tmp_path, capsys):
    source = tmp_path/"simple.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((50,100), "Um parágrafo simples e completo.", fontsize=11)
        pdf.save(source)
    output = tmp_path/"simple"
    report = process(source, output, Config(pages=(0,)))
    assert report["status"] == "approved" and report["chunking_gate"]["allowed"]
    assert not report["fidelity_certified"]
    assert main(["check-ready", str(output)]) == 0


def test_gate_refuses_real_chapter_pending_review(reviewed_story, capsys):
    assert main(["check-ready", str(reviewed_story["output"])]) == 2
    assert '"allowed": false' in capsys.readouterr().out
