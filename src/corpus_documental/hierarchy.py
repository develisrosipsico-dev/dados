"""Evidências tipográficas locais para PDFs sem marcadores de navegação."""
import re
from collections import Counter

from .layout import font_size


def fonts(block):
    return tuple(sorted({s["font"] for l in block.get("lines", []) for s in l["spans"]}))


def layout_hints(pages, metrics):
    hints = {}
    for page in pages:
        text = sorted([b for b in page["blocks"] if b["type"] == "text"], key=lambda b: (b["bbox"][1], b["bbox"][0]))
        for i, number in enumerate(text[:-1]):
            title = text[i+1]
            n, t = number["text_raw"].strip(), title["text_raw"].strip()
            if (re.fullmatch(r"\d+", n) and font_size(number) >= metrics["size"]*1.5
                    and number["bbox"][1] < page["height"]*.3
                    and abs((number["bbox"][0]+number["bbox"][2])/2-page["width"]/2) < page["width"]*.12
                    and 0 <= title["bbox"][1]-number["bbox"][3] < page["height"]*.2
                    and len(t) > 3 and t.isupper() and fonts(number) == fonts(title)
                    and abs(font_size(number)-font_size(title)) < .7):
                evidence = {"type": "chapter_number_and_display_title", "number": n,
                            "number_block_id": number["block_id"], "title_block_id": title["block_id"],
                            "page_index": page["page_index"], "font_names": fonts(title)}
                hints[number["block_id"]] = {"kind": "chapter", "level": 2, "number_only": True, "evidence": evidence}
                hints[title["block_id"]] = {"kind": "chapter", "level": 2, "evidence": evidence}
    styles = Counter((round(font_size(b), 1), fonts(b)) for p in pages for b in p["blocks"]
                     if b["type"] == "text" and len(b["text_raw"].strip()) > 3 and b["text_raw"].strip().isupper()
                     and font_size(b) >= metrics["size"]*1.25)
    for page in pages:
        for block in page["blocks"]:
            if block["type"] != "text" or block["block_id"] in hints:
                continue
            t, size = block["text_raw"].strip(), font_size(block)
            style = round(size, 1), fonts(block)
            if (len(t) > 3 and len(t) < 180 and size >= metrics["size"]*1.25
                    and abs(block["bbox"][0]-metrics["left"]) < 15):
                if t.isupper() and styles[style] >= 2:
                    hints[block["block_id"]] = {"kind": "section", "level": 3, "provisional": True,
                        "evidence": {"type": "recurring_section_typography", "font_names": fonts(block), "size": size, "occurrences": styles[style]}}
                elif not t.isupper() and any("Bold" in f for f in fonts(block)):
                    hints[block["block_id"]] = {"kind": "subsection", "level": 4, "provisional": True,
                        "evidence": {"type": "contrasting_bold_heading", "font_names": fonts(block), "size": size}}
    return hints
