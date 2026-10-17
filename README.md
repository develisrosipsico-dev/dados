# Corpus documental a partir de PDF

Protótipo Python para processar **um capítulo explicitamente selecionado**, preservar
a extração física e produzir unidades documentais localizáveis no PDF original.
Não utiliza modelos de linguagem, embeddings, índices de recuperação ou resumos.

A revisão incremental **0.2.3** preserva as correções anteriores e resolve o
elemento marginal da página local 7 como `text_layer_render_mismatch`, subtipo
`clipped_text_object`. A camada textual `Ó` foi preservada; o objeto está quase
todo fora do recorte de renderização e aparece apenas como um pequeno traço.
São 72 parágrafos; **70 testes passaram**. O PDF e `pages_raw.jsonl` foram
preservados byte a byte, com histórico, mapas de proveniência e linhagem.
Os registros auditáveis das [Tarefas 012](reviews/tarefa-012-v1.json),
[013](reviews/tarefa-013-v1.json) e [014](reviews/tarefa-014-v1.json) documentam
evidências, mudanças e testes.

**Estado: `review_required`; futuro chunking bloqueado.** Há 12 pendências
explícitas. Cobertura integral da extração não certifica fidelidade visual.
O [relatório completo](docs/REVISAO_DOCUMENTAL_0_2.md) apresenta causas, funções
alteradas, regressões, IDs, demonstração visual e limitações.

Baixe pelo GitHub o [novo corpus, PDF e evidências em ZIP](story-capitulo-1-revisao-documental-v0.2.3.zip)
ou o [PDF de 18 páginas](story-capitulo-1.pdf). O
[ZIP anterior 0.1.1](story-capitulo-1-corpus-corrigido.zip) permanece como histórico
e fixture de regressão. A referência às páginas 19–36 do livro completo fica em
metadados separados dos índices locais 0–17; não se inventou paginação impressa.
O [exemplo sintético](examples/demo_corpus) também foi migrado ao novo esquema.

## Clonar em outra máquina

```bash
git clone https://github.com/develisrosipsico-dev/dados.git
cd dados
```

No Linux ou WSL, com Python 3.11+ instalado:

```bash
bash scripts/setup.sh
source .venv/bin/activate
export TESSDATA_PREFIX="$PWD/.local/tessdata"
corpus inspect examples/demo_corpus
```

Para abrir a revisão já processada, inclusive no macOS com a instalação existente:

```bash
git pull --ff-only
source .venv/bin/activate
unzip -n story-capitulo-1-revisao-documental-v0.2.3.zip -d Corpora
corpus inspect Corpora/story-capitulo-1-revisao-documental-v0.2.3
```

Se ainda não houver ambiente Python no macOS, com Python 3.11+ instalado:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip install --no-deps -e .
```

O capítulo usa texto nativo; abrir o resultado não exige modelo OCR. Pare o
inspetor antigo com Ctrl+C antes de iniciar outro na mesma porta. O relatório,
as imagens e as consultas por ID também estão dentro do ZIP.

## Instalação

Requisitos: Python 3.11+ (validado em 3.12), `venv`, `curl`, `sha256sum` e acesso a
PyPI e `raw.githubusercontent.com`. O OCR do PyMuPDF usa Tesseract internamente;
o script instala o modelo português oficial com revisão e SHA-256 fixados.

```bash
cd /workspace/dados
bash scripts/setup.sh
source .venv/bin/activate
export TESSDATA_PREFIX="$PWD/.local/tessdata"
```

O script instala as versões de `requirements-dev.txt`, registra o pacote local e
executa os testes. Pode ser repetido. O modelo fica em `.local/`, ignorado pelo
Git; não é necessário alterar pacotes do sistema nem fornecer credenciais.
`--ocr never` permite trabalhar exclusivamente com a camada textual, mas páginas
que precisam de OCR continuam registradas como problema de extração.

## Processar o capítulo

Os números de `--pages` são **páginas físicas do arquivo, base 1**, não os números
impressos no livro. A seleção é obrigatória; não há processamento integral implícito.
Exemplo para um capítulo que ocupa as páginas físicas 12 a 24:

```bash
corpus process /caminho/livro.pdf --pages 12-24 --output corpora/capitulo-v1
corpus validate corpora/capitulo-v1
corpus inspect corpora/capitulo-v1
```

`inspect` abre um serviço local na porta 8765. A interface permite escolher uma
página, comparar a imagem com a extração, consultar parágrafos e elementos,
examinar alertas e clicar no ID de um parágrafo para destacar suas coordenadas.
O serviço é somente leitura e escuta na interface de loopback. Encerre com Ctrl+C.

Para inspecionar o capítulo já processado:

```bash
corpus inspect Corpora/story-capitulo-1-revisao-documental-v0.2.3
corpus paragraph Corpora/story-capitulo-1-revisao-documental-v0.2.3 para_f58b94908b71d770fe6e0cb2
```

O registro bibliográfico opcional aceita campos com evidências conferidas na fonte:

```bash
corpus process /caminho/story.pdf --pages 19-36 --merge-pages \
  --bibliography examples/story_bibliography.json --output corpora/story-nova-versao
