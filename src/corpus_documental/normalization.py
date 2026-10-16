"""Transformações reversíveis por registro explícito de antes e depois."""
import re
import unicodedata


def normalize(raw, config, audit, unit_id):
    text, changes = raw, []

    def apply(operation, updated):
        nonlocal text
        if updated != text:
            changes.append({"operation": operation, "before": text, "after": updated})
            audit.add("normalization", operation, unit_id=unit_id,
                      before=text, after=updated)
            text = updated

    apply("unicode_nfc", unicodedata.normalize("NFC", text))
    if re.search(r"\w-\n\w", text):
        audit.add("hyphenation_candidate", "Hífen de fim de linha pode ser lexical ou de diagramação.",
                  severity="warning", unit_id=unit_id)
        if config.join_hyphens:
            apply("join_line_end_hyphen_explicit_option", re.sub(r"(?<=\w)-\n(?=\w)", "", text))
    apply("join_layout_lines", text.replace("\n", " "))
    apply("trim_boundary_whitespace", text.strip())
    if "\ufffd" in text or any(unicodedata.category(c) == "Cc" and c not in "\t" for c in text):
        audit.add("suspect_characters", "Caracteres suspeitos preservados para revisão.",
                  severity="warning", unit_id=unit_id)
    return text, changes
