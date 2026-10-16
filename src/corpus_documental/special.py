"""Vínculos explícitos de citações e notas, sem interpretar seu conteúdo."""
import re

from .models import stable_id


def link_special_elements(pages, paragraphs, elements, nodes, version, audit):
    by_node = {node["node_id"]: node for node in nodes}

    def chapter(parent):
        visited = set()
        while parent in by_node and parent not in visited:
            visited.add(parent)
            node = by_node[parent]
            if node["kind"] == "chapter":
                return parent
            parent = node["parent_id"]
        return None

    notes = {}
    for element in elements:
        if element["kind"] in {"footnote", "endnote", "endnote_candidate"}:
            match = re.match(r"^\s*(\d+)\b", element["text_raw"])
            if match:
                element.update(note_number=match[1], call_ids=[], anchor_paragraph_ids=[])
                notes.setdefault((chapter(element["parent_id"]), match[1]), []).append(element)
    for paragraph in paragraphs:
        paragraph["note_call_ids"] = []
        if paragraph["classification"] == "block_quote":
            identifier = stable_id("quote", version, paragraph["paragraph_id"])
            paragraph["quote_element_id"] = identifier
            elements.append({"element_id": identifier, "kind": "block_quote", "text_ownership": "reference",
                             "paragraph_id": paragraph["paragraph_id"], "parent_id": paragraph["parent_id"],
                             "source_spans": paragraph["source_spans"], "quality_status": "review_required",
                             "composition_evidence": paragraph["composition_evidence"]})
    for page in pages:
        for block in page["blocks"]:
            if block["type"] != "text":
                continue
            offset = 0
            for line in block["lines"]:
                local = 0
                for span in line["spans"]:
                    number = span["text"].strip()
                    if span["flags"] & 1 and number.isdigit():
                        start = offset+local+len(span["text"])-len(span["text"].lstrip())
                        end = start+len(number)
                        owners = [p for p in paragraphs if any(s["page_index"] == page["page_index"]
                                  and s["block_id"] == block["block_id"] and s["block_char_start"] <= start
                                  and s["block_char_end"] >= end for s in p["source_spans"])]
                        owner = owners[0] if len(owners) == 1 else None
                        targets = notes.get((owner["chapter_id"] if owner else None, number), [])
                        target = targets[0] if len(targets) == 1 else None
                        identifier = stable_id("call", version, page["page_index"], block["block_id"], start, end)
                        physical = {"page_index": page["page_index"], "printed_page_number": None,
                                    "pdf_page_label": page.get("pdf_page_label"), "block_id": block["block_id"],
                                    "bbox": list(span["bbox"]), "block_char_start": start, "block_char_end": end,
                                    "char_start": block["char_start"]+start, "char_end": block["char_start"]+end}
                        clean_ranges = []
                        if owner:
                            for run in owner["normalization_map"]:
                                for ref in run["source_refs"]:
                                    if ref["page_index"] == page["page_index"] and ref["block_id"] == block["block_id"]:
                                        a, b = max(start, ref["block_char_start"]), min(end, ref["block_char_end"])
                                        if a < b:
                                            if run["kind"] == "identity":
                                                base = run["clean_start"]+ref["text_raw_start"]-run["text_raw_start"]
                                                clean_ranges.append([base+a-ref["block_char_start"], base+b-ref["block_char_start"]])
                                            else:
                                                clean_ranges.append([run["clean_start"], run["clean_end"]])
                        elements.append({"element_id": identifier, "kind": "note_call", "text_ownership": "reference",
                                         "text_raw": number, "note_number": number, "source_spans": [physical],
                                         "paragraph_id": owner["paragraph_id"] if owner else None,
                                         "parent_id": owner["parent_id"] if owner else nodes[0]["node_id"],
                                         "target_note_id": target["element_id"] if target else None,
                                         "text_clean_ranges": clean_ranges,
                                         "quality_status": "automated" if owner and target else "review_required"})
                        if owner:
                            owner["note_call_ids"].append(identifier)
                        if target and owner:
                            target["call_ids"].append(identifier)
                            target["anchor_paragraph_ids"].append(owner["paragraph_id"])
                            target["anchor_paragraph_id"] = owner["paragraph_id"]
                            if target["kind"] in {"endnote_candidate", "footnote"}:
                                target["kind"] = target["classification"] = "endnote" if target["source_spans"][0]["page_index"] > page["page_index"] else "footnote"
                            target["quality_status"] = "automated"
                            target["classification_resolved_by"] = "unique_superscript_note_link"
                            target["evidence"] = "numbered_note_linked_to_superscript_call_in_same_chapter"
                        audit.add("note_link", "Chamada sobrescrita e nota numerada vinculadas." if owner and target else "Vínculo de nota exige revisão.",
                                  severity="info" if owner and target else "warning", page_index=page["page_index"],
                                  element_id=identifier, target_note_id=target["element_id"] if target else None)
                    local += len(span["text"])
                offset += len(line["text"])+1
    for element in elements:
        if element["kind"] == "heading_number":
            source = element["source_spans"][0]["block_id"]
            node = next((n for n in nodes if n.get("evidence", {}).get("number_block_id") == source), None)
            if node:
                element.update(parent_id=node["node_id"], chapter_id=node["node_id"], numbering_role="chapter_number")
