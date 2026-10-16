"""Reconstrução conservadora; toda fatia física tem um único proprietário."""
from collections import Counter
import re
import statistics

from .layout import font_size, margin_key, reading_order, repeated_margins
from .models import stable_id
from .normalization import normalize


def segments(block):
    lines = block["lines"]
    if not lines:
        return [(0, len(block["text_raw"]), block)]
    cuts, offset = [0], 0
    for i, line in enumerate(lines):
        if i:
            previous = lines[i - 1]
            height = max(1, previous["bbox"][3] - previous["bbox"][1])
            gap = line["bbox"][1] - previous["bbox"][3]
            prev_size = font_size({"lines": [previous]})
            size = font_size({"lines": [line]})
            if gap > .8 * height or abs(prev_size - size) > 1.5:
                cuts.append(offset)
        offset += len(line["text"]) + (1 if i < len(lines) - 1 else 0)
    cuts.append(len(block["text_raw"]))
    result = []
    for start, end in zip(cuts, cuts[1:]):
        start_line = block["text_raw"][:start].count("\n")
        count = block["text_raw"][start:end].rstrip("\n").count("\n") + 1
        selected = lines[start_line:start_line + count]
        boxes = [line["bbox"] for line in selected]
        bbox = [min(b[0] for b in boxes), min(b[1] for b in boxes),
                max(b[2] for b in boxes), max(b[3] for b in boxes)]
        result.append((start, end, {**block, "lines": selected, "bbox": bbox,
                                   "text_raw": block["text_raw"][start:end]}))
    return result


def heading(text):
    text = text.strip()
    if len(text) > 160 or len(text.splitlines()) > 2:
        return None
    if re.match(r"^(parte|part|livro|book)\s+[IVXLCDM\d]+(?:\b|[.:—–-])", text, re.I):
        return "part", 1
    if re.match(r"^(cap[íi]tulo|chapter)\s+[IVXLCDM\d]+(?:\b|[.:—–-])", text, re.I):
        return "chapter", 2
    if re.match(r"^(se[çc][ãa]o|section)\s+[IVXLCDM\d]+\b", text, re.I):
        return "section", 3
    if re.match(r"^\d+(?:\.\d+){1,}\.?\s+\S", text):
        depth = len(re.match(r"^\d+(?:\.\d+)+", text)[0].split("."))
        return ("section", 3) if depth == 2 else ("subsection", 4)
    if text.casefold() in {"referências", "referências bibliográficas", "bibliografia", "references", "notas", "notas finais", "endnotes"}:
        return "section", 3
    return None


def source_span(page, block, start, end, bbox):
    return {"page_index": page["page_index"], "printed_page_number": None,
            "pdf_page_label": page.get("pdf_page_label"), "block_id": block["block_id"],
            "bbox": list(bbox), "block_char_start": block.get("source_block_start", 0) + start,
            "block_char_end": block.get("source_block_start", 0) + end,
            "char_start": block["char_start"] + start, "char_end": block["char_start"] + end}


def sentences(text, paragraph_id):
    # Segmentação linguística provisória; intervalos cobrem o texto limpo sem perdas.
    boundaries = [0]
    abbreviations = {"sr", "sra", "dr", "dra", "prof", "etc", "ex", "p", "pp", "vol", "fig", "art"}
    for match in re.finditer(r"[.!?][\"”’»)]*\s+(?=[A-ZÀ-Ý])", text):
        prefix = text[:match.start()]
        last = re.search(r"([\w]+)$", prefix)
        if last and (last[1].casefold() in abbreviations or len(last[1]) == 1):
            continue
        boundaries.append(match.end())
    boundaries.append(len(text))
    return [{"sentence_id": stable_id("sent", paragraph_id, start, end),
             "paragraph_id": paragraph_id, "order": i + 1, "char_start": start,
             "char_end": end, "text": text[start:end], "quality_status": "provisional_rule_based"}
            for i, (start, end) in enumerate(zip(boundaries, boundaries[1:])) if end > start]


