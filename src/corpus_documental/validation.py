"""Validação de cobertura, reconstrução, transformações e relações."""
from collections import Counter, defaultdict
import math

from .layout import inline_connections


def validate_integrity(metadata, pages, structure, paragraphs, elements, events):
    errors = []

    def require(condition, code, **context):
        if not condition:
            errors.append({"code": code, **context})

    expected = metadata["selected_pages"]
    require([p["page_index"] for p in pages] == expected, "page_coverage")
    page_map = {p["page_index"]: p for p in pages}
    blocks = {(p["page_index"], b["block_id"]): b for p in pages
              for b in p["blocks"] if b["type"] == "text"}
    nodes = structure["nodes"]
    node_ids = [n["node_id"] for n in nodes]
    para_ids = [p["paragraph_id"] for p in paragraphs]
    elem_ids = [e["element_id"] for e in elements]
    all_ids = node_ids + para_ids + elem_ids
    require(len(all_ids) == len(set(all_ids)), "duplicate_identifiers")
    for node in nodes:
        require(node["parent_id"] is None or node["parent_id"] in node_ids,
                "hierarchy_parent", node_id=node["node_id"])
        visited, current = set(), node
        by_id = {n["node_id"]: n for n in nodes}
        while current and current["node_id"] not in visited:
            visited.add(current["node_id"])
            current = by_id.get(current["parent_id"])
        require(current is None, "hierarchy_cycle", node_id=node["node_id"])
        if node.get("element_id"):
            require(node["element_id"] in elem_ids, "hierarchy_element", node_id=node["node_id"])
    ownership, fragments = defaultdict(list), defaultdict(list)
    units = paragraphs + [e for e in elements if e.get("text_ownership") == "primary"]
    local_counts = Counter()
    previous_position = None
    multi_page = 0
    for index, paragraph in enumerate(paragraphs):
        unit_id = paragraph["paragraph_id"]
        require(paragraph["paragraph_global_order"] == index+1, "paragraph_order", unit_id=unit_id)
        require(paragraph["previous_id"] == (para_ids[index-1] if index else None), "previous_link", unit_id=unit_id)
        require(paragraph["next_id"] == (para_ids[index+1] if index+1 < len(para_ids) else None), "next_link", unit_id=unit_id)
        local_counts[paragraph["parent_id"]] += 1
        require(paragraph["paragraph_local_order"] == local_counts[paragraph["parent_id"]], "local_order", unit_id=unit_id)
        for key in ("chapter_id", "section_id"):
            require(paragraph[key] is None or paragraph[key] in node_ids, "hierarchy_link", unit_id=unit_id, field=key)
        by_id = {n["node_id"]: n for n in nodes}
        ancestors, current = [], by_id.get(paragraph["parent_id"])
        while current and current["node_id"] not in {n["node_id"] for n in ancestors}:
            ancestors.append(current)
            current = by_id.get(current["parent_id"])
        for key, kinds in (("chapter_id", {"chapter"}), ("section_id", {"section", "subsection"})):
            actual = next((n["node_id"] for n in ancestors if n["kind"] in kinds), None)
            require(paragraph[key] == actual, "hierarchy_ancestry", unit_id=unit_id, field=key)
        if paragraph["source_spans"]:
            span = paragraph["source_spans"][0]
            page = page_map.get(span["page_index"], {})
            order = structure.get("page_reading_order", {}).get(str(span["page_index"]), page.get("reading_order", []))
            rank = next((i for i, item in enumerate(order) if item["block_id"] == span["block_id"]
                         and item["block_char_start"] <= span["block_char_start"]
                         and item["block_char_end"] >= span["block_char_end"]), -1)
            require(rank >= 0, "reading_order_source", unit_id=unit_id)
            pos = (span["page_index"], rank, span["block_char_start"])
            require(previous_position is None or pos > previous_position, "source_order", unit_id=unit_id)
            previous_position = pos
        multi_page += len({s["page_index"] for s in paragraph["source_spans"]}) > 1
        require("".join(s["text"] for s in paragraph["sentences"]) == paragraph["text_clean"], "sentence_coverage", unit_id=unit_id)
        cursor = 0
        for sentence in paragraph["sentences"]:
            require(sentence["paragraph_id"] == unit_id and sentence["char_start"] == cursor
                    and paragraph["text_clean"][sentence["char_start"]:sentence["char_end"]] == sentence["text"],
                    "sentence_offsets", unit_id=unit_id)
            cursor = sentence["char_end"]
    for unit in units:
        unit_id = unit.get("paragraph_id", unit.get("element_id"))
        require(unit["document_id"] == metadata["document_id"], "document_link", unit_id=unit_id)
        require(unit["parent_id"] in node_ids, "unit_parent", unit_id=unit_id)
        for table_id in unit.get("related_table_ids", []):
            require(any(e["element_id"] == table_id and e["kind"] == "table" for e in elements), "table_link", unit_id=unit_id)
        require(bool(unit["source_spans"]), "missing_source", unit_id=unit_id)
        raw_parts, raw_cursor = [], 0
        for span in unit["source_spans"]:
            key = span["page_index"], span["block_id"]
            block, page = blocks.get(key), page_map.get(span["page_index"])
            if block is None or page is None:
                require(False, "unknown_source", unit_id=unit_id)
                continue
            start, end = span["block_char_start"], span["block_char_end"]
            require(0 <= start <= end <= len(block["text_raw"]), "block_offsets", unit_id=unit_id)
            require(span["char_start"] == block["char_start"] + start and
                    span["char_end"] == block["char_start"] + end, "page_offsets", unit_id=unit_id)
            source = page["text_raw"][span["char_start"]:span["char_end"]]
            require(source == block["text_raw"][start:end], "source_slice", unit_id=unit_id)
            raw_parts.append(source)
            ownership[key].append((start, end, unit_id))
            fragments[key].append((start, end, unit["text_raw"][raw_cursor:raw_cursor+end-start]))
            raw_cursor += end-start+1  # separador explícito entre source_spans de um parágrafo
            bbox = span["bbox"]
            require(len(bbox) == 4 and all(math.isfinite(x) for x in bbox)
                    and bbox[0] <= bbox[2] and bbox[1] <= bbox[3], "source_bbox", unit_id=unit_id)
        require(unit["text_raw"] == "\n".join(raw_parts), "raw_text_changed", unit_id=unit_id)
        text = unit["text_raw"]
        for transformation in unit["transformations"]:
            require(transformation["before"] == text, "transformation_chain", unit_id=unit_id)
            require(any(e["code"] == "normalization" and e.get("unit_id") == unit_id
                        and e.get("before") == transformation["before"] and e.get("after") == transformation["after"]
                        for e in events), "missing_transformation_audit", unit_id=unit_id)
            text = transformation["after"]
        require(text == unit["text_clean"], "unjustified_clean_text", unit_id=unit_id)
        require(bool(unit.get("classification")), "unclassified_text", unit_id=unit_id)
    covered_blocks = 0
    for key, block in blocks.items():
        cursor = 0
        for start, end, owner in sorted(ownership[key]):
            require(start == cursor, "text_gap_or_duplicate", block_id=key[1], unit_id=owner)
            cursor = end
        complete = cursor == len(block["text_raw"]) and bool(ownership[key])
        require(complete, "block_coverage", block_id=key[1], page_index=key[0])
        covered_blocks += complete
        rebuilt = "".join(text for _, _, text in sorted(fragments[key]))
        require(rebuilt == block["text_raw"], "block_reconstruction", block_id=key[1])
        for before, after in inline_connections(block):
            previous_owner = next((owner for start, end, owner in ownership[key] if start <= before < end), None)
            next_owner = next((owner for start, end, owner in ownership[key] if start <= after < end), None)
            if previous_owner in para_ids and next_owner in para_ids:
                require(previous_owner == next_owner, "inline_paragraph_split", page_index=key[0],
                        block_id=key[1], previous_unit_id=previous_owner, next_unit_id=next_owner)
            order = structure.get("page_reading_order", {}).get(str(key[0]), page_map[key[0]].get("reading_order", []))
            ranks = [next((i for i, item in enumerate(order) if item["block_id"] == key[1]
                           and item["block_char_start"] <= offset < item["block_char_end"]), -1)
                     for offset in (before, after)]
            require(0 <= ranks[0] <= ranks[1], "inline_reading_order", page_index=key[0], block_id=key[1])
    for page in pages:
        reconstructed = "\n".join("".join(text for _, _, text in sorted(fragments[(page["page_index"], b["block_id"])]))
                                  for b in page["blocks"] if b["type"] == "text")
        require(reconstructed == page["text_raw"], "page_reconstruction", page_index=page["page_index"])
        if page["status"] == "failed":
            require(any(e["code"] == "page_extraction_failed" and e.get("page_index") == page["page_index"] for e in events),
                    "unlogged_page_failure", page_index=page["page_index"])
    processing_errors = [e for e in events if e["severity"] == "error"]
    warnings = [e for e in events if e["severity"] == "warning"]
    problems = sorted({e["page_index"] for e in events if e["severity"] in {"warning", "error"} and "page_index" in e}
                      | {p["page_index"] for p in pages if p["status"] != "ok"}
                      | {s["page_index"] for u in units if u["quality_status"] == "review_required" for s in u["source_spans"]})
    status = "failed" if errors or processing_errors else "review_required" if warnings or problems else "automated_checks_passed"
    return {
        "schema_version": "1.0", "status": status,
        "scope": {"selected_pages": expected, "out_of_scope_pages": metadata["out_of_scope_pages"]},
        "checks": {"errors": errors, "processing_errors": processing_errors,
                   "raw_reconstruction_matches": not any(e["code"] in {"block_reconstruction", "page_reconstruction", "raw_text_changed"} for e in errors)},
        "metrics": {"pages_selected": len(expected), "pages_recorded": len(pages),
                    "page_record_coverage_ratio": len(set(page_map) & set(expected))/len(expected) if expected else None,
                    "pages_extracted": sum(p["status"] != "failed" for p in pages),
                    "pages_failed": sum(p["status"] == "failed" for p in pages),
                    "pages_without_text": sum(not p["text_raw"].strip() for p in pages),
                    "text_blocks": len(blocks), "classified_blocks": covered_blocks,
                    "block_coverage_ratio": covered_blocks/len(blocks) if blocks else None,
                    "paragraphs": len(paragraphs), "cross_page_paragraphs": multi_page,
                    "paragraphs_requiring_review": sum(p["quality_status"] == "review_required" for p in paragraphs),
                    "consistency_errors": len(errors), "warning_count": len(warnings),
                    "segmentation_confidence": "not_calibrated; heuristic rules, manual review required",
                    "ocr_pages": sum(p["method"] == "ocr" for p in pages)},
        "problem_pages": problems,
        "fidelity": "Preservation relative to extracted text checked; fidelity to visible PDF is not certified.",
        "limitations": ["Reading order, hierarchy and paragraph segmentation are heuristic.",
                        "Printed page numbers require visual verification; embedded labels are separate.",
                        "OCR and sentence boundaries require human review.",
                        "Vector figures and borderless tables may remain unrecognized."]}