```

Esse JSON registra editora e ano a partir da página física 4. O programa exige que
o trecho e o valor declarado existam na extração dessa página; não infere edição.

Por padrão, a aplicação mantém os hífens e as separações entre páginas. Opções de
normalização que exigem decisão documental são explícitas:

```bash
corpus process /caminho/livro.pdf --pages 12-24 \
  --merge-pages --join-hyphens --output corpora/capitulo-v2
```

`--merge-pages` une somente candidatos com páginas contíguas, mesmo contexto
hierárquico, tipografia e alinhamento compatíveis, ausência de pontuação terminal
e continuação iniciada em minúscula. As evidências e ambiguidades ficam registradas.
`--join-hyphens` só remove um hífen com corroboração literal no bruto e mantém
essa alteração sob revisão; candidatos sem evidência são preservados.
`--reviewed-line-hyphen revela-se` registra uma decisão documental pontual:
remove apenas a quebra depois do hífen e conserva a forma lexical autorizada.
O argumento pode ser repetido e integra a identidade da versão do corpus.
`--editorial-amendment 'pré-requisi-tos=pré-requisitos'` registra uma proposta
editorial separada, com proveniência, sem aplicá-la a `text_clean`.
`--reviewed-text-layer-mismatch 'p000006_b00005=clipped_text_object'` aplica uma
decisão visual explícita somente ao bloco indicado e conserva seu texto bruto.
Todas as mudanças registram o texto anterior e posterior. O diretório de saída
deve ser novo; execuções não sobrescrevem corpora existentes.

Para idiomas adicionais, disponibilize os modelos oficiais em `TESSDATA_PREFIX`
e use, por exemplo, `--ocr-language por+eng`. A execução registra os hashes dos
modelos efetivamente usados. Não se presume que o modelo inglês esteja instalado
na pasta portuguesa preparada pelo script.

## Recuperação por identificador e localização

O exemplo incluído contém um parágrafo que atravessa duas páginas:

```bash
corpus paragraph examples/demo_corpus para_47ede0090298e60d62d44eb4
corpus render examples/demo_corpus --page 1 \
  --paragraph para_47ede0090298e60d62d44eb4 --output /tmp/origem-pagina-1.png
corpus render examples/demo_corpus --page 2 \
  --paragraph para_47ede0090298e60d62d44eb4 --output /tmp/origem-pagina-2.png
```

Texto recuperado: “Este parágrafo atravessa a página e continua na página seguinte
com referências às duas origens.” Sua posição é obra → capítulo 1 → seção 1.1.
As duas origens têm índices físicos 0 e 1, coordenadas e intervalos de caracteres.
Veja o resultado salvo em [`examples/paragraph_lookup.json`](examples/paragraph_lookup.json)
e a marcação em [`examples/paragraph_location.png`](examples/paragraph_location.png).
A renderização altera apenas a cópia em memória, sem salvar anotações no PDF.

Para gerar um novo exemplo em diretórios ainda inexistentes:

```bash
python examples/make_demo.py /tmp/novo-capitulo-sintetico.pdf
corpus process /tmp/novo-capitulo-sintetico.pdf --pages 1-2 \
  --merge-pages --output corpora/nova-demo
