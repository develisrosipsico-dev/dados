"""Contratos de execução e identidade, sem estado global."""
from dataclasses import asdict, dataclass
import hashlib
import json
import re


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_id(prefix, *parts):
    digest = hashlib.sha256(canonical(parts).encode()).hexdigest()[:24]
    return f"{prefix}_{digest}"


@dataclass(frozen=True)
class Config:
    # Índices físicos base zero; seleção obrigatória, nunca livro inteiro implícito.
    pages: tuple[int, ...]
    ocr: str = "auto"
    ocr_language: str = "por"
    ocr_dpi: int = 300
    join_hyphens: bool = False
    merge_pages: bool = False
    document_id: str | None = None
    bibliographic_evidence: dict | None = None

    def validate(self, total_pages):
        if not self.pages or tuple(sorted(set(self.pages))) != self.pages:
            raise ValueError("Selecione páginas únicas, crescentes e não vazias.")
        if self.pages[0] < 0 or self.pages[-1] >= total_pages:
            raise ValueError("Página fora dos limites do PDF.")
        if self.ocr not in {"auto", "never", "always"}:
            raise ValueError("OCR deve ser auto, never ou always.")
        if self.ocr_dpi < 72:
            raise ValueError("Resolução de OCR deve ser >= 72 dpi.")
        if not re.fullmatch(r"[A-Za-z0-9_]+(?:\+[A-Za-z0-9_]+)*", self.ocr_language):
            raise ValueError("Idiomas OCR devem usar nomes como por ou por+eng.")
        if self.bibliographic_evidence is not None and not isinstance(self.bibliographic_evidence, dict):
            raise ValueError("Evidências bibliográficas devem ser um objeto JSON por campo.")

    def to_dict(self):
        return asdict(self)
