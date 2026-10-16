"""Coordenação do processamento de um recorte explícito, sem alterar a fonte."""
import os
import hashlib
from pathlib import Path
import shutil
import tempfile

import pymupdf

from . import __version__
from .audit import Audit
from .extraction import extract_pages
from .ingest import register, sha256
from .models import stable_id
from .storage import write_json, write_jsonl
from .structure import build_structure
from .validation import validate


def process(source, output, config):
    source, output = Path(source).resolve(), Path(output).absolute()
    if output.exists():
        raise FileExistsError("A saída já existe. Use outro diretório para preservar versões e arquivos.")
    metadata = register(source, config)
    audit = Audit()
    audit.add("source_registered", "Fonte registrada por SHA-256.", sha256=metadata["sha256"])
    pages = extract_pages(source, config, audit)
    ocr_models = {}
    if any("native_extraction" in p for p in pages):
        try:
            tessdata = Path(pymupdf.get_tessdata())
            ocr_models = {language: sha256(tessdata/f"{language}.traineddata")
                          if (tessdata/f"{language}.traineddata").is_file() else None
                          for language in config.ocr_language.split("+")}
        except (RuntimeError, OSError):
            ocr_models = {language: None for language in config.ocr_language.split("+")}
    implementation = hashlib.sha256()
    for module in sorted(Path(__file__).parent.glob("*.py")):
        implementation.update(module.name.encode() + b"\0" + module.read_bytes())
    implementation_digest = implementation.hexdigest()
    version = stable_id("corpus", metadata["sha256"], config.to_dict(), __version__,
                        implementation_digest, pymupdf.VersionBind, ocr_models)
    metadata.update(corpus_version=version, processing={"application_version": __version__,
                    "pymupdf_version": pymupdf.VersionBind, "ocr_model_sha256": ocr_models,
                    "implementation_sha256": implementation_digest,
                    "config": config.to_dict()},
                    identity_policy="IDs deterministic within corpus version; source/configuration/implementation/tool changes create a new version")
    structure, paragraphs, elements = build_structure(pages, metadata, version, config, audit)
    warning_units = {e["unit_id"] for e in audit.events if e["severity"] != "info" and "unit_id" in e}
    warning_pages = {e["page_index"] for e in audit.events if e["severity"] != "info" and "page_index" in e}
    for unit in paragraphs + elements:
        if (unit.get("paragraph_id", unit.get("element_id")) in warning_units or
                any(s["page_index"] in warning_pages for s in unit["source_spans"])):
            unit["quality_status"] = "review_required"
    metadata["source_characteristics"] = {"scope": "selected_pages_only",
                                           "by_page": [{"page_index": p["page_index"], "kind": p.get("source_kind", "unknown"),
                                                        "method": p["method"]} for p in pages]}
    report = validate(metadata, pages, structure, paragraphs, elements, audit.events)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".corpus-", dir=output.parent))
    try:
        shutil.copyfile(source, staging/"original.pdf")
        if sha256(staging/"original.pdf") != metadata["sha256"] or sha256(source) != metadata["sha256"]:
            raise RuntimeError("A fonte mudou durante o processamento; saída descartada.")
        write_json(staging/"metadata.json", metadata)
        write_json(staging/"structure.json", structure)
        write_json(staging/"validation_report.json", report)
        for name, records in [("pages_raw", pages), ("paragraphs", paragraphs),
                              ("elements", elements), ("processing_log", audit.events)]:
            write_jsonl(staging/f"{name}.jsonl", records)
        # Sem sobrescrita intencional; cada execução usa um novo diretório.
        if output.exists():
            raise FileExistsError(output)
        os.rename(staging, output)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return report
