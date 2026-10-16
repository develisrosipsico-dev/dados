import copy
from pathlib import Path

import pymupdf
import pytest

from corpus_documental.audit import Audit
from corpus_documental.cli import main, parse_pages
from corpus_documental.models import Config
from corpus_documental.normalization import normalize, normalize_document
from corpus_documental.pipeline import process
from corpus_documental.storage import load_corpus
from corpus_documental.validation import validate


def run(book, tmp_path, **options):
    output = tmp_path/"corpus"
    report = process(book, output, Config(pages=(0, 1), **options))
    return output, load_corpus(output), report


def test_artifacts_integrity_and_scope(book, tmp_path):
    original = book.read_bytes()
    output, data, report = run(book, tmp_path)
    assert book.read_bytes() == original == (output/"original.pdf").read_bytes()
    assert {p.name for p in output.iterdir()} == {
        "original.pdf", "pages_raw.jsonl", "structure.json", "paragraphs.jsonl",
        "elements.jsonl", "metadata.json", "processing_log.jsonl", "validation_report.json"}
    assert report["checks"]["errors"] == []
    assert report["metrics"]["pages_recorded"] == 2
    assert report["metrics"]["block_coverage_ratio"] == 1
    assert report["checks"]["raw_reconstruction_matches"]
    assert data["metadata"]["out_of_scope_pages"] == [2]
    assert data["metadata"]["bibliographic"]["edition"] is None


def test_headings_notes_margins_and_references_are_separate(book, tmp_path):
    _, data, report = run(book, tmp_path)
    body = "\n".join(p["text_raw"] for p in data["paragraphs"])
    for text in ("Capítulo", "Fundamentos", "Nota explicativa", "CADERNO", "SILVA"):
        assert text not in body
    kinds = {e["kind"] for e in data["elements"]}
    assert {"chapter", "section", "footnote", "header", "footer", "reference"} <= kinds
    for p in data["paragraphs"]:
        assert p["chapter_id"] and p["section_id"]
    assert report["status"] == "review_required"


def test_cross_page_join_is_explicit_and_traceable(book, tmp_path):
    _, data, report = run(book, tmp_path, merge_pages=True)
    combined = [p for p in data["paragraphs"] if len(p["source_spans"]) > 1]
    assert len(combined) == 1
    p = combined[0]
    assert [s["page_index"] for s in p["source_spans"]] == [0, 1]
    assert "continua na página" in p["text_clean"]
    assert p["quality_status"] == "review_required"
    assert report["checks"]["errors"] == []
    assert report["metrics"]["cross_page_paragraphs"] == 1
    assert any(e["code"] == "paragraph_merge" for e in data["events"])


def test_default_does_not_silently_merge(book, tmp_path):
    _, data, _ = run(book, tmp_path)
    assert not any(len(p["source_spans"]) > 1 for p in data["paragraphs"])
    assert any(e["code"] == "page_continuation_candidate" and not e["applied"] for e in data["events"])


def test_reproducibility_and_versioning(book, tmp_path):
    a, b = tmp_path/"a", tmp_path/"b"
    process(book, a, Config(pages=(0, 1)))
    process(book, b, Config(pages=(0, 1)))
    assert {p.name:p.read_bytes() for p in a.iterdir()} == {p.name:p.read_bytes() for p in b.iterdir()}
    c = tmp_path/"c"
    process(book, c, Config(pages=(0, 1), join_hyphens=True))
    assert load_corpus(a)["metadata"]["corpus_version"] != load_corpus(c)["metadata"]["corpus_version"]


def test_no_overwrite_or_invalid_range(book, tmp_path):
    output = tmp_path/"exists"
    output.mkdir()
    with pytest.raises(FileExistsError):
        process(book, output, Config(pages=(0,)))
    with pytest.raises(ValueError):
        process(book, tmp_path/"invalid", Config(pages=(100,)))
    assert not (tmp_path/"invalid").exists()


def test_controlled_normalization_and_suspect_characters():
    audit = Audit()
    raw = "  hifeni-\nzação e ac\u0327a\u0303o\ufffd  "
    text, changes = normalize(raw, Config(pages=(0,)), audit, "p1")
    assert "hifeni- zação" in text and "ação\ufffd" in text
    assert changes[0]["before"] == raw
    for a, b in zip(changes, changes[1:]):
        assert a["after"] == b["before"]
    unsafe, _ = normalize(raw, Config(pages=(0,), join_hyphens=True), audit, "p2")
    assert "hifeni- zação" in unsafe
    joined, _, _ = normalize_document(raw, Config(pages=(0,), join_hyphens=True), audit, "p3", word_evidence={"hifenização"})
    assert "hifenização" in joined
    assert {e["code"] for e in audit.events} >= {"suspect_characters", "hyphenation_candidate", "normalization"}