def validate(metadata, pages, structure, paragraphs, elements, events):
    from .quality import assess_document
    result = validate_integrity(metadata, pages, structure, paragraphs, elements, events)
    documentary = assess_document(metadata, pages, structure, paragraphs, elements, events)
    raw_codes = {"page_coverage", "unknown_source", "block_offsets", "page_offsets", "source_slice", "raw_text_changed",
                 "transformation_chain", "missing_transformation_audit", "unjustified_clean_text", "text_gap_or_duplicate",
                 "block_coverage", "block_reconstruction", "page_reconstruction", "unlogged_page_failure"}
    raw_errors = [e for e in result["checks"]["errors"] if e["code"] in raw_codes]
    formal = [e for e in result["checks"]["errors"] if e["code"] not in raw_codes]
    documentary["formal_relationship_errors"] = formal
    blockers = raw_errors+formal+result["checks"]["processing_errors"]+documentary["blockers"]
    status = "blocked" if blockers else "review_required" if documentary["review_items"] else "approved"
    result.update(schema_version="1.1", status=status,
                  raw_integrity={"status": "failed" if raw_errors or result["checks"]["processing_errors"] else "passed",
                                 "errors": raw_errors, "raw_reconstruction_matches": result["checks"]["raw_reconstruction_matches"]},
                  documentary_quality=documentary)
    categories = {
        "raw_integrity": not raw_errors and not result["checks"]["processing_errors"],
        "identifiers_relationships_and_order": not formal,
        "documentary_reconstruction": not documentary["blockers"],
        "reading_order": not any(e["code"] in {"visual_x_inversion", "visual_y_inversion", "inline_reading_order", "source_order"} for e in formal+documentary["blockers"]),
        "paragraph_boundaries": not any(e["code"] in {"merged_visual_paragraphs", "inline_paragraph_split"} for e in formal+documentary["blockers"]),
        "hierarchy": not any("hierarchy" in e["code"] or e["code"] in {"missing_paragraph_chapter", "missing_paragraph_section"} for e in formal+documentary["blockers"]),
        "special_elements": not any("note_" in e["code"] or "quote" in e["code"] for e in documentary["blockers"]),
        "graphic_geometry_and_type": not any("graphic_" in e["code"] for e in documentary["blockers"]),
        "normalization_provenance": not any("normalization_map_" in e["code"] for e in documentary["blockers"]),
        "manual_review_of_unsafe_cases": not documentary["review_items"],
    }
    result["blocking_criteria"] = [{"criterion": name, "passed": passed} for name, passed in categories.items()]
    result["chunking_gate"] = {"allowed": all(categories.values()), "required_state": "approved",
                               "blocking_error_count": len(blockers), "pending_review_count": len(documentary["review_items"]),
                               "reason": "All implemented documentary criteria satisfied." if all(categories.values()) else "Documentary blockers or unsafe cases remain unresolved."}
    result["metrics"].update(documentary["metrics"])
    result["checks"]["documentary_errors"] = documentary["blockers"]
    result["fidelity_certified"] = False
    return result


