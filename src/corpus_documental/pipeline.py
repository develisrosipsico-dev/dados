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
from .storage import write_json, write_jsonl, read_jsonl
from .models import canonical
import json
from .structure import build_structure
from .validation import validate


def process(source, output, config, *, raw_pages_path=None):
    source, output = Path(source).resolve(), Path(output).absolute()
    if output.exists():
        raise FileExistsError("A saída já existe. Use outro diretório para preservar versões e arquivos.")
    metadata = register(source, config)
    audit = Audit()
    audit.add("source_registered", "Fonte registrada por SHA-256.", sha256=metadata["sha256"])
    previous = None
    if raw_pages_path is not None:
        raw_pages_path = Path(raw_pages_path)
        previous_path = raw_pages_path.parent/"metadata.json"
        if not previous_path.is_file():
            raise ValueError("Reuso do bruto exige metadata.json adjacente para conferir a identidade da fonte.")
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
        if previous.get("sha256") != metadata["sha256"]:
            raise ValueError("A extração bruta pertence a outro PDF; SHA-256 divergente.")
        pages = read_jsonl(raw_pages_path)
        if [p["page_index"] for p in pages] != list(config.pages):
            raise ValueError("A seleção de páginas deve coincidir com a extração bruta reutilizada.")
        audit.add("raw_extraction_reused", "Extração existente reutilizada sem reescrita.", raw_sha256=sha256(raw_pages_path),
                  previous_corpus_version=previous.get("corpus_version"))
    else:
        pages = extract_pages(source, config, audit)
    raw_digest = sha256(raw_pages_path) if raw_pages_path else hashlib.sha256(("".join(canonical(p)+"\n" for p in pages)).encode()).hexdigest()
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
                        implementation_digest, pymupdf.VersionBind, ocr_models, raw_digest)
    metadata.update(corpus_version=version, processing={"application_version": __version__,
                    "pymupdf_version": pymupdf.VersionBind, "ocr_model_sha256": ocr_models,
                    "implementation_sha256": implementation_digest,
                    "raw_pages_sha256": raw_digest,
                    "config": config.to_dict()},
                    identity_policy="IDs deterministic within corpus version; source/configuration/implementation/tool changes create a new version")
    metadata["schema_version"] = "1.1"
    metadata["source_context"] = config.source_context
    if previous:
        metadata["previous_corpus_version"] = previous.get("corpus_version")
    structure, paragraphs, elements = build_structure(pages, metadata, version, config, audit)
    extraction_codes = {"ocr_applied", "ocr_failed", "no_text", "ocr_required", "page_extraction_failed", "rotated_text"}
    warning_pages = {e["page_index"] for e in audit.events if e["severity"] != "info" and e["code"] in extraction_codes and "page_index" in e}
    node_map = {n["node_id"]: n for n in structure["nodes"]}
    for unit in paragraphs + elements:
        identifier = unit.get("element_id", unit.get("paragraph_id"))
        warnings = [e for e in audit.events if e["severity"] != "info" and e.get("unit_id") == identifier
                    and not (e["code"] == "classification_review" and unit.get("classification_resolved_by"))]
        parent, inherited, visited = unit.get("parent_id"), False, set()
        while parent in node_map and parent not in visited:
            visited.add(parent)
            inherited |= node_map[parent].get("quality_status") == "review_required"
            parent = node_map[parent]["parent_id"]
        if unit.get("text_ownership") in {"none", "derived", "reference"}:
            inherited = False
        if unit.get("classification_resolved_by") == "explicit_visual_text_layer_review":
            inherited = False
        unit["hierarchy_review_required"] = inherited
        if (warnings or inherited or
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
        if raw_pages_path:
            shutil.copyfile(raw_pages_path, staging/"pages_raw.jsonl")
            history = staging/"history"
            history.mkdir()
            manifest = {}
            for filename in ("metadata.json", "structure.json", "paragraphs.jsonl", "elements.jsonl", "processing_log.jsonl", "validation_report.json"):
                file = raw_pages_path.parent/filename
                if file.is_file():
                    shutil.copyfile(file, history/filename)
                    manifest[filename] = sha256(file)
            if (raw_pages_path.parent/"history").is_dir():
                shutil.copyfile(raw_pages_path, history/"pages_raw.jsonl")
                shutil.copytree(raw_pages_path.parent/"history", history/"previous_history")
            manifest["../pages_raw.jsonl"] = raw_digest
            write_json(history/"manifest.json", manifest)
        else:
            write_jsonl(staging/"pages_raw.jsonl", pages)
        if sha256(staging/"pages_raw.jsonl") != raw_digest:
            raise RuntimeError("A extração bruta foi alterada durante a reconstrução.")
        write_json(staging/"metadata.json", metadata)
        write_json(staging/"structure.json", structure)
        write_json(staging/"validation_report.json", report)
        for name, records in [("paragraphs", paragraphs),
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
