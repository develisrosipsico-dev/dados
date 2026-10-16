from pathlib import Path

import pymupdf
import pytest


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
