"""Extração física por página; mantém ordem nativa e tipografia."""
import pymupdf


def _json_geometry(value):
    if isinstance(value, (pymupdf.Point, pymupdf.Rect, pymupdf.Quad)):
        return [_json_geometry(v) for v in value]
    if isinstance(value, (tuple, list)):
        return [_json_geometry(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_geometry(v) for k, v in value.items()}
    return value


def _blocks(data, page_index):
    blocks, offset, texts = [], 0, []
    for index, block in enumerate(data["blocks"]):
        identifier = f"p{page_index:06}_b{index:05}"
        if block["type"] != 0:
            blocks.append({"block_id": identifier, "type": "image", "bbox": block["bbox"],
                           "width": block.get("width"), "height": block.get("height")})
            continue
        lines = []
        for line in block["lines"]:
            spans = []
            for span in line["spans"]:
                chars = span.get("chars", [])
                spans.append({"text": "".join(c["c"] for c in chars), "bbox": span["bbox"],
                              "font": span["font"], "size": span["size"],
                              "flags": span["flags"], "chars": chars})
            lines.append({"text": "".join(s["text"] for s in spans), "bbox": line["bbox"],
                          "direction": line["dir"], "spans": spans})
        raw = "\n".join(line["text"] for line in lines)
        if texts:
            offset += 1  # Separador físico entre blocos, preservado na página.
        blocks.append({"block_id": identifier, "type": "text", "bbox": block["bbox"],
                       "lines": lines, "text_raw": raw,
                       "char_start": offset, "char_end": offset + len(raw)})
        texts.append(raw)
        offset += len(raw)
    return blocks, "\n".join(texts)


def extract_pages(path, config, audit):
    results = []
    with pymupdf.open(path) as pdf:
        for index in config.pages:
            result = {"page_index": index, "status": "ok", "method": "native",
                      "tool": f"PyMuPDF {pymupdf.VersionBind}", "alerts": []}
            try:
                page = pdf[index]
                result.update(width=page.cropbox.width, height=page.cropbox.height,
                              rotation=page.rotation, coordinate_system="unrotated PyMuPDF points",
                              # Etiqueta embutida não comprova o número visível impresso.
                              pdf_page_label=page.get_label() or None,
                              printed_page_number=None)
                data = page.get_text("rawdict", sort=False)
                blocks, raw = _blocks(data, index)
                native = {"text_raw": raw, "blocks": blocks}
                image_area = sum((b["bbox"][2]-b["bbox"][0])*(b["bbox"][3]-b["bbox"][1])
                                 for b in blocks if b["type"] == "image")
                image_heavy = image_area > page.rect.width * page.rect.height * .4
                unreliable = bool(raw) and raw.count("\ufffd") / max(1, len(raw)) > .02
                needs_ocr = unreliable or (len(raw.strip()) < 20 and image_heavy)
                result["source_kind"] = ("mixed" if raw.strip() and image_heavy else
                                         "scanned" if image_heavy else
                                         "text" if raw.strip() else "blank_or_vector")
                if config.ocr == "always" or (config.ocr == "auto" and needs_ocr):
                    result["native_extraction"] = native
                    try:
                        tp = page.get_textpage_ocr(language=config.ocr_language,
                                                   dpi=config.ocr_dpi, full=True)
                        ocr_blocks, ocr_raw = _blocks(page.get_text("rawdict", textpage=tp), index)
                        if not ocr_raw.strip():
                            raise RuntimeError("OCR não produziu texto")
                        blocks, raw = ocr_blocks, ocr_raw
                        result["method"] = "ocr"
                        result["status"] = "review_required"
                        result["alerts"].append("ocr_text_requires_manual_review")
                        audit.add("ocr_applied", "OCR aplicado; fidelidade exige revisão humana.",
                                  severity="warning", page_index=index)
                    except Exception as error:
                        result["status"] = "review_required"
                        result["alerts"].append("ocr_failed")
                        audit.add("ocr_failed", str(error), severity="error", page_index=index)
                elif needs_ocr:
                    result["status"] = "review_required"
                    result["alerts"].append("ocr_required_but_disabled")
                    audit.add("ocr_required", "Camada textual insuficiente e OCR desativado.",
                              severity="error", page_index=index)
                if not raw.strip():
                    result["status"] = "review_required"
                    result["alerts"].append("no_text_blank_scan_or_vector_requires_review")
                    audit.add("no_text", "Página sem texto; revisar se branca, vetorial ou digitalizada.",
                              severity="warning", page_index=index)
                result.update(blocks=blocks, text_raw=raw)
                try:
                    result["drawings"] = [_json_geometry(d) for d in page.get_drawings()]
                except Exception as error:
                    result["drawings"] = []
                    audit.add("vector_detection_failed", str(error), severity="warning", page_index=index)
                # A detecção de tabelas complementa, sem substituir, os blocos de texto.
                try:
                    result["tables"] = [{"bbox": t.bbox, "cells": t.extract()}
                                        for t in page.find_tables().tables]
                except Exception as error:
                    result["tables"] = []
                    audit.add("table_detection_failed", str(error), severity="warning", page_index=index)
            except Exception as error:
                result.update(status="failed", blocks=[], text_raw="", tables=[],
                              alerts=["page_extraction_failed"])
                audit.add("page_extraction_failed", str(error), severity="error", page_index=index)
            results.append(result)
    return results
