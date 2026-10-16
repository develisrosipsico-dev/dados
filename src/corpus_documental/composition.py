"""Composição geométrica sem alterar linhas, blocos ou offsets nativos."""
import statistics
import re


def bounds(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def body_metrics(pages):
    from .layout import font_size
    candidates = [b for p in pages for b in p["blocks"] if b["type"] == "text" and len(b["text_raw"]) > 80]
    if not candidates:
        candidates = [b for p in pages for b in p["blocks"] if b["type"] == "text"]
    size = statistics.median([font_size(b) for b in candidates]) if candidates else 12
    body = [b for b in candidates if abs(font_size(b)-size) < .7]
    return {"size": size, "left": statistics.median([b["bbox"][0] for b in body]) if body else 0,
            "right": statistics.median([b["bbox"][2] for b in body]) if body else 612}


def visual_rows(lines):
    from .layout import same_visual_line
    rows = []
    for line in sorted(lines, key=lambda l: (l["bbox"][1], l["bbox"][0])):
        row = next((r for r in rows if same_visual_line(r[0], line)), None)
        if row is None:
            rows.append([line])
        else:
            row.append(line)
    return [sorted(row, key=lambda l: l["bbox"][0]) for row in rows]


def coalesce(pieces):
    result = []
    for start, end in pieces:
        if result and result[-1][1] == start:
            result[-1] = (result[-1][0], end)
        else:
            result.append((start, end))
    return result


def make_segment(block, lines):
    native = block.get("_native_block", block)
    pieces = coalesce([(l["_source_start"], l["_source_end"]) for l in lines])
    return {**block, "lines": lines, "bbox": bounds([l["bbox"] for l in lines]),
            "text_raw": "\n".join(native["text_raw"][a:b] for a, b in pieces),
            "source_pieces": pieces, "_native_block": native,
            "source_block_start": pieces[0][0], "source_block_end": pieces[-1][1]}


def paragraph_break(previous, current, metrics, all_rows):
    from .layout import font_size, same_visual_line
    if same_visual_line(previous[0], current[0]):
        return None
    a, b = bounds([l["bbox"] for l in previous]), bounds([l["bbox"] for l in current])
    size_a, size_b = font_size({"lines": previous}), font_size({"lines": current})
    if b[1]-a[3] > .8*max(1, a[3]-a[1]):
        return "vertical_spacing"
    if abs(size_a-size_b) > 1.5:
        return "typographic_boundary"
    local_left = min(l["bbox"][0] for row in all_rows for l in row)
    if abs(size_b-metrics["size"]) < 1:
        local_left = min(local_left, metrics["left"])
    right = max(l["bbox"][2] for row in all_rows for l in row)
    text = " ".join(l["text"].strip() for l in previous)
    if (b[0]-local_left >= max(8, .75*size_b) and right-a[2] >= 1.5*size_b
            and re.search(r'[.!?][\"”’»)]*$', text)):
        return "first_line_indent_after_short_terminal_line"
    return None


def paragraph_segments(block, metrics):
    rows = visual_rows(block["lines"])
    # Preserva a ordem por coluna já resolvida pelo layout; cada fragmento contém uma coluna.
    groups, current, decisions = [], [], []
    for row in rows:
        reason = paragraph_break(current[-1], row, metrics, rows) if current else None
        if reason:
            groups.append([line for r in current for line in r])
            decisions.append({"reason": reason, "native_start": row[0]["_source_start"]})
            current = []
        current.append(row)
    if current:
        groups.append([line for r in current for line in r])
    return [make_segment(block, lines) for lines in groups], decisions