def _fold(text):
    return " ".join(re.findall(r"\w+", text.casefold()))


def _outline_entries(metadata):
    entries, stack = [], []
    for item in metadata.get("pdf_outline", []):
        while stack and stack[-1]["outline_level"] >= item["level"]:
            stack.pop()
        detected = heading(item["title"])
        if not detected and re.match(r"^\d+[.)]\s+", item["title"]) and stack and stack[-1].get("kind") == "part":
            detected = "chapter", 2
        entry = {**item, "outline_level": item["level"],
                 "kind": detected[0] if detected else None,
                 "level": detected[1] if detected else None,
                 "outline_parent_index": stack[-1]["outline_index"] if stack else None}
        entries.append(entry)
        stack.append(entry)
    return entries


def _outline_hints(page, entries):
    hints = {}
    for entry in entries:
        if entry["page_index"] != page["page_index"] or not entry["kind"]:
            continue
        title = re.sub(r"^\d+[.)]\s+", "", entry["title"])
        candidates = [b for b in page["blocks"] if b["type"] == "text" and
                      _fold(b["text_raw"]) in {_fold(title), _fold(entry["title"])}]
        if len(candidates) == 1:
            hints[candidates[0]["block_id"]] = entry
            number = re.match(r"^(\d+)[.)]\s+", entry["title"])
            if number:
                for b in page["blocks"]:
                    if b["type"] == "text" and b["text_raw"].strip() == number[1] and b["bbox"][3] <= candidates[0]["bbox"][1]:
                        hints[b["block_id"]] = {**entry, "number_only": True}
    return hints


