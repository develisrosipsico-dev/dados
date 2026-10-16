# Corpus documental a partir de PDF

Protótipo Python para processar **um capítulo explicitamente selecionado**, preservar
a extração física e produzir unidades documentais localizáveis no PDF original.
Não utiliza modelos de linguagem, embeddings, índices de recuperação ou resumos.

O capítulo 1 de `story.pdf`, “O problema da estória”, foi processado nas páginas
físicas **19–36**, delimitadas pelos marcadores do PDF. A versão **0.1.1** corrige
a fragmentação de palavras justificadas na página 3 do capítulo: são **73 parágrafos**,
dez com origem em duas páginas, e seis notas finais candidatas.
O [relatório da correção](docs/CORRECAO_FLUXO.md) registra o caso e as limitações.
O corpus em [`examples/demo_corpus`](examples/demo_corpus) é **sintético** e
permanece disponível para demonstrar o fluxo sem depender do livro.

O capítulo 1 também está disponível para download direto pelo GitHub:
[PDF com as 18 páginas](story-capitulo-1.pdf) ou
[ZIP contendo somente esse PDF](capitulo-1-story.zip).
O [corpus corrigido com JSON/JSONL e inspeção](story-capitulo-1-corpus-corrigido.zip)
também está disponível. Corpora da versão 0.1.0 devem ser reprocessados em nova pasta;
a validação antiga de cobertura não detectava a fragmentação identificada.

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

O clone inclui código, testes, documentação, o exemplo sintético e o ZIP do corpus
corrigido. Para abrir esse resultado sem reprocessar:

```bash
mkdir -p corpora
unzip -n story-capitulo-1-corpus-corrigido.zip -d corpora
corpus inspect corpora/story-capitulo-1-corrigido
```

Para atualizar a instalação e gerar uma nova versão a partir do PDF local:

```bash
git pull --ff-only
source .venv/bin/activate
corpus process Corpora/story-capitulo-1.pdf --pages 1-18 --merge-pages \
  --output Corpora/story-capitulo-1-corrigido
corpus inspect Corpora/story-capitulo-1-corrigido
```

Pare o inspetor antigo com Ctrl+C antes de iniciar outro na mesma porta. A saída
precisa ser uma pasta nova; a aplicação preserva o corpus anterior para comparação.

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
corpus inspect corpora/story-capitulo-1-corrigido
corpus paragraph corpora/story-capitulo-1-corrigido para_e819e28b37515935f9211f2f
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
e continuação iniciada em minúscula. Cada junção fica pendente de revisão.
`--join-hyphens` pode alterar hífens lexicais: use apenas após inspecionar o recorte.
Todas as mudanças registram o texto anterior e posterior. O diretório de saída
deve ser novo; execuções não sobrescrevem corpora existentes.

Para idiomas adicionais, disponibilize os modelos oficiais em `TESSDATA_PREFIX`
e use, por exemplo, `--ocr-language por+eng`. A execução registra os hashes dos
modelos efetivamente usados. Não se presume que o modelo inglês esteja instalado
na pasta portuguesa preparada pelo script.

## Recuperação por identificador e localização

O exemplo incluído contém um parágrafo que atravessa duas páginas:

```bash
corpus paragraph examples/demo_corpus para_54a4b44e6a521e5d79887d7c
corpus render examples/demo_corpus --page 1 \
  --paragraph para_54a4b44e6a521e5d79887d7c --output /tmp/origem-pagina-1.png
corpus render examples/demo_corpus --page 2 \
  --paragraph para_54a4b44e6a521e5d79887d7c --output /tmp/origem-pagina-2.png
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
| `normalization.py` | Transformações explícitas e reversíveis por registro |
| `structure.py` | Hierarquia, classificação, parágrafos, períodos e vínculos |
| `models.py` | Configuração e identidades determinísticas |
| `audit.py` | Eventos e decisões de processamento |
| `storage.py` | JSON/JSONL e leitura do corpus |
| `validation.py` | Cobertura, relações, reconstrução e auditoria de transformações |
| `pipeline.py` | Coordenação, cópia imutável e persistência da saída |
| `inspection.py`, `cli.py` | Consulta por ID, renderização e interface local |

Cada saída contém os oito artefatos solicitados: `original.pdf`,
`pages_raw.jsonl`, `structure.json`, `paragraphs.jsonl`, `elements.jsonl`,
`metadata.json`, `processing_log.jsonl` e `validation_report.json`.
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

- `failed`: inconsistência documental ou falha de processamento. CLI retorna 2.
- `review_required`: invariantes passaram, mas há ambiguidades ou OCR a revisar.
- `automated_checks_passed`: verificações automáticas passaram, sem certificação
  de fidelidade visual. A revisão de um livro real continua necessária.

`process` e `validate` imprimem JSON; os dois últimos estados retornam 0.
Erros de uso/arquivo retornam 1 (sintaxe de argumentos usa o padrão do argparse, 2).
Falhas por página não desaparecem do relatório. Páginas fora do recorte são
explicitamente separadas de falhas. Os indicadores não são probabilidades de
acerto nem demonstram recuperação de caracteres que o PDF/OCR não forneceu.

Configuração, fonte, hash do código Python, versão da aplicação, PyMuPDF e modelos OCR compõem
a versão do corpus. IDs e artefatos são determinísticos sob essas condições;
alterações de segmentação ou configuração geram nova versão. Não há migração
automática de IDs entre versões. A garantia testada de reprodução é na mesma
plataforma e toolchain; não foi demonstrada equivalência bit a bit entre sistemas.