@pytest.mark.parametrize("mutation,code", [
    ("raw", "raw_text_changed"), ("clean", "unjustified_clean_text"),
    ("duplicate", "duplicate_identifiers"), ("missing", "block_coverage"),
    ("link", "next_link"), ("offset", "page_offsets"), ("audit", "missing_transformation_audit"),
    ("order", "paragraph_order"), ("classification", "unclassified_text"),
])
def test_validation_rejects_documentary_corruption(book, tmp_path, mutation, code):
    _, data, _ = run(book, tmp_path)
    p = data["paragraphs"][0]
    if mutation == "raw":
        p["text_raw"] += " perdido"
    elif mutation == "clean":
        p["text_clean"] += " inventado"
    elif mutation == "duplicate":
        data["paragraphs"].append(copy.deepcopy(p))
    elif mutation == "missing":
        data["paragraphs"].pop(0)
    elif mutation == "link":
        p["next_id"] = "inexistente"
    elif mutation == "offset":
        p["source_spans"][0]["char_start"] += 1
    elif mutation == "audit":
        data["events"] = [e for e in data["events"] if e["code"] != "normalization"]
    elif mutation == "order":
        p["paragraph_global_order"] = 10
    elif mutation == "classification":
        p["classification"] = ""
    report = validate(**data)
    assert report["status"] == "blocked"
    assert code in {e["code"] for e in report["checks"]["errors"]}


def test_columns_override_native_object_order(tmp_path):
    source = tmp_path/"columns.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=600, height=800)
        for xy, text in [((330, 100), "Direita primeiro."), ((50, 100), "Esquerda primeiro."),
                         ((330, 180), "Direita segundo."), ((50, 180), "Esquerda segundo.")]:
            page.insert_text(xy, text, fontsize=11)
        pdf.save(source)
    output = tmp_path/"columns"
    process(source, output, Config(pages=(0,)))
    data = load_corpus(output)
    assert [p["text_clean"] for p in data["paragraphs"]] == [
        "Esquerda primeiro.", "Esquerda segundo.", "Direita primeiro.", "Direita segundo."]
    assert any(e["code"] == "reading_order" for e in data["events"])


def test_failed_ocr_is_explicit_and_keeps_native(tmp_path, monkeypatch):
    source = tmp_path/"scan.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100), False)
        pix.clear_with(255)
        page.insert_image(page.rect, stream=pix.tobytes("png"))
        pdf.save(source)

    def fail(*args, **kwargs):
        raise RuntimeError("language data unavailable")

    monkeypatch.setattr(pymupdf.Page, "get_textpage_ocr", fail)
    output = tmp_path/"scan"
    report = process(source, output, Config(pages=(0,)))
    data = load_corpus(output)
    assert data["pages"][0]["native_extraction"]["blocks"]
    assert any(e["code"] == "ocr_failed" for e in data["events"])
    assert report["status"] == "blocked"
    assert "ocr_failed" in {e["code"] for e in report["checks"]["processing_errors"]}


def test_page_failure_is_preserved_and_reported(book, tmp_path, monkeypatch):
    original = pymupdf.Page.get_text

    def fail_one(self, *args, **kwargs):
        if self.number == 1:
            raise RuntimeError("simulated broken page")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(pymupdf.Page, "get_text", fail_one)
    _, data, report = run(book, tmp_path)
    assert len(data["pages"]) == 2 and data["pages"][1]["status"] == "failed"
    assert report["metrics"]["pages_failed"] == 1
    assert report["status"] == "blocked"


def test_cli_requires_scope_and_revalidates_source(book, tmp_path, capsys):
    assert parse_pages("2,4-6") == (1, 3, 4, 5)
    with pytest.raises(SystemExit):
        main(["process", str(book), "--output", str(tmp_path/"x")])
    output, _, _ = run(book, tmp_path)
    assert main(["validate", str(output)]) == 0
    (output/"original.pdf").write_bytes(b"tampered")
    assert main(["validate", str(output)]) == 2
    assert "source_hash_mismatch" in capsys.readouterr().out


def test_cli_process_emits_valid_json(book, tmp_path, capsys):
    import json
    assert main(["process", str(book), "--pages", "1-2", "--output", str(tmp_path/"cli")]) == 0
    assert json.loads(capsys.readouterr().out)["metrics"]["paragraphs"] > 0


def test_real_ocr_when_model_available(tmp_path, monkeypatch):
    local_models = Path(__file__).resolve().parents[1]/".local"/"tessdata"
    if (local_models/"por.traineddata").is_file():
        monkeypatch.setenv("TESSDATA_PREFIX", str(local_models))
        language = "por"
    else:
        try:
            models = Path(pymupdf.get_tessdata())
        except RuntimeError:
            pytest.skip("OCR opcional: execute bash scripts/setup.sh para instalar o modelo.")
        if not (models/"eng.traineddata").is_file():
            pytest.skip("Modelo OCR indisponível; execute bash scripts/setup.sh.")
        language = "eng"
    source = tmp_path/"raster.pdf"
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((50, 100), "Este documento preserva a origem de cada parágrafo.", fontsize=18)
        image = page.get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes("png")
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_image(page.rect, stream=image)
        document.save(source)
    output = tmp_path/"ocr"
    report = process(source, output, Config(pages=(0,), ocr_language=language))
    data = load_corpus(output)
    assert data["pages"][0]["method"] == "ocr"
    assert "documento" in data["pages"][0]["text_raw"]
    assert data["metadata"]["processing"]["ocr_model_sha256"][language]
    assert data["pages"][0]["native_extraction"]["blocks"]
    assert report["checks"]["errors"] == []
    assert report["status"] == "review_required"


