"""Ordem de leitura geométrica conservadora e margens repetidas."""
from collections import Counter
import re
import statistics


def font_size(block):
    sizes = [span["size"] for line in block.get("lines", []) for span in line["spans"]
             for _ in span["text"] if not _.isspace()]
    return statistics.median(sizes) if sizes else 0


def same_visual_line(first, second):
    """Caixas alinhadas verticalmente; não confunde a próxima linha do corpo."""
    if any(tuple(line.get("direction", (1, 0))) != (1, 0) for line in (first, second)):
        return False
    a, b = first["bbox"], second["bbox"]
    overlap = min(a[3], b[3]) - max(a[1], b[1])
    small_height = max(1, min(a[3]-a[1], b[3]-b[1]))
    return overlap >= .7 * small_height and abs(a[3]-b[3]) <= .35 * max(a[3]-a[1], b[3]-b[1])


def _persistent_gutter(lines, split):
    # Um gutter entre colunas se repete em várias linhas e não é atravessado
    # pelas linhas largas do mesmo parágrafo, ao contrário da justificação.
    if any(line["bbox"][0] < split < line["bbox"][2] for line in lines):
        return False
    sides = ([line for line in lines if line["bbox"][2] <= split],
             [line for line in lines if line["bbox"][0] >= split])
    for side in sides:
        rows = []
        for line in sorted(side, key=lambda item: item["bbox"][1]):
            if not any(same_visual_line(line, row) for row in rows):
                rows.append(line)
        if len(rows) < 2:
            return False
    return True


def is_inline_continuation(first, second, lines=()):
    """Evidência geométrica de palavras da mesma linha, sem apagar a extração."""
    if not same_visual_line(first, second):
        return False
    gap = second["bbox"][0] - first["bbox"][2]
    size = max(font_size({"lines": [first]}), font_size({"lines": [second]}), 1)
    bridge = any(l["bbox"][0] <= first["bbox"][2] and l["bbox"][2] >= second["bbox"][0]
                 and not same_visual_line(l, first) for l in lines)
    if not -1 <= gap <= (4 if bridge else 2) * size:
        return False
    if re.match(r"^\s*(?:[•●▪◦–—-]|\d+[.)]|[A-Za-z][.)])\s+", second["text"]):
        return False
    split = (first["bbox"][2] + second["bbox"][0]) / 2
    return not _persistent_gutter(lines, split)


def inline_connections(block):
    """Offsets nativos das linhas adjacentes que pertencem à mesma linha visual."""
    lines = block.get("lines", [])
    starts, offset = [], 0
    for line in lines:
        starts.append(offset)
        offset += len(line["text"]) + 1
    return [(starts[i-1], starts[i]) for i in range(1, len(lines))
            if is_inline_continuation(lines[i-1], lines[i], lines)]


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


def _ordered_lines(lines):
    from .composition import visual_rows
    intervals = sorted((l["bbox"][0], l["bbox"][2]) for l in lines)
    if intervals:
        right = intervals[0][1]
        for left, end in intervals[1:]:
            split = (left+right)/2
            if left-right >= 12 and _persistent_gutter(lines, split):
                return (_ordered_lines([l for l in lines if l["bbox"][2] <= split]) +
                        _ordered_lines([l for l in lines if l["bbox"][0] >= split]))
            right = max(right, end)
    return [line for row in visual_rows(lines) for line in row]


def _physical_fragments(block):
    """Alguns PDFs agrupam linhas de colunas distintas no mesmo objeto nativo."""
    if block["type"] != "text" or not block.get("lines"):
        return [block]
    from .composition import make_segment
    native, offset = [], 0
    for i, line in enumerate(block["lines"]):
        end = offset+len(line["text"])+(i+1 < len(block["lines"]))
        native.append({**line, "_source_start": offset, "_source_end": end})
        offset = end
    groups, current = [], []
    for line in _ordered_lines(native):
        if current:
            a, b = current[-1]["bbox"], line["bbox"]
            separate = (max(a[0], b[0]) - min(a[2], b[2]) > 12
                        and not is_inline_continuation(current[-1], line, block["lines"]))
            if separate and not same_visual_line(current[-1], line) and b[1] >= a[1]:
                split = (max(a[0], b[0])+min(a[2], b[2]))/2
                separate = _persistent_gutter(block["lines"], split)
            if separate:
                groups.append(current)
                current = []
        current.append(line)
    groups.append(current)
    return [make_segment(block, group) for group in groups]


def reading_order(page, audit):
    for block in page["blocks"]:
        connections = inline_connections(block)
        if connections:
            audit.add("inline_line_reconstruction", "Objetos alinhados da mesma linha visual mantidos no fluxo do parágrafo.",
                      page_index=page["page_index"], block_id=block["block_id"],
                      native_line_starts=connections)
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
