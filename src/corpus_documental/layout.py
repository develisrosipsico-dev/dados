"""Ordem de leitura geométrica conservadora e margens repetidas."""
from collections import Counter
import re
import statistics


def font_size(block):
    sizes = [span["size"] for line in block.get("lines", []) for span in line["spans"]
             for _ in span["text"] if not _.isspace()]
    return statistics.median(sizes) if sizes else 0


def margin_key(page, block):
    y0, y1 = block["bbox"][1], block["bbox"][3]
    edge = "header" if y1 < page["height"] * .12 else "footer" if y0 > page["height"] * .88 else None
    text = block.get("text_raw", "").strip()
    if edge and len(text) <= 160:
        return edge, re.sub(r"\d+", "#", text.casefold())
    return None


def repeated_margins(pages):
    count = Counter(key for page in pages for key in
                    {margin_key(page, b) for b in page["blocks"] if b["type"] == "text"}
                    if key)
    threshold = max(2, (len(pages) + 1) // 2)
    return {key for key, n in count.items() if n >= threshold}


def _column_order(blocks):
    if len(blocks) < 2:
        return blocks
    # Corte vertical apenas em faixa branca que nenhum bloco atravessa.
    intervals = sorted((b["bbox"][0], b["bbox"][2]) for b in blocks)
    right, gaps = intervals[0][1], []
    for left, end in intervals[1:]:
        if left - right >= 12:
            gaps.append((left - right, (left + right) / 2))
        right = max(right, end)
    if gaps:
        _, split = max(gaps)
        left = [b for b in blocks if b["bbox"][2] <= split]
        right = [b for b in blocks if b["bbox"][0] >= split]
        return _column_order(left) + _column_order(right)
    return sorted(blocks, key=lambda b: (round(b["bbox"][1], 1), b["bbox"][0]))


def _physical_fragments(block):
    """Alguns PDFs agrupam linhas de colunas distintas no mesmo objeto nativo."""
    if block["type"] != "text" or not block.get("lines"):
        return [block]
    groups, current, start, offset = [], [], 0, 0
    for line in block["lines"]:
        if current:
            a, b = current[-1]["bbox"], line["bbox"]
            separate = max(a[0], b[0]) - min(a[2], b[2]) > 12
            if separate:
                groups.append((start, offset, current))
                current, start = [], offset
        current.append(line)
        offset += len(line["text"]) + 1
    groups.append((start, len(block["text_raw"]), current))
    fragments = []
    for start, end, lines in groups:
        boxes = [line["bbox"] for line in lines]
        fragments.append({**block, "text_raw": block["text_raw"][start:end], "lines": lines,
                          "source_block_start": start, "source_block_end": end,
                          "char_start": block["char_start"] + start,
                          "bbox": [min(b[0] for b in boxes), min(b[1] for b in boxes),
                                   max(b[2] for b in boxes), max(b[3] for b in boxes)]})
    return fragments


def reading_order(page, audit):
    blocks = [fragment for block in page["blocks"] for fragment in _physical_fragments(block)]
    if not blocks:
        return []
    width = page["width"]
    wide = sorted([b for b in blocks if b["bbox"][2] - b["bbox"][0] > .65 * width],
                  key=lambda b: b["bbox"][1])
    remaining = [b for b in blocks if b not in wide]
    ordered = []
    for anchor in wide:
        before = [b for b in remaining if b["bbox"][3] <= anchor["bbox"][1]]
        ordered.extend(_column_order(before))
        remaining = [b for b in remaining if b not in before]
        ordered.append(anchor)
    ordered.extend(_column_order(remaining))
    if ([(b["block_id"], b.get("source_block_start", 0)) for b in ordered] !=
            [(b["block_id"], b.get("source_block_start", 0)) for b in blocks] or len(blocks) != len(page["blocks"])):
        audit.add("reading_order", "Ordem geométrica por faixas e colunas; revisar layouts complexos.",
                  severity="warning", page_index=page["page_index"],
                  block_order=[b["block_id"] for b in ordered])
    # Não assume que todo layout se torna inequívoco com uma ordenação geométrica.
    rotated = any(tuple(line["direction"]) != (1.0, 0.0)
                  for b in blocks for line in b.get("lines", []))
    if rotated:
        audit.add("rotated_text", "Texto não horizontal exige revisão da ordem de leitura.",
                  severity="warning", page_index=page["page_index"])
    return ordered