def test_tables_lists_captions_and_images_preserve_text(tmp_path):
    source = tmp_path/"elements.pdf"
    with pymupdf.open() as document:
        page = document.new_page()
        for y in (150, 190, 230):
            page.draw_line((50, y), (350, y))
        for x in (50, 200, 350):
            page.draw_line((x, 150), (x, 230))
        for xy, text in [((60, 175), "Coluna A"), ((210, 175), "Coluna B"),
                         ((60, 215), "Valor A"), ((210, 215), "Valor B"),
                         ((50, 300), "- Item enumerado"), ((50, 450), "Figura 1. Imagem de teste")]:
            page.insert_text(xy, text, fontsize=11)
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10), False)
        pix.clear_with(180)
        page.insert_image(pymupdf.Rect(50, 340, 150, 420), stream=pix.tobytes("png"))
        document.save(source)
    output = tmp_path/"elements"
    report = process(source, output, Config(pages=(0,)))
    data = load_corpus(output)
    kinds = {e["kind"] for e in data["elements"]}
    assert {"table", "table_text", "list_item", "caption", "figure"} <= kinds
    assert all(e["related_table_ids"] for e in data["elements"] if e["kind"] == "table_text")
    assert report["checks"]["errors"] == []
    assert report["metrics"]["block_coverage_ratio"] == 1


def test_ambiguous_typographic_heading_is_not_invented_as_chapter(tmp_path):
    source = tmp_path/"ambiguous.pdf"
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((50, 100), "Um título sem numeração", fontsize=20)
        page.insert_text((50, 200), "Este parágrafo tem corpo comum e deve permanecer no fluxo documental original.", fontsize=11)
        document.save(source)
    output = tmp_path/"ambiguous"
    process(source, output, Config(pages=(0,)))
    data = load_corpus(output)
    assert len(data["structure"]["nodes"]) == 1
    title = next(e for e in data["elements"] if e["kind"] == "title_candidate")
    assert title["quality_status"] == "review_required"
    assert data["paragraphs"][0]["chapter_id"] is None


def test_bookmarks_link_split_title_and_keep_context_outside_scope(tmp_path):
    source = tmp_path/"outline.pdf"
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((50, 100), "PARTE 1", fontsize=20)
        page = document.new_page()
        page.insert_text((280, 100), "1", fontsize=23)
        page.insert_text((50, 150), "TÍTULO DOCUMENTAL", fontsize=23)
        page.insert_text((50, 210), "PRIMEIRA DIVISÃO", fontsize=16)
        page.insert_text((50, 260), "Este corpo possui mais de oitenta caracteres para estabelecer a tipografia de referência do capítulo.", fontsize=11)
        page.insert_text((50, 350), "SEGUNDA DIVISÃO", fontsize=16)
        page.insert_text((50, 400), "Outro parágrafo completo para preservar a relação entre o texto e a seção que lhe corresponde.", fontsize=11)
        page.insert_text((300, 740), "Ó", fontsize=16)
        document.set_toc([[1, "Parte 1: Conjunto", 1], [2, "1. Título documental", 2]])
        document.save(source)
    output = tmp_path/"outline"
    report = process(source, output, Config(pages=(1,)))
    data = load_corpus(output)
    nodes = data["structure"]["nodes"]
    assert [n["kind"] for n in nodes] == ["work", "part", "chapter", "section", "section"]
    assert nodes[1]["evidence"]["outside_selected_pages"]
    assert nodes[2]["evidence"]["type"] == "pdf_bookmark"
    assert all(n["quality_status"] == "review_required" for n in nodes[3:])
    assert len(data["paragraphs"]) == 2
    assert any(e["kind"] == "marginal_glyph_candidate" for e in data["elements"])
    assert report["checks"]["errors"] == []


def test_bibliographic_evidence_must_match_source(book, tmp_path):
    evidence = {"title": {"value": "Ensaio", "page_index": 0, "quote": "Capítulo 1 - Ensaio"}}
    output = tmp_path/"evidence"
    process(book, output, Config(pages=(0,), bibliographic_evidence=evidence))
    metadata = load_corpus(output)["metadata"]
    assert metadata["bibliographic"]["title"] == "Ensaio"
    assert metadata["bibliographic_evidence"]["title"]["char_start"] >= 0
    evidence["title"]["value"] = "Inventado"
    with pytest.raises(ValueError, match="não conferida"):
        process(book, tmp_path/"bad-evidence", Config(pages=(0,), bibliographic_evidence=evidence))
