"""Normalização auditada; cada caractere limpo mantém sua origem bruta."""
import re
import unicodedata


from .provenance import make_map


def normalize_document(raw, config, audit, unit_id, source_spans=(), word_evidence=()):
    text, changes = raw, []
    origins = [(i, i+1, "identity") for i in range(len(raw))]

    def edits(operation, replacements):
        nonlocal text
        before, deleted = text, []
        for start, end, replacement in sorted(replacements, reverse=True):
            if text[start:end] == replacement:
                continue
            old = origins[start:end]
            a, b = min(o[0] for o in old), max(o[1] for o in old)
            if not replacement:
                deleted.append([a, b])
            text = text[:start]+replacement+text[end:]
            origins[start:end] = [(a, b, operation)]*len(replacement)
        if text != before:
            change = {"operation": operation, "before": before, "after": text}
            if deleted:
                change["deleted_text_raw_ranges"] = sorted(deleted)
            changes.append(change)
            audit.add("normalization", operation, unit_id=unit_id, before=before, after=text,
                      deleted_text_raw_ranges=sorted(deleted))

    clusters, start = [], 0
    for i in range(1, len(text)+1):
        if i == len(text) or not unicodedata.combining(text[i]):
            part = text[start:i]
            if unicodedata.normalize("NFC", part) != part:
                clusters.append((start, i, unicodedata.normalize("NFC", part)))
            start = i
    edits("unicode_nfc", clusters)
    if text != unicodedata.normalize("NFC", text):
        edits("unicode_nfc_cluster", [(0, len(text), unicodedata.normalize("NFC", text))])
    edits("reuse_existing_line_boundary_space", [(m.start(), m.end(), "") for m in re.finditer(r"(?<=[ \t])\n(?=\S)", text)])
    reviewed_forms = {form.casefold() for form in config.reviewed_line_hyphens}
    reviewed = []
    for match in re.finditer(r"([\wÀ-ÿ]+)-[ \t]*\n+(\w+(?:-\w+)*)", text):
        prefix = re.search(r"[\w-]+$", text[:match.start()+len(match[1])])
        retained = (prefix[0] if prefix else match[1])+"-"+match[2]
        if retained.casefold() in reviewed_forms:
            reviewed.append((match.start()+len(match[1])+1, match.end()-len(match[2]), ""))
            audit.add("reviewed_hyphen_preserved",
                      "Quebra visual removida em forma revisada; hífen lexical preservado.",
                      unit_id=unit_id, candidate=match[0], reviewed_form=retained)
    edits("join_reviewed_hyphen_layout", reviewed)

    safe, lexical, evidence = [], [], {w.casefold() for w in word_evidence}
    for match in re.finditer(r"([\wÀ-ÿ]+)-[ \t]*\n+(\w+)", text):
        joined = match[1]+match[2]
        compound = match.start() > 0 and text[match.start()-1] == "-"
        prefix = re.search(r"[\w-]+$", text[:match.start()+len(match[1])])
        retained = (prefix[0] if prefix else match[1])+"-"+match[2]
        if retained.casefold() in evidence:
            lexical.append((match.start()+len(match[1])+1, match.end()-len(match[2]), ""))
            audit.add("lexical_hyphen_preserved", "Quebra removida mantendo o hífen; forma exata corroborada no bruto.",
                      unit_id=unit_id, corroborating_form=retained)
            continue
        corroborated = joined.casefold() in evidence and not compound and match[2].casefold() not in {"se", "me", "te", "lhe", "lo", "la", "nos"}
        applied = bool(config.join_hyphens and corroborated)
        audit.add("hyphenation_candidate", "Junção autorizada e corroborada; confirmar graficamente." if applied else "Hífen preservado; diagramação e grafia lexical exigem revisão.",
                  severity="warning", unit_id=unit_id,
                  candidate=match[0], joined_candidate=joined, corroborated=corroborated, applied=applied)
        if applied:
            safe.append((match.start()+len(match[1]), match.end()-len(match[2]), ""))
    edits("join_corroborated_hyphen_layout", safe+lexical)
    edits("join_layout_lines", [(m.start(), m.end(), " ") for m in re.finditer(r"[ \t]*\n[ \t\n]*", text)])
    if text and not text.strip():
        edits("trim_boundary_whitespace", [(0, len(text), "")])
    else:
        replacements = []
        left, right = len(text)-len(text.lstrip()), len(text.rstrip())
        if left:
            replacements.append((0, left, ""))
        if right < len(text):
            replacements.append((right, len(text), ""))
        edits("trim_boundary_whitespace", replacements)
    if "\ufffd" in text or any(unicodedata.category(c) == "Cc" and c not in "\t" for c in text):
        audit.add("suspect_characters", "Caracteres suspeitos preservados para revisão.",
                  severity="warning", unit_id=unit_id)
    return text, changes, make_map(raw, text, origins, source_spans)


def normalize(raw, config, audit, unit_id):
    text, changes, _ = normalize_document(raw, config, audit, unit_id)
    return text, changes
