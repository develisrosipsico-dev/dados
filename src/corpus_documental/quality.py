"""Qualidade documental separada da conservação de caracteres extraídos."""
from collections import Counter
import re

from .composition import body_metrics, visual_rows, paragraph_break, bounds
from .graphics import clip_bbox
from .hierarchy import layout_hints
from .layout import same_visual_line, font_size
from .provenance import validate_map


def assess_document(metadata, pages, structure, paragraphs, elements, events):
    blockers, review = [], []
    metrics = body_metrics(pages)
    blocks = {(p["page_index"], b["block_id"]): b for p in pages for b in p["blocks"] if b["type"] == "text"}
    by_page = {p["page_index"]: p for p in pages}
    by_node = {n["node_id"]: n for n in structure["nodes"]}
    by_paragraph = {p["paragraph_id"]: p for p in paragraphs}
    by_element = {e["element_id"]: e for e in elements}
    units = paragraphs+[e for e in elements if e.get("text_ownership") == "primary"]

    def issue(code, **context):
        blockers.append({"code": code, **context})

    def atom_lines(span):
        block = blocks.get((span["page_index"], span["block_id"]))
        if not block:
            return []
        offset, result = 0, []
        for i, line in enumerate(block["lines"]):
            end = offset+len(line["text"])+(i+1 < len(block["lines"]))
            if max(offset, span["block_char_start"]) < min(end, span["block_char_end"]):
                result.append({**line, "_source_start": offset, "_source_end": end})
            offset = end
        return result

    for unit in units:
        identifier = unit.get("paragraph_id", unit.get("element_id"))
        for error in validate_map(unit):
            issue(error, unit_id=identifier)
        for span in unit["source_spans"]:
            page = by_page.get(span["page_index"])
            if page and clip_bbox(span["bbox"], page["width"], page["height"]) != list(span["bbox"]):
                issue("text_geometry_outside_page", unit_id=identifier, page_index=span["page_index"])
            selected = atom_lines(span)
            if selected and any(abs(a-b) > .5 for a,b in zip(span["bbox"], bounds([l["bbox"] for l in selected]))):
                issue("source_geometry_mismatch", unit_id=identifier, page_index=span["page_index"])
    for paragraph in paragraphs:
        identifier = paragraph["paragraph_id"]
        if not paragraph["source_spans"]:
            issue("missing_paragraph_source", unit_id=identifier)
            continue
        words = re.findall(r"\b[^\W\d_]+\b", paragraph["text_clean"])
        for amendment in paragraph.get("editorial_amendments", []):
            start, end = amendment.get("text_clean_start"), amendment.get("text_clean_end")
            if (not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(paragraph["text_clean"])
                    or paragraph["text_clean"][start:end] != amendment.get("documentary_text")
                    or amendment.get("applied_to_text_clean") is not False
                    or amendment.get("status") != "proposed_unverified"
                    or not amendment.get("source_refs")):
                issue("editorial_amendment_provenance", unit_id=identifier,
                      amendment_id=amendment.get("amendment_id"))
        if len(words) == 1:
            review.append({"code": "single_word_paragraph", "unit_id": identifier, "text": paragraph["text_clean"]})
        # A mesma unidade não pode retroceder horizontalmente dentro de uma linha.
        physical = [(s["page_index"], l) for s in paragraph["source_spans"] for l in atom_lines(s)]
        for (p0, a), (p1, b) in zip(physical, physical[1:]):
            if p0 == p1 and same_visual_line(a, b) and b["bbox"][0] < a["bbox"][0]-.5:
                issue("visual_x_inversion", unit_id=identifier, page_index=p0)
            if p0 == p1 and b["bbox"][3] < a["bbox"][1] and abs(a["bbox"][0]-b["bbox"][0]) < metrics["size"]:
                issue("visual_y_inversion", unit_id=identifier, page_index=p0)
        # Um recuo de primeira linha após uma linha curta terminal é uma fronteira.
        for span in paragraph["source_spans"]:
            rows = visual_rows(atom_lines(span))
            for previous, current in zip(rows, rows[1:]):
                if paragraph_break(previous, current, metrics, rows) == "first_line_indent_after_short_terminal_line":
                    issue("merged_visual_paragraphs", unit_id=identifier, page_index=span["page_index"], native_start=current[0]["_source_start"])
        if re.match(r"^[a-zà-ÿ]", paragraph["text_clean"]):
            review.append({"code": "lowercase_paragraph_start", "unit_id": identifier})
        if paragraph["text_clean"].endswith(("-", ",")):
            review.append({"code": "open_paragraph_ending", "unit_id": identifier})
        raw_lines = [line for span in paragraph["source_spans"] for line in atom_lines(span)]
        raw_fonts = [s for line in raw_lines for s in line["spans"]]
        italic = sum(len(s["text"])*bool(s["flags"]&2) for s in raw_fonts)/max(1,sum(len(s["text"]) for s in raw_fonts))
        expected_quote = (italic > .6 and min(s["bbox"][0] for s in paragraph["source_spans"]) >= metrics["left"]+max(8,.8*metrics["size"])
                          and max(s["bbox"][2] for s in paragraph["source_spans"]) <= metrics["right"]-8
                          and font_size({"lines": raw_lines}) < .95*metrics["size"])
        if expected_quote and paragraph["classification"] != "block_quote":
            issue("unclassified_formatted_quote", unit_id=identifier)
        if paragraph["classification"] == "block_quote":
            if paragraph.get("quality_status") == "review_required":
                review.append({"code": "formatted_quote_requires_review", "unit_id": identifier})
            linked = by_element.get(paragraph.get("quote_element_id"))
            if not linked or linked["kind"] != "block_quote" or linked.get("paragraph_id") != identifier:
                issue("quote_link", unit_id=identifier)

    hints = layout_hints(pages, metrics)
    expected_chapters = [h for h in hints.values() if h["kind"] == "chapter" and not h.get("number_only")]
    chapters = [n for n in structure["nodes"] if n["kind"] == "chapter"]
    sections = [n for n in structure["nodes"] if n["kind"] == "section"]
    if expected_chapters and not chapters:
        issue("missing_chapter_hierarchy")
    if chapters and any(h["kind"] == "section" for h in hints.values()) and not sections:
        issue("missing_section_hierarchy")
    for paragraph in paragraphs:
        if expected_chapters and paragraph["chapter_id"] is None:
            issue("missing_paragraph_chapter", unit_id=paragraph["paragraph_id"])
        if sections and paragraph["chapter_id"] and paragraph["section_id"] is None:
            # Apenas páginas anteriores à primeira seção podem ter corpo sem seção.
            first = min((s["page_index"], s["bbox"][1]) for n in sections for s in n.get("source_spans", []))
            origin = paragraph["source_spans"][0]
            if (origin["page_index"], origin["bbox"][1]) >= first:
                issue("missing_paragraph_section", unit_id=paragraph["paragraph_id"])
        for key in ("chapter_id", "section_id"):
            node = by_node.get(paragraph[key])
            if node and node.get("source_spans"):
                first = node["source_spans"][0]
                origin = paragraph["source_spans"][0]
                if (first["page_index"], first["bbox"][1]) > (origin["page_index"], origin["bbox"][1]):
                    issue("hierarchy_after_paragraph", unit_id=paragraph["paragraph_id"], field=key)
    for node in structure["nodes"]:
        parent = by_node.get(node["parent_id"])
        if parent and parent.get("level") is not None and node.get("level", 0) <= parent["level"]:
            issue("hierarchy_level", node_id=node["node_id"])
        if node.get("quality_status") == "review_required":
            review.append({"code": "hierarchy_requires_review", "node_id": node["node_id"]})

    drawings = {(p["page_index"], i): d for p in pages for i, d in enumerate(p.get("drawings", []))}
    classified = Counter()
    for element in elements:
        if element["kind"] == "text_layer_render_mismatch":
            mismatch = element.get("text_layer_render_mismatch", {})
            if (element.get("classification_resolved_by") != "explicit_visual_text_layer_review"
                    or mismatch.get("status") != "confirmed"
                    or not mismatch.get("subtype")
                    or mismatch.get("text_layer_value") != element.get("text_raw")
                    or mismatch.get("included_in_reading_flow") is not False
                    or mismatch.get("reviewer_kind") != "automated_assistant"
                    or mismatch.get("human_reviewed") is not False
                    or not element.get("source_spans")):
                issue("text_layer_render_mismatch_provenance", element_id=element["element_id"])
        if element["kind"] in {"figure", "table"} and element.get("bbox") is not None:
            page = by_page.get(element.get("page_index"))
            if not page or clip_bbox(element["bbox"], page["width"], page["height"]) != list(element["bbox"]):
                issue("graphic_geometry_outside_page", element_id=element["element_id"])
        if "source_drawing_index" in element:
            key = element["page_index"], element["source_drawing_index"]
            classified[key] += 1
            raw = drawings.get(key)
            page = by_page.get(key[0])
            if raw is None or element.get("source_bbox") != list(raw["rect"]):
                issue("graphic_source_geometry", element_id=element["element_id"])
            elif element["bbox"] != clip_bbox(raw["rect"], page["width"], page["height"]):
                issue("graphic_visible_geometry", element_id=element["element_id"])
            if element["kind"] in {"layout_artifact", "separator_rule"}:
                if element.get("included_in_figure_structure") is not False or not element.get("classification_reason"):
                    issue("graphic_artifact_justification", element_id=element["element_id"])
            else:
                review.append({"code": "graphic_requires_review", "element_id": element["element_id"]})
        if element["kind"] == "note_call":
            target = by_element.get(element.get("target_note_id"))
            owner = by_paragraph.get(element.get("paragraph_id"))
            if not target or target["kind"] not in {"footnote", "endnote"} or not owner:
                issue("unresolved_note_call", element_id=element["element_id"])
            elif (element["element_id"] not in target.get("call_ids", []) or element["element_id"] not in owner.get("note_call_ids", [])
                  or target.get("note_number") != element.get("note_number")):
                issue("note_bidirectional_link", element_id=element["element_id"])
            for span in element["source_spans"]:
                block = blocks.get((span["page_index"], span["block_id"]))
                if not block or block["text_raw"][span["block_char_start"]:span["block_char_end"]] != element["text_raw"]:
                    issue("note_call_source", element_id=element["element_id"])
        pending_node = by_node.get(element.get("node_id"), {}).get("quality_status") == "review_required"
        resolved_classification = element.get("classification_resolved_by") in {
            "unique_superscript_note_link", "explicit_visual_text_layer_review"}
        if (element.get("quality_status") == "review_required" and not pending_node and not resolved_classification
                and element["kind"] not in {"block_quote", "note_call", "vector_graphic_candidate", "layout_artifact", "separator_rule"}):
            review.append({"code": "element_requires_review", "element_id": element["element_id"], "kind": element["kind"]})
    for key in drawings:
        if classified[key] != 1:
            issue("graphic_coverage", page_index=key[0], source_drawing_index=key[1])
    raw_calls = sum(bool(s["flags"] & 1 and s["text"].strip().isdigit()) for p in pages for b in p["blocks"]
                    for l in b.get("lines", []) for s in l["spans"])
    calls = sum(e["kind"] == "note_call" for e in elements)
    if raw_calls != calls:
        issue("note_call_coverage", expected=raw_calls, actual=calls)
    for event in events:
        if event["severity"] == "warning" and event["code"] in {"hyphenation_candidate", "editorial_amendment", "suspect_characters", "ocr_applied", "no_text", "page_continuation_ambiguous"}:
            review.append({"code": event["code"], "event_id": event["event_id"], "unit_id": event.get("unit_id")})
    return {"status": "blocked" if blockers else "review_required" if review else "approved",
            "blockers": blockers, "review_items": review,
            "metrics": {"chapters": len(chapters), "sections": len(sections),
                        "subsections": sum(n["kind"] == "subsection" for n in structure["nodes"]),
                        "block_quotes": sum(p["classification"] == "block_quote" for p in paragraphs),
                        "endnotes": sum(e["kind"] == "endnote" for e in elements), "note_calls": calls,
                        "drawings": len(drawings), "classified_drawings": len(classified),
                        "layout_artifacts": sum(e["kind"] == "layout_artifact" for e in elements),
                        "text_layer_render_mismatches": sum(e["kind"] == "text_layer_render_mismatch" for e in elements),
                        "single_word_paragraphs": sum(i["code"] == "single_word_paragraph" for i in review),
                        "blocking_documentary_errors": len(blockers), "pending_review_count": len(review)}}
