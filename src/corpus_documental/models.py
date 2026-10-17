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
    reviewed_line_hyphens: tuple[str, ...] = ()
    editorial_amendments: tuple[str, ...] = ()
    reviewed_text_layer_mismatches: tuple[str, ...] = ()
    merge_pages: bool = False
    document_id: str | None = None
    bibliographic_evidence: dict | None = None
    source_context: dict | None = None

    def validate(self, total_pages):
        if not self.pages or tuple(sorted(set(self.pages))) != self.pages:
            raise ValueError("Selecione páginas únicas, crescentes e não vazias.")
        if self.pages[0] < 0 or self.pages[-1] >= total_pages:
            raise ValueError("Página fora dos limites do PDF.")
        if self.ocr not in {"auto", "never", "always"}:
            raise ValueError("OCR deve ser auto, never ou always.")
        if self.ocr_dpi < 72:
            raise ValueError("Resolução de OCR deve ser >= 72 dpi.")
        if (len(set(self.reviewed_line_hyphens)) != len(self.reviewed_line_hyphens)
                or any(not re.fullmatch(r"[\wÀ-ÿ]+(?:-[\wÀ-ÿ]+)+", form)
                       for form in self.reviewed_line_hyphens)):
            raise ValueError("Hifenizações revisadas devem ser formas únicas como revela-se.")
        if (len(set(self.editorial_amendments)) != len(self.editorial_amendments)
                or any("=" not in item or not all(part.strip() for part in item.split("=", 1))
                       for item in self.editorial_amendments)):
            raise ValueError("Emendas editoriais devem usar a forma DOCUMENTAL=PROPOSTA.")
        if (len(set(self.reviewed_text_layer_mismatches)) != len(self.reviewed_text_layer_mismatches)
                or any(not re.fullmatch(r"p\d{6}_b\d{5}=[a-z][a-z0-9_]*", item)
                       for item in self.reviewed_text_layer_mismatches)):
            raise ValueError("Incompatibilidades visuais revisadas devem usar BLOCO=SUBTIPO.")
        if not re.fullmatch(r"[A-Za-z0-9_]+(?:\+[A-Za-z0-9_]+)*", self.ocr_language):
            raise ValueError("Idiomas OCR devem usar nomes como por ou por+eng.")
        if self.bibliographic_evidence is not None and not isinstance(self.bibliographic_evidence, dict):
            raise ValueError("Evidências bibliográficas devem ser um objeto JSON por campo.")
        if self.source_context is not None:
            if (not isinstance(self.source_context, dict) or not isinstance(self.source_context.get("page_index_offset"), int)
                    or self.source_context["page_index_offset"] < 0
                    or not re.fullmatch(r"[0-9a-f]{64}", self.source_context.get("original_sha256", ""))):
                raise ValueError("Contexto do recorte exige original_sha256 e page_index_offset não negativo.")

    def to_dict(self):
        return asdict(self)
