"""Registro da fonte: nenhuma inferência bibliográfica a partir do nome."""
import hashlib
from pathlib import Path

import pymupdf

from .models import stable_id


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as source:
        for data in iter(lambda: source.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def register(path, config):
    path = Path(path)
    digest = sha256(path)
    with pymupdf.open(path) as pdf:
        if not pdf.is_pdf:
            raise ValueError("A fonte precisa ser um PDF.")
        if pdf.needs_pass:
            raise ValueError("PDF criptografado: forneça uma cópia autorizada acessível.")
        config.validate(len(pdf))
        supplied = {k: v for k, v in (pdf.metadata or {}).items() if v}
        labels = pdf.get_page_labels()
        outline = [{"outline_index": i, "level": level, "title": title, "page_index": page-1}
                   for i, (level, title, page) in enumerate(pdf.get_toc()) if page > 0]
        total = len(pdf)
        evidence = {}
        for field, item in (config.bibliographic_evidence or {}).items():
            if field not in {"title", "author", "edition", "publisher", "year"}:
                raise ValueError(f"Campo bibliográfico desconhecido: {field}")
            if not isinstance(item, dict) or not {"value", "page_index", "quote"} <= item.keys():
                raise ValueError("Evidência bibliográfica exige value, page_index e quote.")
            index = item["page_index"]
            if not isinstance(index, int) or not 0 <= index < total:
                raise ValueError("Página de evidência bibliográfica inválida.")
            text = pdf[index].get_text(sort=False)
            quote = item["quote"]
            if not isinstance(quote, str) or not quote or quote not in text or str(item["value"]) not in quote:
                raise ValueError(f"Evidência bibliográfica não conferida na fonte: {field}")
            offset = text.index(quote)
            evidence[field] = {**item, "char_start": offset, "char_end": offset+len(quote),
                               "extraction_method": "PyMuPDF page.get_text(sort=False)",
                               "verification": "curated field; exact quote checked against PDF"}
    result = {
        "schema_version": "1.0", "file_id": f"sha256:{digest}", "sha256": digest,
        "document_id": config.document_id or stable_id("doc", digest),
        "filename": path.name, "page_count": total,
        "bibliographic": {
            "title": supplied.get("title"), "author": supplied.get("author"),
            "edition": None, "publisher": None, "year": None,
            "provenance": "PDF metadata unless bibliographic_evidence specifies a checked source excerpt",
        },
        "pdf_metadata": supplied, "pdf_page_label_rules": labels,
        "pdf_outline": outline,
        "bibliographic_evidence": evidence,
        "selected_pages": list(config.pages),
        "out_of_scope_pages": [i for i in range(total) if i not in config.pages],
        "page_index_convention": "zero-based physical PDF index",
        "character_offsets": "Unicode code points, half-open [start,end); pages_raw.text_raw",
    }
    for field, item in evidence.items():
        result["bibliographic"][field] = item["value"]
    return result
