"""Qualidade da reconstrução: critérios independentes da cobertura bruta."""
from collections import Counter
from copy import deepcopy

from corpus_documental.models import stable_id
from corpus_documental.validation import validate


def assert_derived_id(paragraph, data):
    key = [(s["block_id"], s["block_char_start"], s["block_char_end"]) for s in paragraph["source_spans"]]
    expected = stable_id("para", data["metadata"]["corpus_version"], key)
    if paragraph["paragraph_id"] != expected:
        event = next(e for e in data["events"] if e["code"] == "paragraph_merge" and e["unit_id"] == paragraph["paragraph_id"])
        expected = stable_id("para", *event["predecessor_ids"])
    assert paragraph["paragraph_id"] == expected


def test_page_3_same_baseline_is_one_ordered_visual_paragraph(reviewed_story):
    data = reviewed_story["data"]
    relevant = [p for p in data["paragraphs"] if any(s["page_index"] == 2 for s in p["source_spans"])]
    found = [p for p in relevant if "Quando uma sociedade experimenta repetitivamente pseudoestórias" in p["text_clean"]]
    assert len(found) == 1
    assert found[0]["text_clean"].startswith("Estórias falsas e defeituosas")
    assert not any(p["text_clean"] in {"Quando", "uma", "sociedade", "experimenta"} for p in relevant)
    assert found[0]["source_spans"][0]["block_id"] == "p000002_b00002"
    assert_derived_id(found[0], data)


def test_page_3_revela_se_preserves_lexical_hyphen(reviewed_story):
    data = reviewed_story["data"]
    paragraph = next(p for p in data["paragraphs"] if "revela-\nse" in p["text_raw"])
    assert paragraph["text_clean"].count("revela-se") == 1
    assert "revela- se" not in paragraph["text_clean"]
    change = next(c for c in paragraph["transformations"]
                  if c["operation"] == "join_reviewed_hyphen_layout")
    start = paragraph["text_raw"].index("revela-\nse") + len("revela-")
    assert change["deleted_text_raw_ranges"] == [[start, start+1]]
    assert paragraph["text_raw"][start:start+1] == "\n"
    assert not any(e["code"] == "hyphenation_candidate" and e.get("unit_id") == paragraph["paragraph_id"]
                   for e in data["events"])


def test_page_13_long_quotation_is_one_visual_unit(reviewed_story):
    data = reviewed_story["data"]
    relevant = [p for p in data["paragraphs"] if any(s["page_index"] == 12 for s in p["source_spans"])]
    found = [p for p in relevant if "pega acidentalmente aquela-coisa" in p["text_clean"]]
    assert len(found) == 1
    quote = found[0]
    assert quote["classification"] == "block_quote"
    assert quote["text_clean"].startswith("Em uma confusão na hora de pegar a bagagem")
    assert quote["text_clean"].endswith("humanidade.")
    assert "nós-conhecemos" in quote["text_clean"]
    assert not any(p["text_clean"] == "acidentalmente" for p in relevant)
    assert_derived_id(quote, data)


def test_page_8_indented_paragraphs_are_separate_in_same_native_block(reviewed_story):
    data = reviewed_story["data"]
    first = next(p for p in data["paragraphs"] if p["text_clean"].startswith("Se escrevesse esse relatório"))
    second = next(p for p in data["paragraphs"] if p["text_clean"].startswith("A placa sobre a porta"))
    assert first["text_clean"] == "Se escrevesse esse relatório, teria perdido meu emprego."
    assert first["next_id"] == second["paragraph_id"] and second["previous_id"] == first["paragraph_id"]
    assert first["source_spans"][0]["block_id"] == second["source_spans"][0]["block_id"] == "p000007_b00005"
    assert first["source_spans"][-1]["block_char_end"] == second["source_spans"][0]["block_char_start"]
    assert_derived_id(first, data); assert_derived_id(second, data)


def test_hierarchy_and_chapter_number_have_source_evidence(reviewed_story):
    data = reviewed_story["data"]
    nodes = {n["node_id"]: n for n in data["structure"]["nodes"]}
    assert Counter(n["kind"] for n in nodes.values()) == {"work": 1, "chapter": 1, "section": 6, "subsection": 1}
    for paragraph in data["paragraphs"]:
        chain, parent = [], paragraph["parent_id"]
        while parent:
            node = nodes[parent]
            chain.append(node)
            parent = node["parent_id"]
        assert paragraph["chapter_id"] == next(n["node_id"] for n in chain if n["kind"] == "chapter")
        assert paragraph["section_id"] == next(n["node_id"] for n in chain if n["kind"] in {"section", "subsection"})
    number = next(e for e in data["elements"] if e["kind"] == "heading_number")
    assert number["text_clean"] == "1" and number["numbering_role"] == "chapter_number"
    assert nodes[number["chapter_id"]]["evidence"]["type"] == "chapter_number_and_display_title"
    assert all(s["printed_page_number"] is None for p in data["paragraphs"] for s in p["source_spans"])
    assert data["metadata"]["source_context"]["page_index_offset"] == 18
    assert data["metadata"]["selected_pages"] == list(range(18))


