"""Interface de processamento, recuperação por ID e inspeção."""
import argparse
import json
from pathlib import Path
import sys

import pymupdf

from .inspection import get_paragraph, make_server, render_page
from .models import Config
from .pipeline import process
from .storage import load_corpus
from .validation import validate_corpus


def parse_pages(value):
    try:
        pages = set()
        for part in value.split(","):
            limits = [int(p) for p in part.split("-")]
            if len(limits) not in (1, 2) or min(limits) < 1:
                raise ValueError
            start, end = limits[0], limits[-1]
            if end < start:
                raise ValueError
            pages.update(range(start-1, end))
        if not pages:
            raise ValueError
        return tuple(sorted(pages))
    except ValueError as error:
        raise argparse.ArgumentTypeError("Use páginas físicas base 1, por exemplo 10-15 ou 2,4-6.") from error


def main(argv=None):
    parser = argparse.ArgumentParser(description="Corpus documental rastreável de um recorte de PDF")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("process", help="Processar apenas as páginas explicitamente selecionadas")
    run.add_argument("source", type=Path)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--pages", type=parse_pages, required=True, help="Páginas físicas base 1, ex.: 10-15")
    run.add_argument("--ocr", choices=["auto", "never", "always"], default="auto")
    run.add_argument("--ocr-language", default="por")
    run.add_argument("--ocr-dpi", type=int, default=300)
    run.add_argument("--join-hyphens", action="store_true", help="Tentar junções corroboradas na fonte, mantendo revisão das alterações")
    run.add_argument("--reviewed-line-hyphen", action="append", default=[], metavar="FORMA",
                     help="Preservar o hífen e remover a quebra de uma forma já revisada, ex.: revela-se")
    run.add_argument("--editorial-amendment", action="append", default=[], metavar="DOCUMENTAL=PROPOSTA",
                     help="Registrar proposta editorial separada do texto documental, sem aplicá-la")
    run.add_argument("--reviewed-text-layer-mismatch", action="append", default=[], metavar="BLOCO=SUBTIPO",
                     help="Classificar uma incompatibilidade visual-textual já revisada pelo bloco de origem")
    run.add_argument("--merge-pages", action="store_true", help="Autorizar junção heurística entre páginas; exige revisão")
    run.add_argument("--document-id", help="Identificador bibliográfico externo, se já verificado")
    run.add_argument("--bibliography", type=Path, help="JSON de metadados com trechos de evidência verificáveis no PDF")
    run.add_argument("--raw-pages", type=Path, help="Reutilizar pages_raw.jsonl byte a byte, preservando o histórico")
    run.add_argument("--source-context", type=Path, help="JSON de referência ao recorte original, separado dos índices locais")
    for name in ("validate", "check-ready", "paragraph", "render", "inspect"):
        sub = commands.add_parser(name)
        sub.add_argument("corpus", type=Path)
        if name == "paragraph":
            sub.add_argument("paragraph_id")
        if name == "render":
            sub.add_argument("--page", type=int, required=True, help="Página física base 1")
            sub.add_argument("--paragraph")
            sub.add_argument("--output", type=Path, required=True)
        if name == "inspect":
            sub.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    # Mantém stdout utilizável como JSON; suprime apenas uma recomendação comercial.
    pymupdf.no_recommend_layout()
    try:
        if args.command == "process":
            config = Config(pages=args.pages, ocr=args.ocr, ocr_language=args.ocr_language,
                            ocr_dpi=args.ocr_dpi, join_hyphens=args.join_hyphens,
                            reviewed_line_hyphens=tuple(args.reviewed_line_hyphen),
                            editorial_amendments=tuple(args.editorial_amendment),
                            reviewed_text_layer_mismatches=tuple(args.reviewed_text_layer_mismatch),
                            merge_pages=args.merge_pages, document_id=args.document_id,
                            bibliographic_evidence=json.loads(args.bibliography.read_text(encoding="utf-8")) if args.bibliography else None,
                            source_context=json.loads(args.source_context.read_text(encoding="utf-8")) if args.source_context else None)
            report = process(args.source, args.output, config, raw_pages_path=args.raw_pages)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 2 if report["status"] == "blocked" else 0
        if args.command == "inspect":
            with make_server(args.corpus, port=args.port) as server:
                print(f"Inspeção local ativa na porta {args.port}. Ctrl+C para encerrar.", flush=True)
                server.serve_forever()
            return 0
        data = load_corpus(args.corpus)
        if args.command in {"validate", "check-ready"}:
            report = validate_corpus(args.corpus)
            print(json.dumps(report["chunking_gate"] if args.command == "check-ready" else report, ensure_ascii=False, indent=2))
            return 2 if report["status"] == "blocked" or (args.command == "check-ready" and not report["chunking_gate"]["allowed"]) else 0
        if args.command == "paragraph":
            print(json.dumps(get_paragraph(data, args.paragraph_id), ensure_ascii=False, indent=2))
        elif args.command == "render":
            image = render_page(args.corpus, args.page-1, args.paragraph, data=data)
            with args.output.open("xb") as target:
                target.write(image)
        return 0
    except (ValueError, OSError, KeyError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
