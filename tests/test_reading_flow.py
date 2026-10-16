"""Regressões de fluxo usando geometria sintética, sem o livro nos testes."""

from copy import deepcopy

import pytest

from corpus_documental.audit import Audit
from corpus_documental.models import Config
from corpus_documental.normalization import normalize
from corpus_documental.structure import build_structure, sentences
from corpus_documental.validation import validate


def line(text, bbox, *, size=15, font="Serif"):
    return {"text": text, "bbox": bbox, "direction": [1.0, 0.0],
            "spans": [{"text": text, "bbox": bbox, "size": size,
                       "font": font, "flags": 0, "chars": []}]}


def document(lines):
    """Um objeto PDF pode conter linhas da mesma baseline ou de colunas."""
    raw = "\n".join(item["text"] for item in lines)
    boxes = [item["bbox"] for item in lines]
    block = {"block_id": "p000000_b00000", "type": "text", "lines": lines,
             "text_raw": raw, "char_start": 0, "char_end": len(raw),
             "bbox": [min(b[0] for b in boxes), min(b[1] for b in boxes),
                      max(b[2] for b in boxes), max(b[3] for b in boxes)]}
    page = {"page_index": 0, "width": 612, "height": 792, "status": "ok",
            "method": "native", "pdf_page_label": None, "blocks": [block],
            "text_raw": raw, "drawings": [], "tables": []}
    metadata = {"document_id": "doc_synthetic", "page_count": 1,
                "selected_pages": [0], "out_of_scope_pages": [],
                "bibliographic": {"title": "Ensaio sintético"}}
    audit = Audit()
    structure, paragraphs, elements = build_structure(
        [page], metadata, "version_synthetic", Config(pages=(0,)), audit)
    report = validate(metadata, [page], structure, paragraphs, elements, audit.events)
    return page, paragraphs, elements, audit.events, report


def assert_preserved(page, paragraphs, elements, events, report, *, expected_errors=()):
    """Cada caractere nativo continua com um único proprietário rastreável."""
    assert {error["code"] for error in report["checks"]["errors"]} == set(expected_errors)
    assert report["checks"]["raw_reconstruction_matches"]
    assert report["metrics"]["block_coverage_ratio"] == 1
    units = paragraphs + [item for item in elements
                          if item.get("text_ownership") == "primary"]
    spans = []
    for unit in units:
        pieces = []
        for span in unit["source_spans"]:
            assert span["block_id"] == page["blocks"][0]["block_id"]
            start, end = span["block_char_start"], span["block_char_end"]
            assert (span["char_start"], span["char_end"]) == (start, end)
            pieces.append(page["text_raw"][start:end])
            spans.append((start, end))
        assert unit["text_raw"] == "\n".join(pieces)
        text = unit["text_raw"]
        for change in unit["transformations"]:
            assert change["before"] == text
            assert any(event["code"] == "normalization"
                       and event.get("unit_id") == unit.get("paragraph_id", unit.get("element_id"))
                       and event.get("before") == change["before"]
                       and event.get("after") == change["after"] for event in events)
            text = change["after"]
        assert text == unit["text_clean"]
    cursor = 0
    for start, end in sorted(spans):
        assert start == cursor
        cursor = end
    assert cursor == len(page["text_raw"])


@pytest.mark.parametrize("inline_style", [False, True], ids=["justified", "inline_typography"])
def test_justified_words_stay_in_paragraph_before_their_continuation(inline_style):
    # Reprodução da forma física do defeito: o extrator emite cada palavra
    # justificada como uma `line`, com ~16 pt entre suas caixas na mesma linha.
    lines = [
        line("Uma cultura precisa de uma narrativa honesta e", [77, 420, 535, 437]),
        line("poderosa. ", [77, 437.38, 138.64, 453.99]),
        line("Quando ", [154.84, 437.38, 206.08, 453.99],
             size=18 if inline_style else 15, font="Serif-Bold" if inline_style else "Serif"),
        line("uma ", [222.28, 437.38, 251.86, 453.99]),
        line("sociedade ", [268.06, 437.38, 330.95, 453.99]),
        line("experimenta ", [347.14, 437.38, 425.04, 453.99]),
        line("repetitivamente", [441.22, 437.38, 534.53, 453.99]),
        line("pseudoestórias ocas, ela se degenera.", [77, 454.63, 535, 471.24]),
    ]
    page, paragraphs, elements, events, report = document(lines)
    assert len(paragraphs) == 1
    paragraph = paragraphs[0]
    assert paragraph["text_clean"] == (
        "Uma cultura precisa de uma narrativa honesta e poderosa. "
        "Quando uma sociedade experimenta repetitivamente pseudoestórias ocas, ela se degenera.")
    assert paragraph["text_raw"] == page["text_raw"]
    assert paragraph["source_spans"][0]["block_char_start"] == 0
    assert paragraph["source_spans"][-1]["block_char_end"] == len(page["text_raw"])
    assert_preserved(page, paragraphs, elements, events, report)