def test_quotes_endnotes_and_superscript_calls_remain_distinct(reviewed_story):
    data = reviewed_story["data"]
    elements = {e["element_id"]: e for e in data["elements"]}
    paragraphs = {p["paragraph_id"]: p for p in data["paragraphs"]}
    quotes = [p for p in paragraphs.values() if p["classification"] == "block_quote"]
    assert len(quotes) == 4
    for quote in quotes:
        assert quote["composition_evidence"]["italic_ratio"] > .6
        assert elements[quote["quote_element_id"]]["paragraph_id"] == quote["paragraph_id"]
    notes = [e for e in elements.values() if e["kind"] == "endnote"]
    calls = [e for e in elements.values() if e["kind"] == "note_call"]
    assert len(notes) == len(calls) == 6
    assert {e["note_number"] for e in calls} == set("123456")
    for call in calls:
        note, owner = elements[call["target_note_id"]], paragraphs[call["paragraph_id"]]
        assert note["note_number"] == call["note_number"]
        assert call["element_id"] in note["call_ids"] and call["element_id"] in owner["note_call_ids"]
        assert "".join(owner["text_clean"][a:b] for a,b in call["text_clean_ranges"]) == call["text_raw"]


def test_all_vector_boxes_are_classified_without_erasing_source(reviewed_story):
    data = reviewed_story["data"]
    graphics = [e for e in data["elements"] if "source_drawing_index" in e]
    assert len(graphics) == 19
    assert Counter(e["kind"] for e in graphics) == {"layout_artifact": 18, "separator_rule": 1}
    for element in graphics:
        page = data["pages"][element["page_index"]]
        assert element["source_bbox"] == page["drawings"][element["source_drawing_index"]]["rect"]
        a,b,c,d = element["bbox"]
        assert 0 <= a <= c <= 612 and 0 <= b <= d <= 792
        assert not element["included_in_figure_structure"]
        assert element["classification_reason"]


def test_relationship_order_and_validation_gate(reviewed_story):
    data, report = reviewed_story["data"], reviewed_story["report"]
    assert report["raw_integrity"]["status"] == "passed"
    assert report["checks"]["errors"] == [] and report["documentary_quality"]["blockers"] == []
    assert report["status"] == "review_required" and not report["chunking_gate"]["allowed"]
    assert not report["fidelity_certified"]
    assert report["metrics"]["single_word_paragraphs"] == 0
    for i, paragraph in enumerate(data["paragraphs"]):
        assert paragraph["paragraph_global_order"] == i+1
        assert paragraph["previous_id"] == (data["paragraphs"][i-1]["paragraph_id"] if i else None)
        assert paragraph["next_id"] == (data["paragraphs"][i+1]["paragraph_id"] if i+1 < len(data["paragraphs"]) else None)


def test_missing_hierarchy_blocks_even_formally_consistent_text(reviewed_story):
    data = deepcopy(reviewed_story["data"])
    root = data["structure"]["nodes"][0]
    data["structure"]["nodes"] = [root]
    for i, paragraph in enumerate(data["paragraphs"]):
        paragraph.update(parent_id=root["node_id"], chapter_id=None, section_id=None, paragraph_local_order=i+1)
    for element in data["elements"]:
        element["parent_id"] = root["node_id"]
    report = validate(**data)
    assert report["checks"]["errors"] == []
    assert report["raw_integrity"]["status"] == "passed"
    assert report["status"] == "blocked" and not report["chunking_gate"]["allowed"]
    assert "missing_chapter_hierarchy" in {e["code"] for e in report["documentary_quality"]["blockers"]}


def test_visual_baselines_and_hierarchy_advance_monotonically(reviewed_story):
    data = reviewed_story["data"]
    pages = {p["page_index"]: p for p in data["pages"]}
    previous_position = None
    for paragraph in data["paragraphs"]:
        first = paragraph["source_spans"][0]
        order = data["structure"]["page_reading_order"][str(first["page_index"])]
        rank = next(i for i,item in enumerate(order) if item["block_id"] == first["block_id"]
                    and item["block_char_start"] <= first["block_char_start"] < item["block_char_end"])
        position = first["page_index"], rank, first["block_char_start"]
        assert previous_position is None or position > previous_position
        previous_position = position
        previous_atom = None
        for span in paragraph["source_spans"]:
            block = next(b for b in pages[span["page_index"]]["blocks"] if b["block_id"] == span["block_id"])
            offset = 0
            for line in block["lines"]:
                end = offset+len(line["text"])+1
                if max(offset,span["block_char_start"]) < min(end,span["block_char_end"]):
                    atom = span["page_index"], line["bbox"]
                    if previous_atom and previous_atom[0] == atom[0]:
                        a,b = previous_atom[1], atom[1]
                        if abs(a[1]-b[1]) < 1 and abs(a[3]-b[3]) < 1:
                            assert b[0] >= a[0]
                        elif abs(a[0]-b[0]) < 1:
                            assert b[1] >= a[1]
                    previous_atom = atom
                offset = end
