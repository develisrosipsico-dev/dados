"""Inspeção local, somente leitura, com marcação das coordenadas no PDF."""
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pymupdf

from .storage import load_corpus


def get_paragraph(data, paragraph_id):
    for paragraph in data["paragraphs"]:
        if paragraph["paragraph_id"] == paragraph_id:
            nodes = {n["node_id"]: n for n in data["structure"]["nodes"]}
            hierarchy, current = [], nodes.get(paragraph["parent_id"])
            while current:
                hierarchy.append({k: current[k] for k in ("node_id", "kind", "title")})
                current = nodes.get(current["parent_id"])
            return {**paragraph, "hierarchy": list(reversed(hierarchy))}
    raise KeyError(f"Parágrafo não encontrado: {paragraph_id}")


def render_page(corpus, page_index, paragraph_id=None, *, data=None):
    data = data or load_corpus(corpus)
    if page_index not in data["metadata"]["selected_pages"]:
        raise ValueError("Página fora do recorte processado.")
    spans = get_paragraph(data, paragraph_id)["source_spans"] if paragraph_id else []
    with pymupdf.open(Path(corpus)/"original.pdf") as pdf:
        page = pdf[page_index]
        for span in spans:
            if span["page_index"] == page_index:
                annotation = page.add_rect_annot(pymupdf.Rect(span["bbox"]))
                annotation.set_colors(stroke=(1, .2, 0), fill=(1, .9, 0))
                annotation.set_opacity(.22)
                annotation.update()
        return page.get_pixmap(matrix=pymupdf.Matrix(1.4, 1.4), annots=True).tobytes("png")


HTML = """<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inspeção documental</title><style>
body{font:16px system-ui;margin:1.5rem;color:#192c37;background:#f3f5f7}h1{font-size:1.5rem}
main{display:grid;grid-template-columns:1fr 1fr;gap:1rem}section,article{background:white;padding:1rem;border-radius:8px}
img{width:100%;border:1px solid #cad1d8}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px ui-monospace}
button,select{padding:.5rem;cursor:pointer}article{border:1px solid #cad1d8;margin:.6rem 0}button{max-width:100%;overflow-wrap:anywhere}
.notice{color:#744000}#status{margin:.8rem 0}summary{cursor:pointer}@media(max-width:850px){main{grid-template-columns:1fr}}
</style><h1>Inspeção do corpus documental</h1>
<p>Compare o texto com o PDF. Alertas e classificações heurísticas exigem revisão.</p>
<p id="gate" class="notice" role="status"></p>
<label>Página física do PDF <select id="pages"></select></label><div id="status" role="status"></div>
<main><section><img id="pdf" alt="Página original, com regiões do parágrafo selecionado destacadas">
<details><summary>Extração bruta da página</summary><pre id="raw"></pre></details></section>
<section><h2>Parágrafos</h2><div id="paragraphs"></div><h2>Outros elementos</h2><div id="elements"></div>
<h2>Alertas e decisões</h2><pre id="alerts"></pre></section></main>
<script>
const $=id=>document.getElementById(id);
async function api(url){const r=await fetch(url);if(!r.ok)throw new Error(await r.text());return r.json()}
function pre(value,parent){const p=document.createElement('pre');p.textContent=typeof value==='string'?value:JSON.stringify(value,null,2);parent.append(p)}
async function show(){try{const i=$('pages').value;const d=await api('/api/page?index='+i);
$('status').textContent='Estado da extração: '+d.page.status+' | Método: '+d.page.method+' | Página impressa: não verificada';
$('pdf').src='/api/image?index='+i;$('raw').textContent=d.page.text_raw;
$('paragraphs').replaceChildren();for(const p of d.paragraphs){const a=document.createElement('article');
const b=document.createElement('button');b.textContent=p.paragraph_id;b.onclick=()=>{$('pdf').src='/api/image?index='+i+'&paragraph='+encodeURIComponent(p.paragraph_id)};a.append(b);
pre('Parágrafo '+p.paragraph_global_order+' | '+p.classification+' | '+p.hierarchy.map(n=>n.title||n.kind).join(' → '),a);
pre(p.text_clean,a);const detail=document.createElement('details');const sum=document.createElement('summary');sum.textContent='Hierarquia, origem, texto bruto e transformações';detail.append(sum);pre(p,detail);a.append(detail);$('paragraphs').append(a)}
$('elements').replaceChildren();for(const e of d.elements){const a=document.createElement('details');const s=document.createElement('summary');s.textContent=e.kind+' — '+(e.text_clean||e.element_id);a.append(s);pre(e,a);$('elements').append(a)}
$('alerts').textContent=JSON.stringify(d.events,null,2)}catch(e){$('status').textContent=e.message}}
api('/api/meta').then(d=>{const v=d.validation_summary;$('gate').textContent='Estado documental: '+v.status+' | Etapa de chunking: '+(v.chunking_gate.allowed?'liberada pelos critérios implementados':'bloqueada')+' | Fidelidade visual não certificada';for(const i of d.selected_pages){const o=document.createElement('option');o.value=i;o.textContent=String(i+1);$('pages').append(o)}$('pages').onchange=show;show()}).catch(e=>{$('status').textContent=e.message});
</script></html>"""


class Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, corpus, data, **kwargs):
        self.corpus, self.data = corpus, data
        super().__init__(*args, **kwargs)

    def do_GET(self):
        try:
            url = urlsplit(self.path)
            query = parse_qs(url.query)
            mime = "application/json; charset=utf-8"
            if url.path == "/":
                body, mime = HTML.encode(), "text/html; charset=utf-8"
            elif url.path == "/api/meta":
                body = json.dumps({**self.data["metadata"], "validation_summary": self.data["validation_summary"]}, ensure_ascii=False).encode()
            elif url.path == "/api/report":
                body = json.dumps(self.data["validation_summary"], ensure_ascii=False).encode()
            elif url.path in {"/api/page", "/api/image"}:
                index = int(query.get("index", [""])[0])
                if index not in self.data["metadata"]["selected_pages"]:
                    raise ValueError("Página fora do recorte.")
                if url.path == "/api/image":
                    body = render_page(self.corpus, index, query.get("paragraph", [None])[0], data=self.data)
                    mime = "image/png"
                else:
                    paragraphs = [get_paragraph(self.data, p["paragraph_id"]) for p in self.data["paragraphs"]
                                  if any(s["page_index"] == index for s in p["source_spans"])]
                    ids = {p["paragraph_id"] for p in paragraphs}
                    elements = [e for e in self.data["elements"] if e.get("page_index") == index or
                                any(s["page_index"] == index for s in e["source_spans"])]
                    ids.update(e["element_id"] for e in elements)
                    payload = {"page": next(p for p in self.data["pages"] if p["page_index"] == index),
                               "paragraphs": paragraphs, "elements": elements,
                               "events": [e for e in self.data["events"] if e.get("page_index") == index or e.get("unit_id") in ids]}
                    body = json.dumps(payload, ensure_ascii=False).encode()
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except (ValueError, KeyError) as error:
            self.send_error(400, str(error))


def make_server(corpus, host="127.0.0.1", port=8765):
    from .validation import validate_corpus
    data = load_corpus(corpus)
    data["validation_summary"] = validate_corpus(corpus)
    handler = partial(Handler, corpus=Path(corpus), data=data)
    return ThreadingHTTPServer((host, port), handler)
