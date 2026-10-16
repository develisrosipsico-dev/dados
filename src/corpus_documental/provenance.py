"""Mapa entre caracteres normalizados, texto composto e intervalos físicos."""


def source_refs(start, end, spans):
    result, cursor = [], 0
    for index, span in enumerate(spans):
        length = span["char_end"]-span["char_start"]
        a, b = max(start, cursor), min(end, cursor+length)
        if a < b:
            result.append({"source_span_index": index, "page_index": span["page_index"],
                           "text_raw_start": a, "text_raw_end": b,
                           "block_id": span["block_id"], "char_start": span["char_start"]+a-cursor,
                           "char_end": span["char_start"]+b-cursor,
                           "block_char_start": span["block_char_start"]+a-cursor,
                           "block_char_end": span["block_char_start"]+b-cursor})
        cursor += length+1
    return result


def make_map(raw, clean, origins, spans):
    runs = []
    for i, (start, end, operation) in enumerate(origins):
        kind = "identity" if end-start == 1 and raw[start:end] == clean[i] else "normalized"
        if runs and runs[-1]["kind"] == kind:
            last = runs[-1]
            contiguous = kind == "identity" and last["text_raw_end"] == start
            same_range = kind == "normalized" and (last["text_raw_start"], last["text_raw_end"]) == (start, end)
            if contiguous or same_range:
                last["clean_end"] = i+1
                if contiguous:
                    last["text_raw_end"] = end
                continue
        runs.append({"clean_start": i, "clean_end": i+1, "text_raw_start": start,
                     "text_raw_end": end, "kind": kind})
    for run in runs:
        run["source_refs"] = source_refs(run["text_raw_start"], run["text_raw_end"], spans)
        if not run["source_refs"]:
            run["kind"] = "composition_separator"
    return runs


def validate_map(unit):
    errors, cursor = [], 0
    for run in unit.get("normalization_map", []):
        a, b = run["text_raw_start"], run["text_raw_end"]
        if run["clean_start"] != cursor or not cursor < run["clean_end"] <= len(unit["text_clean"]):
            errors.append("normalization_map_coverage")
        if not 0 <= a < b <= len(unit["text_raw"]):
            errors.append("normalization_map_raw_range")
        if run.get("source_refs") != source_refs(a, b, unit["source_spans"]):
            errors.append("normalization_map_source")
        if run["kind"] == "identity" and unit["text_raw"][a:b] != unit["text_clean"][cursor:run["clean_end"]]:
            errors.append("normalization_map_identity")
        if run["kind"] not in {"identity", "normalized", "composition_separator"}:
            errors.append("normalization_map_kind")
        cursor = run["clean_end"]
    if cursor != len(unit["text_clean"]):
        errors.append("normalization_map_coverage")
    return sorted(set(errors))
