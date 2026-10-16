"""Integridade física e rastreabilidade; não atestam segmentação documental."""
from copy import deepcopy
from pathlib import Path

import pytest

from corpus_documental.ingest import sha256
from corpus_documental.models import stable_id
from corpus_documental.pipeline import process
from corpus_documental.provenance import validate_map
from corpus_documental.validation import validate_corpus


def test_reused_raw_and_source_are_byte_identical(reviewed_story):
    fixture = reviewed_story
    output, previous = fixture["output"], fixture["previous"]
    assert (output/"pages_raw.jsonl").read_bytes() == (previous/"pages_raw.jsonl").read_bytes()
    assert (output/"original.pdf").read_bytes() == fixture["source"].read_bytes()
    assert fixture["report"]["raw_integrity"]["status"] == "passed"
    assert fixture["report"]["raw_integrity"]["raw_reconstruction_matches"]
    assert fixture["report"]["metrics"]["block_coverage_ratio"] == 1
    for filename in ("metadata.json", "structure.json", "paragraphs.jsonl", "elements.jsonl", "processing_log.jsonl", "validation_report.json"):
        assert (output/"history"/filename).read_bytes() == (previous/filename).read_bytes()


def test_every_primary_source_interval_has_one_owner_and_exact_raw(reviewed_story):
    data = reviewed_story["data"]
    page_map = {p["page_index"]: p for p in data["pages"]}
    units = data["paragraphs"]+[e for e in data["elements"] if e.get("text_ownership") == "primary"]
    ownership = {}
    for unit in units:
        assert validate_map(unit) == []
        parts = []
        for span in unit["source_spans"]:
            page = page_map[span["page_index"]]
            block = next(b for b in page["blocks"] if b["block_id"] == span["block_id"])
            a, b = span["block_char_start"], span["block_char_end"]
            raw = page["text_raw"][span["char_start"]:span["char_end"]]
            assert raw == block["text_raw"][a:b]
            parts.append(raw)
            ownership.setdefault((span["page_index"], span["block_id"]), []).append((a, b))
        assert unit["text_raw"] == "\n".join(parts)
    for page in data["pages"]:
        for block in page["blocks"]:
            if block["type"] == "text":
                cursor = 0
                for a, b in sorted(ownership[(page["page_index"], block["block_id"])]):
                    assert a == cursor
                    cursor = b
                assert cursor == len(block["text_raw"])


def test_provenance_map_tracks_selected_words_into_pdf(reviewed_story):
    data = reviewed_story["data"]
    paragraph = next(p for p in data["paragraphs"] if "pega acidentalmente aquela-coisa" in p["text_clean"])
    start = paragraph["text_clean"].index("acidentalmente")
    end = start+len("acidentalmente")
    recovered = ""
    for run in paragraph["normalization_map"]:
        a, b = max(start, run["clean_start"]), min(end, run["clean_end"])
        if a < b:
            assert run["kind"] == "identity"
            raw_start = run["text_raw_start"]+a-run["clean_start"]
            recovered += paragraph["text_raw"][raw_start:raw_start+b-a]
            assert any(ref["page_index"] == 12 for ref in run["source_refs"])
    assert recovered == "acidentalmente"


def test_revision_is_repeatable_without_overwriting_history(reviewed_story, tmp_path):
    fixture = reviewed_story
    output = tmp_path/"repeat"
    process(fixture["source"], output, fixture["config"], raw_pages_path=fixture["previous"]/"pages_raw.jsonl")
    for file in fixture["output"].rglob("*"):
        if file.is_file():
            assert file.read_bytes() == (output/file.relative_to(fixture["output"])).read_bytes()


def test_wrong_raw_source_binding_is_rejected(reviewed_story, tmp_path):
    import json
    previous = reviewed_story["previous"]
    bad = tmp_path/"wrong"; bad.mkdir()
    (bad/"pages_raw.jsonl").write_bytes((previous/"pages_raw.jsonl").read_bytes())
    metadata = json.loads((previous/"metadata.json").read_text())
    metadata["sha256"] = "0"*64
    (bad/"metadata.json").write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="outro PDF"):
        process(reviewed_story["source"], tmp_path/"invalid", reviewed_story["config"], raw_pages_path=bad/"pages_raw.jsonl")


def test_raw_hash_tampering_closes_gate(reviewed_story, tmp_path):
    import shutil
    output = tmp_path/"tampered"
    shutil.copytree(reviewed_story["output"], output)
    with (output/"pages_raw.jsonl").open("a") as target:
        target.write("\n")  # Conteúdo JSON equivalente, bytes diferentes.
    report = validate_corpus(output)
    assert report["status"] == "blocked"
    assert report["raw_integrity"]["status"] == "failed"
    assert not report["chunking_gate"]["allowed"]
    assert any(e["code"] == "raw_artifact_hash_mismatch" for e in report["checks"]["errors"])


def test_second_incremental_revision_preserves_and_validates_nested_history(reviewed_story, tmp_path):
    output = tmp_path/"second-revision"
    process(reviewed_story["source"], output, reviewed_story["config"], raw_pages_path=reviewed_story["output"]/"pages_raw.jsonl")
    assert (output/"history/previous_history/processing_log.jsonl").read_bytes() == (reviewed_story["previous"]/"processing_log.jsonl").read_bytes()
    assert validate_corpus(output)["checks"]["errors"] == []
    (output/"history/previous_history/processing_log.jsonl").write_text("adulterado")
    report = validate_corpus(output)
    assert report["status"] == "blocked"
    assert any(e["code"] == "history_artifact_hash_mismatch" for e in report["checks"]["errors"])
