import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from corpus_documental.inspection import get_paragraph, make_server, render_page
from corpus_documental.models import Config
from corpus_documental.pipeline import process
from corpus_documental.storage import load_corpus


def test_lookup_and_pdf_region(book, tmp_path):
    output = tmp_path/"corpus"
    process(book, output, Config(pages=(0, 1)))
    data = load_corpus(output)
    p = get_paragraph(data, data["paragraphs"][0]["paragraph_id"])
    assert [n["kind"] for n in p["hierarchy"]] == ["work", "chapter", "section"]
    plain = render_page(output, 0)
    marked = render_page(output, 0, p["paragraph_id"])
    assert marked.startswith(b"\x89PNG") and plain != marked
    assert (output/"original.pdf").read_bytes() == book.read_bytes()
    with pytest.raises(KeyError):
        get_paragraph(data, "missing")


def test_inspection_http_smoke(book, tmp_path):
    output = tmp_path/"corpus"
    process(book, output, Config(pages=(0, 1)))
    with make_server(output, port=0) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            assert "Inspeção" in urlopen(base).read().decode()
            page = json.load(urlopen(base+"/api/page?index=0"))
            assert page["paragraphs"] and page["elements"]
            p = page["paragraphs"][0]
            assert p["source_spans"][0]["page_index"] == 0
            image = urlopen(base+"/api/image?index=0&paragraph="+p["paragraph_id"]).read()
            assert image.startswith(b"\x89PNG")
            with pytest.raises(HTTPError) as error:
                urlopen(base+"/api/page?index=2")
            assert error.value.code == 400
        finally:
            server.shutdown()
            thread.join(timeout=5)