def build_structure(pages, metadata, version, config, audit):
    document_id = metadata["document_id"]
    root = {"node_id": document_id, "kind": "work", "parent_id": None,
            "title": metadata["bibliographic"]["title"], "element_id": None}
    nodes, paragraphs, elements, stack = [root], [], [], []
    outline = _outline_entries(metadata)
    # Contexto anterior ao recorte provém dos marcadores, sem extrair outros capítulos.
    for i, entry in enumerate(outline):
        end = next((e["page_index"] for e in outline[i+1:] if e["outline_level"] <= entry["outline_level"]
                    and e["page_index"] >= entry["page_index"]), metadata["page_count"])
        if entry["kind"] and entry["page_index"] < config.pages[0] < end:
            while stack and stack[-1]["level"] >= entry["level"]:
                stack.pop()
            node = {"node_id": stable_id("node", version, "outline", entry["outline_index"]),
                    "kind": entry["kind"], "level": entry["level"], "title": entry["title"],
                    "parent_id": stack[-1]["node_id"] if stack else document_id,
                    "element_id": None, "quality_status": "review_required",
                    "evidence": {"type": "pdf_bookmark", "outline_index": entry["outline_index"],
                                 "page_index": entry["page_index"], "outside_selected_pages": True}}
            nodes.append(node)
            stack.append(node)
            audit.add("outline_context", "Ancestral do recorte obtido de marcador PDF; página fora do corpo processado.",
                      severity="warning", node_id=node["node_id"], source_page_index=entry["page_index"])
    margins = repeated_margins(pages)
    all_sizes = [font_size(b) for p in pages for b in p["blocks"]
                 if b["type"] == "text" and len(b["text_raw"]) > 80]
    if not all_sizes:
        all_sizes = [font_size(b) for p in pages for b in p["blocks"] if b["type"] == "text"]
    body_size = statistics.median(all_sizes) if all_sizes else 12
    title_styles = Counter((round(font_size(b), 1), tuple(sorted({s["font"] for l in b.get("lines", []) for s in l["spans"]})))
                           for p in pages for b in p["blocks"] if b["type"] == "text"
                           and font_size(b) >= body_size * 1.25 and b["text_raw"].strip().isupper()
                           and len(b["text_raw"]) < 180)
    region, barrier = None, 0
    for page in pages:
        ordered = reading_order(page, audit)
        hints = _outline_hints(page, outline)
        page["reading_order"] = [{"block_id": b["block_id"],
                                  "block_char_start": b.get("source_block_start", 0),
                                  "block_char_end": b.get("source_block_end", len(b.get("text_raw", "")))}
                                 for b in ordered]
        for drawing_index, drawing in enumerate(page.get("drawings", [])):
            if any(_inside(drawing["rect"], table["bbox"]) for table in page.get("tables", [])):
                continue
            elements.append({"element_id": stable_id("vector", version, page["page_index"], drawing_index),
                             "kind": "vector_graphic_candidate", "page_index": page["page_index"],
                             "bbox": drawing["rect"], "source_drawing_index": drawing_index,
                             "parent_id": stack[-1]["node_id"] if stack else document_id,
                             "source_spans": [], "quality_status": "review_required", "text_ownership": "none"})
            audit.add("vector_graphic_review", "Traçado vetorial preservado; agrupamento em figuras exige revisão.",
                      severity="warning", page_index=page["page_index"])
        page_tables = []
        for table_index, table in enumerate(page.get("tables", [])):
            table_id = stable_id("table", version, page["page_index"], table_index)
            page_tables.append((table_id, table))
            elements.append({"element_id": table_id,
                             "kind": "table", "source_spans": [], "page_index": page["page_index"],
                             "bbox": table["bbox"], "cells": table["cells"],
                             "parent_id": stack[-1]["node_id"] if stack else document_id,
                             "quality_status": "review_required", "text_ownership": "derived"})
            audit.add("table_detected", "Tabela detectada geometricamente; células exigem revisão.",
                      severity="warning", page_index=page["page_index"])
        for block in ordered:
            if block["type"] == "image":
                elements.append({"element_id": stable_id("fig", version, block["block_id"]),
                                 "kind": "figure", "page_index": page["page_index"],
                                 "bbox": block["bbox"], "source_spans": [],
                                 "source_block_id": block["block_id"], "text_ownership": "none",
                                 "parent_id": stack[-1]["node_id"] if stack else document_id,
                                 "quality_status": "review_required"})
                audit.add("figure_detected", "Imagem preservada por referência ao PDF original.",
                          severity="warning", page_index=page["page_index"])
                barrier += 1
                continue
            block_segments = segments(block)
            if len(block_segments) > 1:
                audit.add("block_segmentation", "Bloco dividido por espaçamento ou mudança tipográfica.",
                          severity="warning", page_index=page["page_index"], block_id=block["block_id"],
                          boundaries=[[a, b] for a, b, _ in block_segments])
            for start, end, segment in block_segments:
                raw = segment["text_raw"]
                span = source_span(page, block, start, end, segment["bbox"])
                kind, level, uncertain = "paragraph", None, False
                key = margin_key(page, block)
                detected = heading(raw)
                size = font_size(segment)
                outline_hint = hints.get(block["block_id"])
                style = (round(size, 1), tuple(sorted({s["font"] for l in segment.get("lines", []) for s in l["spans"]})))
                if key in margins:
                    kind, uncertain = key[0], True
                elif outline_hint:
                    if outline_hint.get("number_only"):
                        kind = "heading_number"
                    else:
                        kind, level = outline_hint["kind"], outline_hint["level"]
                elif detected:
                    kind, level = detected
                elif any(_inside(segment["bbox"], table["bbox"]) for table in page.get("tables", [])):
                    kind = "table_text"
                elif re.match(r"^\s*(?:\d+[.)]?|[*†‡])\s+", raw) and segment["bbox"][1] > page["height"] * .65 and size < body_size * .85:
                    note_count = sum(bool(re.match(r"^\s*\d+\s+", b.get("text_raw", ""))) and font_size(b) < body_size*.85
                                     for b in page["blocks"] if b["type"] == "text")
                    kind, uncertain = ("endnote_candidate" if note_count >= 2 else "footnote"), True
                elif re.match(r"^\s*(figura|figure|tabela|table|quadro)\s+\d+", raw, re.I):
                    kind, uncertain = "caption", True
                elif re.match(r"^\s*(?:[•●▪◦–—-]|\d+[.)])\s+", raw):
                    kind, uncertain = "list_item", True
                elif len(raw.strip()) <= 2 and size > body_size*1.3:
                    kind = "marginal_glyph_candidate" if segment["bbox"][1] > page["height"]*.85 else "short_text_candidate"
                    uncertain = True
                elif size >= body_size * 1.3 and len(raw.strip()) < 180:
                    if any(n["kind"] == "chapter" for n in stack) and raw.strip().isupper() and title_styles[style] >= 2:
                        kind, level, uncertain = "section", 3, True
                    else:
                        kind, uncertain = "title_candidate", True
                elif region:
                    kind, uncertain = region, True
                elif len(segment["lines"]) == 1 and size > body_size * 1.1:
                    kind, uncertain = "title_candidate", True
                if kind == "paragraph" and segment["bbox"][0] > page["width"] * .2 and size < body_size * .95:
                    kind, uncertain = "block_quote", True
                identity = stable_id("para" if kind in {"paragraph", "block_quote"} else "elem",
                                     version, block["block_id"], span["block_char_start"], span["block_char_end"])
                clean, transforms = normalize(raw, config, audit, identity)
                record = {"document_id": document_id, "text_raw": raw, "text_clean": clean,
                          "source_spans": [span], "transformations": transforms,
                          "quality_status": "review_required" if uncertain or page["status"] != "ok" else "automated",
                          "classification": kind}
                if kind == "table_text":
                    record["related_table_ids"] = [identity for identity, table in page_tables if _inside(segment["bbox"], table["bbox"])]
                if kind in {"footnote", "endnote", "endnote_candidate"}:
                    record["anchor_paragraph_id"] = None
                if kind == "caption":
                    record["related_element_id"] = None
                if uncertain:
                    audit.add("classification_review", f"Classificação heurística: {kind}.",
                              severity="warning", unit_id=identity, page_index=page["page_index"])
                if kind in {"paragraph", "block_quote"}:
                    parent = stack[-1]["node_id"] if stack else document_id
                    record.update(paragraph_id=identity, parent_id=parent,
                                  chapter_id=next((n["node_id"] for n in reversed(stack) if n["kind"] == "chapter"), None),
                                  section_id=next((n["node_id"] for n in reversed(stack) if n["kind"] in {"section", "subsection"}), None),
                                  _barrier=barrier, _size=size)
                    paragraphs.append(record)
                    audit.add("paragraph_boundary", "Unidade baseada em bloco físico e quebras geométricas; segmentação heurística.",
                              unit_id=identity, source_spans=[span])
                else:
                    record.update(element_id=identity, kind=kind, text_ownership="primary",
                                  parent_id=stack[-1]["node_id"] if stack else document_id)
                    elements.append(record)
                    if level is not None:
                        while stack and stack[-1]["level"] >= level:
                            stack.pop()
                        node_id = stable_id("node", version, identity)
                        node = {"node_id": node_id, "kind": kind, "level": level,
                                "parent_id": stack[-1]["node_id"] if stack else document_id,
                                "title": clean, "element_id": identity,
                                "quality_status": "review_required" if uncertain else "automated"}
                        evidence = ({"type": "pdf_bookmark", "outline_index": outline_hint["outline_index"],
                                     "title": outline_hint["title"]} if outline_hint else
                                    {"type": "repeated_typographic_style", "font_size": size,
                                     "font_names": style[1], "provisional": True} if uncertain else
                                    {"type": "explicit_text_marker"})
                        node["evidence"] = evidence
                        record["parent_id"] = node["parent_id"]
                        record["node_id"] = node_id
                        nodes.append(node)
                        stack.append(node)
                        region = ("reference" if clean.casefold() in {"referências", "referências bibliográficas", "bibliografia", "references"}
                                  else "endnote" if clean.casefold() in {"notas", "notas finais", "endnotes"} else None)
                        audit.add("hierarchy_decision", "Divisão identificada por evidência textual, marcador PDF ou estilo tipográfico provisório.",
                                  severity="warning" if uncertain else "info",
                                  unit_id=identity, node_id=node_id, evidence=evidence, source_text=raw)
                    if kind not in {"header", "footer", "footnote", "endnote_candidate"}:
                        barrier += 1
    paragraphs = _merge(paragraphs, config, audit)
    local_counts = Counter()
    for index, record in enumerate(paragraphs):
        record.pop("_barrier", None)
        record.pop("_size", None)
        local_counts[record["parent_id"]] += 1
        record.update(paragraph_global_order=index + 1,
                      paragraph_local_order=local_counts[record["parent_id"]],
                      previous_id=paragraphs[index-1]["paragraph_id"] if index else None,
                      next_id=paragraphs[index+1]["paragraph_id"] if index+1 < len(paragraphs) else None,
                      sentences=sentences(record["text_clean"], record["paragraph_id"]))
    return {"document_id": document_id, "corpus_version": version, "nodes": nodes}, paragraphs, elements


