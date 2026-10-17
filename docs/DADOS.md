# Contrato documental — esquema 1.1

## Convenções

Todos os arquivos de texto usam UTF-8. Intervalos são semiabertos `[start,end)`
medidos em pontos de código Unicode de Python, não bytes nem unidades UTF-16.
As páginas dos registros usam **índice físico base zero**. A CLI aceita páginas
base um. Coordenadas são pontos do PyMuPDF, no sistema não rotacionado da página.
`rotation` e dimensões ficam no registro da página. A renderização respeita a
rotação ao exibir as anotações.

`printed_page_number` permanece `null`: o protótipo não faz certificação visual da
numeração impressa. `pdf_page_label` guarda separadamente a etiqueta embutida,
que pode estar ausente ou divergir do número visível. Metadados bibliográficos
também preservam a proveniência; edição, editora e ano ausentes ficam `null`.

## Identidade e versões

- `file_id`: `sha256:<hash integral do PDF>`.
- `document_id`: identificador externo passado por `--document-id`, quando
  verificado; na ausência dele, um identificador determinístico derivado do arquivo.
  Não se deduz equivalência entre edições ou arquivos diferentes.
- `corpus_version`: hash da fonte, configuração, código Python, aplicação, PyMuPDF e modelos OCR.
- IDs de unidades: hash da versão e da localização física/segmentação. Uma junção
  registra IDs predecessores no log. Não se promete estabilidade entre versões.

## `metadata.json`

Inclui `schema_version`, `file_id`, `document_id`, `sha256`, `filename`,
`page_count`, `processing.raw_pages_sha256`, `previous_corpus_version`, `source_context`, `bibliographic`, `pdf_metadata`, `pdf_page_label_rules`,
`selected_pages`, `out_of_scope_pages`, `corpus_version`, `processing` e
`source_characteristics`. A caracterização textual/digitalizada/mista é uma
heurística do **recorte**, sem conclusão sobre páginas não processadas.

`pdf_outline` preserva os marcadores PDF. `bibliographic_evidence` contém campos
declarados com valor, página e trecho exato conferido no PDF. Seus offsets indexam
`page.get_text(sort=False)` dessa página de evidência, separadamente do corpus do
capítulo. Isso permite registrar dados da página de créditos sem processar o
restante do livro como corpo textual. O arquivo `examples/story_bibliography.json`
demonstra esse contrato para editora e ano.

## `pages_raw.jsonl`

Um registro por página selecionada, inclusive falhas:

```json
{
  "page_index": 0,
  "status": "ok",
  "method": "native",
  "text_raw": "texto do bloco 1\ntexto do bloco 2",
  "blocks": [],
  "reading_order": [],
  "tables": [],
  "drawings": [],
  "alerts": []
}
```

O exemplo acima ilustra campos, não um registro completo válido. Cada bloco textual
real tem `block_id`, `bbox`, `text_raw`, `char_start`, `char_end` e `lines`.
Cada linha preserva direção, coordenadas e spans tipográficos; cada span contém
fonte, tamanho, flags e caracteres com suas posições. Blocos de imagens preservam
posição e dimensões; seus pixels continuam disponíveis no PDF original.

`text_raw` concatena blocos textuais na **ordem nativa**, separados por `\n`.
As linhas de cada bloco também são separadas por `\n`. Esses separadores são uma
serialização da extração, não caracteres garantidamente presentes no arquivo.
Não se altera esse arquivo quando a ordem geométrica muda. O campo legado
`reading_order` do bruto não é atualizado: a ordem derivada fica em
`structure.page_reading_order`, com bloco e intervalos locais. Um bloco nativo
pode conter linhas de duas colunas ou vários parágrafos visuais.

Quando há tentativa de OCR, `native_extraction` retém os blocos e o texto nativos.
A camada usada nas unidades estruturadas fica em `text_raw`/`blocks`, com o método
explicitado. OCR não substitui a fonte original e exige revisão humana. Traçados
vetoriais são preservados em `drawings`, sem interpretar seu conteúdo.