```

## Arquitetura e artefatos

| Módulo | Responsabilidade |
| --- | --- |
| `ingest.py` | Identidade SHA-256, registro da fonte, metadados com proveniência |
| `extraction.py` | Texto, linhas, caracteres, fontes, imagens e traçados por página; OCR seletivo |
| `layout.py` | Fragmentação de blocos entre colunas, ordem geométrica e margens repetidas |
| `composition.py` | Linhas visuais, fragmentos e fronteiras por composição |
| `hierarchy.py` | Níveis reconhecidos por evidências tipográficas e posição |
| `normalization.py`, `provenance.py` | Transformações e mapa limpo → bruto → fonte |
| `special.py`, `graphics.py` | Citações, notas/chamadas e classificação geométrica |
| `structure.py` | Hierarquia, classificação, parágrafos, períodos e vínculos |
| `models.py` | Configuração e identidades determinísticas |
| `audit.py` | Eventos e decisões de processamento |
| `storage.py` | JSON/JSONL e leitura do corpus |
| `validation.py`, `quality.py` | Integridade bruta, qualidade documental e gate de chunking |
| `pipeline.py` | Coordenação, cópia imutável e persistência da saída |
| `inspection.py`, `cli.py` | Consulta por ID, renderização e interface local |

Cada saída contém os oito artefatos solicitados: `original.pdf`,
`pages_raw.jsonl`, `structure.json`, `paragraphs.jsonl`, `elements.jsonl`,
`metadata.json`, `processing_log.jsonl` e `validation_report.json`.
Revisões com `--raw-pages` preservam os bytes do bruto, validam sua identidade
e arquivam os derivados anteriores em `history/`. `--source-context` permite
registrar o vínculo do recorte ao livro sem confundir a paginação.
O PDF copiado corresponde ao arquivo completo; somente as páginas selecionadas
são processadas. Não foi implementada a exportação opcional para SQLite.

Consulte o [contrato de dados](docs/DADOS.md) e o
[relatório de validação e limitações](docs/VALIDACAO.md).

## Verificação e interpretação do relatório

```bash
.venv/bin/python -m pytest -q
.venv/bin/corpus validate examples/demo_corpus
```

Os testes incluem documentos sintéticos, OCR real quando o modelo está disponível,
falhas de extração simuladas e adulterações de texto, offsets, relações e auditoria.
`scripts/setup.sh` instala o modelo necessário para executar também o caso de OCR.

- `blocked`: erro de integridade, processamento ou reconstrução documental. CLI retorna 2.
- `review_required`: critérios automáticos passaram, mas há casos inseguros pendentes.
- `approved`: critérios implementados passaram e não há pendências identificadas;
  não certifica fidelidade visual exaustiva.

`process` e `validate` imprimem JSON; os dois últimos estados retornam 0.
`corpus check-ready PASTA` revalida os arquivos e só retorna 0 com todos os
critérios bloqueantes satisfeitos. Para esta entrega retorna **2**.
`raw_integrity` e `documentary_quality` são avaliados separadamente.
Erros de uso/arquivo retornam 1 (sintaxe de argumentos usa o padrão do argparse, 2).
Falhas por página não desaparecem do relatório. Páginas fora do recorte são
explicitamente separadas de falhas. Os indicadores não são probabilidades de
acerto nem demonstram recuperação de caracteres que o PDF/OCR não forneceu.

Configuração, fonte, hash do código Python, versão da aplicação, PyMuPDF e modelos OCR compõem
a versão do corpus. IDs e artefatos são determinísticos sob essas condições;
alterações de segmentação ou configuração geram nova versão. Não há estabilidade
automática de IDs entre versões; esta entrega inclui `lineage.jsonl` para os 72
parágrafos e `element_lineage.jsonl` para o elemento reclassificado, por igualdade
das origens. A garantia testada de reprodução é na mesma
plataforma e toolchain; não foi demonstrada equivalência bit a bit entre sistemas.