def _inside(box, outer):
    x0, y0, x1, y1 = box
    area = max(0, min(x1, outer[2])-max(x0, outer[0])) * max(0, min(y1, outer[3])-max(y0, outer[1]))
    return area / max(1, (x1-x0)*(y1-y0)) > .7


def _merge(paragraphs, config, audit):
    merged = []
    for current in paragraphs:
        if merged:
            previous = merged[-1]
            a, b = previous["source_spans"][-1], current["source_spans"][0]
            compatible = (b["page_index"] == a["page_index"] + 1
                          and previous["parent_id"] == current["parent_id"]
                          and previous["_barrier"] == current["_barrier"]
                          and abs(previous["_size"] - current["_size"]) < .5
                          and abs(a["bbox"][0] - b["bbox"][0]) < 12
                          and previous["text_clean"] and current["text_clean"]
                          and not re.search(r'[.!?:;][\"”’»)]*$', previous["text_clean"])
                          and current["text_clean"][0].islower())
            if compatible:
                audit.add("page_continuation_candidate", "Possível continuação entre páginas; revisão obrigatória.",
                          severity="warning", unit_id=previous["paragraph_id"], next_unit_id=current["paragraph_id"],
                          applied=config.merge_pages)
                if config.merge_pages:
                    old_ids = [previous["paragraph_id"], current["paragraph_id"]]
                    previous["paragraph_id"] = stable_id("para", *old_ids)
                    previous["text_raw"] += "\n" + current["text_raw"]
                    previous["source_spans"].extend(current["source_spans"])
                    previous["text_clean"], previous["transformations"] = normalize(
                        previous["text_raw"], config, audit, previous["paragraph_id"])
                    previous["quality_status"] = "review_required"
                    audit.add("paragraph_merge", "Junção entre páginas autorizada pela opção de execução.",
                              unit_id=previous["paragraph_id"], predecessor_ids=old_ids)
                    continue
            elif (b["page_index"] == a["page_index"] + 1 and previous["parent_id"] == current["parent_id"]
                  and previous["_barrier"] == current["_barrier"] and previous["text_clean"]
                  and not re.search(r'[.!?:;][\"”’»)]*$', previous["text_clean"])):
                audit.add("page_continuation_ambiguous", "Limite de página com possível continuação, mas indícios insuficientes para junção.",
                          severity="warning", unit_id=previous["paragraph_id"], next_unit_id=current["paragraph_id"],
                          page_index=b["page_index"])
        merged.append(current)
    return merged