## `structure.json`

`nodes` é uma lista de nós ligados por `parent_id`. O nó raiz tem
`node_id = document_id`, tipo `work` e pai `null`. Outros nós têm `kind`
(`part`, `chapter`, `section`, `subsection`), `title`, `element_id` e `level`.
Os níveis ausentes não são criados. Títulos tipográficos sem nível identificável
ficam como elementos `title_candidate`, com revisão pendente.
Nós reconhecidos por estilo incluem `source_spans`, evidência e estado de revisão.
Um número grande centralizado associado ao título pode fornecer o número do
capítulo; ele não se converte em paginação impressa.

Marcadores podem confirmar um título dividido entre número e texto. Ancestrais
fora do recorte podem ser nós contextuais com `element_id = null` e evidência do
marcador, sem extrair o corpo dessas páginas. Um padrão tipográfico recorrente
de títulos em maiúsculas, dentro de capítulo conhecido, pode produzir seções
**provisórias**, marcadas `review_required`. Não são classificações definitivas.

## `paragraphs.jsonl`

Cada registro contém:

| Campo | Significado |
| --- | --- |
| `paragraph_id`, `document_id` | Identidade da unidade e da obra/arquivo |
| `parent_id`, `chapter_id`, `section_id` | Contexto hierárquico; vínculos não identificados são `null` |
| `paragraph_global_order`, `paragraph_local_order` | Ordem base um na obra e no pai imediato |
| `previous_id`, `next_id` | Navegação entre parágrafos; extremos `null` |
| `text_raw`, `text_clean` | Extração integral da unidade e versão normalizada |
| `source_spans` | Uma ou mais origens físicas, na ordem de composição |
| `transformations` | Operação e valores completos `before`/`after`, encadeados |
| `classification`, `quality_status` | Tipo e estado da revisão |
| `normalization_map` | Intervalos limpos ligados ao texto bruto composto e às origens físicas |
| `editorial_amendments` | Propostas editoriais opcionais, separadas e não aplicadas ao texto documental |
| `hierarchy_review_required` | Necessidade de revisar o contexto ancestral |
| `sentences` | Períodos subordinados, com IDs e offsets no texto **limpo** |

Cada origem tem `page_index`, `printed_page_number`, `pdf_page_label`, `block_id`,
`bbox`, `block_char_start`, `block_char_end`, `char_start` e `char_end`.
Os dois últimos campos indexam `pages_raw.text_raw`; os intervalos locais indexam
`blocks[].text_raw`. Em unidades com várias origens, `text_raw` é a concatenação
das fatias, separadas por um `\n` explicitamente introduzido na composição.

Períodos cobrem exatamente o texto limpo, incluindo espaços entre frases. Seus
offsets não indexam a camada bruta; a origem física é consultada pelo parágrafo
pai e pelas transformações. As fronteiras linguísticas são provisórias, baseadas
em pontuação e exceções de abreviaturas. `normalization_map` registra intervalos do texto limpo, intervalos no bruto
composto e `source_refs` físicos correspondentes. Separadores introduzidos na
composição são explicitados. Operações de NFC podem mapear um grupo de caracteres
a um intervalo, sem prometer alinhamento lexical um a um.

Cada item de `editorial_amendments` registra `documentary_text`, `proposed_text`,
intervalos em `text_clean`, `source_refs`, justificativa, estado de verificação e
se a proposta foi aplicada. Propostas `proposed_unverified` mantêm
`applied_to_text_clean = false`; elas não substituem a transcrição visível no PDF.

## `elements.jsonl`

Armazena títulos, cabeçalhos, rodapés, notas, referências, listas, citações
classificadas, legendas, tabelas, figuras e candidatos vetoriais. Citações em bloco
também podem ser parágrafos classificados `block_quote`. Elementos textuais têm
o mesmo contrato de texto e origens, com `element_id` em vez de `paragraph_id`.

