"""Classifica desenhos com geometria válida sem apagar o registro bruto."""
import math

from .models import stable_id


def clip_bbox(box, width, height):
    if len(box) != 4 or not all(math.isfinite(v) for v in box):
        return None
    result = [max(0, box[0]), max(0, box[1]), min(width, box[2]), min(height, box[3])]
    return result if result[0] <= result[2] and result[1] <= result[3] else None


def drawing_elements(page, version, parent_id, audit):
    result = []
    for index, drawing in enumerate(page.get("drawings", [])):
        raw = list(drawing["rect"])
        clipped = clip_bbox(raw, page["width"], page["height"])
        outside = clipped != raw
        white = drawing.get("type") == "f" and all(c >= .99 for c in (drawing.get("fill") or [0]))
        if outside and white and raw[3]-raw[1] > page["height"]:
            kind, reason, status = "layout_artifact", "oversized_white_background_rectangle", "automated"
        elif clipped and clipped[2]-clipped[0] > 20*max(.1, clipped[3]-clipped[1]) and clipped[3]-clipped[1] < 2:
            kind, reason, status = "separator_rule", "thin_horizontal_rule", "automated"
        else:
            kind, reason, status = "vector_graphic_candidate", "unresolved_graphic_requires_review", "review_required"
        result.append({"element_id": stable_id("drawing", version, page["page_index"], index),
                       "kind": kind, "page_index": page["page_index"], "bbox": clipped,
                       "source_bbox": raw, "source_drawing_index": index, "source_spans": [],
                       "parent_id": parent_id, "text_ownership": "none", "quality_status": status,
                       "included_in_figure_structure": False, "geometry_status": "clipped" if outside else "within_page",
                       "classification_reason": reason})
        audit.add("graphic_classification", reason, severity="warning" if status == "review_required" else "info",
                  page_index=page["page_index"], element_id=result[-1]["element_id"], source_bbox=raw,
                  bbox=clipped, source_drawing_index=index, included_in_figure_structure=False)
    return result
