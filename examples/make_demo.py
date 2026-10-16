"""Gera somente um capítulo fictício, explicitamente identificado como sintético."""
from pathlib import Path

import pymupdf


def create(path):
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    with pymupdf.open() as pdf:
        for index in range(2):
            page = pdf.new_page(width=595, height=842)
            page.insert_text((50, 35), "DEMONSTRAÇÃO SINTÉTICA", fontsize=9)
            page.insert_text((290, 815), str(index+1), fontsize=9)
            if index == 0:
                page.insert_text((50, 100), "Capítulo 1 - Documento de teste", fontsize=19)
                page.insert_text((50, 150), "1.1 Rastreabilidade", fontsize=15)
                page.insert_text((50, 200), "Este documento é sintético. Não representa o livro do usuário.", fontsize=11)
                page.insert_text((50, 250), "A normalização une linhas\nsem apagar a extração original.", fontsize=11)
                page.insert_text((50, 680), "Este parágrafo atravessa a página e continua", fontsize=11)
                page.insert_text((50, 745), "1 Nota sintética para inspeção documental.", fontsize=8)
            else:
                page.insert_text((50, 100), "na página seguinte com referências às duas origens.", fontsize=11)
                page.insert_text((50, 170), "Uma palavra hifeni-\nzada permanece preservada por padrão.", fontsize=11)
                page.insert_text((50, 250), "Referências bibliográficas", fontsize=15)
                page.insert_text((50, 290), "AUTOR FICTÍCIO. Documento de demonstração. 2026.", fontsize=11)
        pdf.set_metadata({"title": "Capítulo sintético de demonstração", "author": "Gerador de testes"})
        pdf.save(path, no_new_id=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    create(parser.parse_args().output)