def validate_corpus(path):
    from pathlib import Path
    from .storage import load_corpus
    from .ingest import sha256
    import json
    path = Path(path)
    data = load_corpus(path)
    report = validate(**data)
    checks = [("original.pdf", data["metadata"]["sha256"], "source_hash_mismatch"),
              ("pages_raw.jsonl", data["metadata"].get("processing", {}).get("raw_pages_sha256"), "raw_artifact_hash_mismatch")]
    for manifest_file in sorted((path/"history").rglob("manifest.json")) if (path/"history").exists() else []:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        for filename, expected in manifest.items():
            target = (manifest_file.parent/filename).resolve()
            if not target.is_relative_to(path.resolve()):
                checks.append((None, expected, "history_artifact_outside_corpus"))
            elif not target.is_file():
                checks.append((str(target), expected, "history_artifact_missing"))
            else:
                checks.append((str(target), expected, "history_artifact_hash_mismatch"))
    for filename, expected, code in checks:
        target = path/filename if filename is not None else None
        if expected and (target is None or not target.is_file() or sha256(target) != expected):
            error = {"code": code}
            report["checks"]["errors"].append(error)
            report["raw_integrity"]["errors"].append(error)
            report["raw_integrity"]["status"] = "failed"
            report["status"] = "blocked"
            report["metrics"]["consistency_errors"] += 1
            report["chunking_gate"].update(allowed=False, reason="Artifact digest differs from the registered source.")
            report["chunking_gate"]["blocking_error_count"] += 1
            for criterion in report["blocking_criteria"]:
                if criterion["criterion"] == "raw_integrity":
                    criterion["passed"] = False
    return report