`text_ownership = primary` identifica os elementos que possuem fatias de texto.
`derived` identifica células de tabela extraídas adicionalmente, sem reivindicar
novamente o texto; `reference` aponta ao texto primário (citação ou chamada), sem dupla posse;
`none` indica imagem ou traçado. Tabelas têm `cells` e `bbox`.
O texto associado referencia `related_table_ids`. Figuras raster referenciam
`source_block_id`; candidatos vetoriais, `source_drawing_index`.

Chamadas numéricas sobrescritas podem ser vinculadas a notas numeradas com
evidência; os vínculos são bidirecionais e incluem offsets no texto limpo.
Notas na mesma página são diferenciadas das finais. Vínculos não verificados,
como uma chamada ambígua ou legenda → figura,
permanecem `null`, sem associações inventadas. Uma nota detectada por posição e
tipografia exige revisão; grupos de notas numeradas pequenas podem ser
`endnote_candidate`, sem afirmar se são notas finais ou de rodapé.
Glifos curtos isolados podem ficar como `marginal_glyph_candidate` ou
`short_text_candidate`, sem criar seções. Margens repetidas continuam presentes na extração e
nos elementos, embora separadas do fluxo de parágrafos.

Uma incompatibilidade visual-textual confirmada pode usar
`kind = text_layer_render_mismatch`, mantendo `text_ownership = primary` para
conservar a camada bruta. O objeto `text_layer_render_mismatch` registra subtipo,
valor textual, exclusão do fluxo de leitura, escopo da decisão e natureza do
revisor. A classificação exige um bloco explicitamente revisado; uma ocorrência
isolada não cria regra automática global.

## Auditoria e validação

`processing_log.jsonl` guarda eventos determinísticos com `event_id`, `code`,
`severity`, `message` e contexto (página, unidade, evidência ou transformação).
Não contém relógios nem segredos. Eventos anteriores a uma junção podem mencionar
unidades predecessoras, identificadas no evento `paragraph_merge`.

`validation_report.json` distingue falhas de consistência, falhas de processamento
e alertas. A reconstrução reagrupa as fatias dos proprietários primários na ordem
física dos blocos, conferindo página a página. Células derivadas e períodos
subordinados não são contados como cópias adicionais do conteúdo.

Essa verificação demonstra conservação da **extração recebida**, não a correção
de OCR nem a exatidão das fronteiras e classificações em relação à página visível.

Desde a versão 0.1.1, o validador também verifica as conexões geométricas entre
objetos da mesma linha visual. `inline_paragraph_split` identifica fragmentos
indevidamente separados em parágrafos; `inline_reading_order` identifica a
inversão desses objetos. O evento `inline_line_reconstruction` registra os
offsets nativos envolvidos. Fontes e intervalos brutos permanecem intactos.

## Extensões de validação e histórico — 0.2.0

Os 19 desenhos do capítulo conservam `source_bbox` e índice no bruto. A região
visível é limitada à página; `layout_artifact` distingue fundos brancos que
extrapolam a página e `separator_rule` distingue a linha de separação das notas.
A razão da exclusão de figuras fica registrada. O bruto não é apagado.

`history/manifest.json` registra os hashes dos seis derivados anteriores; revisões
sucessivas preservam o histórico existente. `validate_corpus()` verifica hashes
do PDF, do bruto e do histórico, além dos contratos relacionais.

O relatório separa `raw_integrity` de `documentary_quality`. Seus estados são
`blocked`, `review_required` e `approved`. `blocking_criteria` explicita os critérios
e `chunking_gate.allowed` só abre quando todos passam, incluindo a ausência de
casos inseguros pendentes. `fidelity_certified` permanece falso: aprovação das
verificações implementadas não equivale a certificação visual completa.

As verificações documentais incluem linhas por baseline/x, ordem dos parágrafos,
recuo com linha terminal curta, ancestralidade, citações, chamadas/notas, tipos e
caixas gráficas, correspondência do mapa, cobertura e não sobreposição primária.
Consulte [a revisão 0.2.0](REVISAO_DOCUMENTAL_0_2.md) para os critérios e resultados.
