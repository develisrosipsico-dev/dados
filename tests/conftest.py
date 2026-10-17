from pathlib import Path

import pymupdf
import pytest
import json
from zipfile import ZipFile

from corpus_documental.models import Config
from corpus_documental.pipeline import process
from corpus_documental.storage import load_corpus


def synthetic_book(path):
    """Três páginas; somente duas pertencem ao capítulo de teste."""
    with pymupdf.open() as pdf:
        for index in range(3):
            page = pdf.new_page(width=595, height=842)
            page.insert_text((50, 35), "CADERNO DOCUMENTAL", fontsize=9)
            page.insert_text((290, 815), str(index+1), fontsize=9)
            if index == 0:
                page.insert_text((50, 100), "Capítulo 1 - Ensaio", fontsize=19)
                page.insert_text((50, 150), "1.1 Fundamentos", fontsize=15)
                page.insert_text((50, 200), "Este é o primeiro parágrafo. Ele preserva a pontuação.", fontsize=11)
                page.insert_text((50, 250), "Uma palavra hifeni-\nzada permanece auditável.", fontsize=11)
                page.insert_text((50, 740), "1 Nota explicativa preservada fora do corpo.", fontsize=8)
                page.insert_text((50, 680), "Este parágrafo atravessa a página e continua", fontsize=11)
            elif index == 1:
                page.insert_text((50, 100), "na página seguinte com sua origem preservada.", fontsize=11)
                page.insert_text((50, 150), "Outro parágrafo completo. Uma segunda frase.", fontsize=11)
                page.insert_text((50, 220), "Referências bibliográficas", fontsize=15)
                page.insert_text((50, 260), "SILVA, A. Uma obra documental. 2020.", fontsize=11)
            else:
                page.insert_text((50, 100), "Capítulo 2 - Fora do recorte", fontsize=19)
        pdf.set_metadata({"title": "Ensaio sintético", "author": "Autor de teste"})
        pdf.save(path, no_new_id=True)
    return Path(path)


@pytest.fixture
def book(tmp_path):
    return synthetic_book(tmp_path/"ensaio.pdf")


@pytest.fixture(scope="session")
def reviewed_story(tmp_path_factory):
    """Regressão no PDF real a partir da versão obrigatória 0.2.2."""
    project = Path(__file__).resolve().parents[1]
    source = project/"story-capitulo-1.pdf"
    assert source.is_file(), "O PDF de regressão deve acompanhar o checkout."
    folder = tmp_path_factory.mktemp("story_incremental")
    previous = folder/"previous"
    previous.mkdir()
    archive_root = "corpora/story-capitulo-1-revisao-documental-v0.2.2/"
    with ZipFile(project/"story-capitulo-1-revisao-documental-v0.2.2.zip") as archive:
        for name in ("metadata.json", "structure.json", "pages_raw.jsonl", "paragraphs.jsonl", "elements.jsonl", "processing_log.jsonl", "validation_report.json"):
            (previous/name).write_bytes(archive.read(archive_root+name))
    context = json.loads((project/"examples/story_excerpt_context.json").read_text())
    output = folder/"revised"
    config = Config(pages=tuple(range(18)), merge_pages=True,
                    reviewed_line_hyphens=("revela-se", "pré-requisi-tos"),
                    editorial_amendments=("pré-requisi-tos=pré-requisitos",),
                    reviewed_text_layer_mismatches=("p000006_b00005=clipped_text_object",),
                    source_context=context)
    report = process(source, output, config, raw_pages_path=previous/"pages_raw.jsonl")
    return {"source": source, "previous": previous, "output": output, "data": load_corpus(output),
            "config": config, "report": report}
