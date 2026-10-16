"""Formatos abertos e publicação local atômica do diretório de saída."""
import json
from pathlib import Path

from .models import canonical


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path, records):
    with Path(path).open("w", encoding="utf-8") as target:
        for record in records:
            target.write(canonical(record) + "\n")


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def load_corpus(path):
    path = Path(path)
    return {"metadata": json.loads((path/"metadata.json").read_text(encoding="utf-8")),
            "pages": read_jsonl(path/"pages_raw.jsonl"),
            "structure": json.loads((path/"structure.json").read_text(encoding="utf-8")),
            "paragraphs": read_jsonl(path/"paragraphs.jsonl"),
            "elements": read_jsonl(path/"elements.jsonl"),
            "events": read_jsonl(path/"processing_log.jsonl")}