@pytest.mark.parametrize("right_x", [345, 257], ids=["wide_gutter", "narrow_persistent_gutter"])
def test_separate_columns_on_same_baseline_keep_their_reading_order(right_x):
    # Ordem nativa alternada: a faixa branca persiste em duas linhas por coluna.
    # Mesmo 17 pt de gutter não equivale a uma palavra espaçada do corpo corrido.
    page, paragraphs, elements, events, report = document([
        line("Esquerda: primeira afirmação.", [50, 100, 240, 112], size=11),
        line("Direita: primeira afirmação.", [right_x, 100, right_x + 190, 112], size=11),
        line("Esquerda: segunda afirmação.", [50, 140, 240, 152], size=11),
        line("Direita: segunda afirmação.", [right_x, 140, right_x + 190, 152], size=11),
    ])
    assert [p["text_clean"] for p in paragraphs] == [
        "Esquerda: primeira afirmação.", "Esquerda: segunda afirmação.",
        "Direita: primeira afirmação.", "Direita: segunda afirmação."]
    assert_preserved(page, paragraphs, elements, events, report)


def test_independent_list_items_are_not_joined_by_same_baseline():
    # Um gap pequeno isoladamente não basta para unir dois marcadores explícitos.
    page, paragraphs, elements, events, report = document([
        line("- Primeiro item independente", [77, 100, 235, 112], size=11),
        line("- Segundo item independente", [252, 100, 420, 112], size=11),
    ])
    assert paragraphs == []
    assert [e["text_clean"] for e in elements if e["kind"] == "list_item"] == [
        "- Primeiro item independente", "- Segundo item independente"]
    assert_preserved(page, paragraphs, elements, events, report)


@pytest.mark.parametrize("reordered", [False, True], ids=["split_only", "split_and_reordered"])
def test_validation_rejects_legacy_inline_split_despite_complete_coverage(reordered):
    lines = [
        line("Quando ", [77, 100, 125, 116]),
        line("uma ", [142, 100, 170, 116]),
        line("sociedade ", [187, 100, 250, 116]),
        line("experimenta repetitivamente", [267, 100, 460, 116]),
        line("pseudoestórias ocas.", [77, 117, 460, 133]),
    ]
    page, paragraphs, elements, _, original_report = document(lines)
    assert original_report["checks"]["errors"] == []
    assert len(paragraphs) == 1
    original = paragraphs[0]
    audit, legacy, offset = Audit(), [], 0
    for index, item in enumerate(lines):
        # Simula o resultado antigo preservando cada caractere, inclusive o
        # separador nativo. Somente a fronteira de parágrafo está indevida.
        end = offset + len(item["text"]) + (index < len(lines)-1)
        record = deepcopy(original)
        identity = f"para_legacy_{index}"
        record["paragraph_id"] = identity
        record["text_raw"] = page["text_raw"][offset:end]
        record["source_spans"] = [{**original["source_spans"][0], "bbox": item["bbox"],
                                   "block_char_start": offset, "block_char_end": end,
                                   "char_start": offset, "char_end": end}]
        record["text_clean"], record["transformations"] = normalize(
            record["text_raw"], Config(pages=(0,)), audit, identity)
        record["sentences"] = sentences(record["text_clean"], identity)
        legacy.append(record)
        offset = end
    if reordered:
        # Faz a continuação preceder as palavras, com a lista de ordem e todos
        # os links também consistentes: a validação precisa usar a geometria.
        legacy = [legacy[3], *legacy[:3], legacy[4]]
    for index, record in enumerate(legacy):
        record.update(paragraph_global_order=index+1, paragraph_local_order=index+1,
                      previous_id=legacy[index-1]["paragraph_id"] if index else None,
                      next_id=legacy[index+1]["paragraph_id"] if index+1 < len(legacy) else None)
    page["reading_order"] = [{key: span[key] for key in
                              ("block_id", "block_char_start", "block_char_end")}
                             for record in legacy for span in record["source_spans"]]
    metadata = {"document_id": "doc_synthetic", "selected_pages": [0], "out_of_scope_pages": []}
    structure = {"nodes": [{"node_id": "doc_synthetic", "parent_id": None, "kind": "work"}]}
    report = validate(metadata, [page], structure, legacy, elements, audit.events)
    expected_errors = {"inline_paragraph_split"}
    if reordered:
        expected_errors.add("inline_reading_order")
    assert report["status"] == "blocked"
    assert_preserved(page, legacy, elements, audit.events, report, expected_errors=expected_errors)
