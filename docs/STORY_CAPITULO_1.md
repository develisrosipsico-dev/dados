# Story — protótipo controlado do capítulo 1

> Relatório histórico. A entrega atual está na [revisão 0.2.0](REVISAO_DOCUMENTAL_0_2.md).

**Relatório histórico da versão 0.1.0.** A revisão do usuário identificou uma
fragmentação e inversão de palavras na página 3 que a cobertura textual não
detectava. O corpus de 78 parágrafos descrito abaixo foi substituído pela versão
0.1.1, com 73 parágrafos. Consulte a [correção e validação atual](CORRECAO_FLUXO.md).
Preservar todos os caracteres não comprova a ordem e a segmentação corretas.

Fonte recebida: `story.pdf`, 493 páginas. Título e autor nos metadados internos:
**Story**, **Robert Mckee**. A página física 4 fornece a referência
“Curitiba : Arte & Letra, 2006.”, registrada como evidência de editora e ano.
A edição permanece desconhecida; “6a reimpressão”, também presente nos créditos,
não foi convertida indevidamente em número de edição.

SHA-256 da fonte e da cópia `original.pdf`:
`5360f54ed5d6e27414e7d06ca915f113235c010f614cf363c0e36d74cea0c35b`.

## Recorte e execução

Capítulo **1. O problema da estória**, páginas físicas **19–36**, índices 18–35.
O marcador da Parte 2 aponta para a página 37 e delimita o final do capítulo.
Os 475 demais índices ficam fora do corpus textual. A cópia original preserva
o arquivo integral, sem modificá-lo.

```bash
cd /workspace/dados
source .venv/bin/activate
export TESSDATA_PREFIX="$PWD/.local/tessdata"
corpus process /caminho/story.pdf --pages 19-36 --merge-pages \
  --bibliography examples/story_bibliography.json --output corpora/nova-versao-story
```

O resultado entregue está em `corpora/story-capitulo-1/`. Os hífens foram mantidos.
Não foi necessário OCR nesse capítulo, pois todas as páginas têm camada textual.
As páginas iniciais com imagens, fora do capítulo, não foram submetidas a OCR.

## Resultado automático

| Indicador | Resultado |
| --- | --- |
| Páginas selecionadas / registradas / extraídas | 18 / 18 / 18 |
| Falhas de página e processamento | 0 |
| Blocos textuais extraídos / cobertos | 97 / 97 |
| Cobertura dos blocos | 100% |
| Parágrafos | 78 |
| Parágrafos com origem em duas páginas | 10 |
| Erros de consistência | 0 |
| Reconstrução bruta | Conferida contra todos os blocos e páginas extraídos |
| Alertas de revisão | 57 |
| Estado | **`review_required`** |

Foram identificados um capítulo, seis seções **provisórias por estilo tipográfico**,
um título candidato adicional, seis notas finais candidatas, um glifo marginal
candidato e 19 traçados vetoriais candidatos. Esses elementos permanecem
rastreáveis. Os traçados incluem fundos e linhas; não são 19 ilustrações confirmadas.

A Parte 1 foi registrada como ancestral contextual a partir do marcador da página
10, sem incluir essa página no corpus textual do capítulo. O número e o título
do capítulo, separados fisicamente na página 19, estão ligados pela evidência
do marcador PDF. As seis notas pequenas da página 36 foram mantidas fora do corpo.

## Demonstração de recuperação e origem

```bash
corpus paragraph corpora/story-capitulo-1 para_749a8e0f324172055219f003
corpus render corpora/story-capitulo-1 --page 19 \
  --paragraph para_749a8e0f324172055219f003 --output /tmp/story-origem-19.png
corpus render corpora/story-capitulo-1 --page 20 \
  --paragraph para_749a8e0f324172055219f003 --output /tmp/story-origem-20.png
corpus inspect corpora/story-capitulo-1
```

Esse parágrafo tem ordem global 2 e pertence ao caminho **Story → Parte 1 →
O problema da estória → O declínio da estória**. O registro integral, com texto,
transformações e coordenadas das duas páginas, está em
`corpora/story-capitulo-1/inspection/paragraph_lookup.json`.
As imagens `paragraph-page-19.png` e `paragraph-page-20.png`, na mesma pasta,
destacam as duas regiões de origem. Ambas foram inspecionadas visualmente.

## Revisão e limitações específicas

- **Glifo marginal na página 25:** a extração retorna “Ó” perto da margem inferior,
  mas a renderização não mostra um título correspondente. O glifo foi preservado
  como candidato marginal, sem entrar no corpo nem criar seção. Isso demonstra
  uma divergência entre camada textual e aparência, ainda pendente de revisão.
- **Seções tipográficas:** seis títulos em maiúsculas compartilham estilo recorrente.
  Seus nós são provisórios; não representam aprovação humana da hierarquia.
  “Boa estória bem contada”, na página 29, permanece título candidato sem nível
  hierárquico atribuído automaticamente.
- **Junções entre páginas:** dez junções passaram pelas regras conservadoras.
  A primeira, entre as páginas 19 e 20, foi comparada visualmente. As demais seguem
  pendentes de revisão individual. Não se certifica a segmentação completa.
- **Hifenização:** quatro ocorrências candidatas foram registradas e mantidas;
  nenhum hífen foi removido automaticamente.
- **Notas:** os seis blocos finais da página 36 permanecem candidatos, sem vincular
  automaticamente os números às chamadas no corpo. Sua separação visual do corpo
  foi conferida nessa página.
- **Numeração impressa:** não foi inferida; os índices físicos fornecem localização.
- **Escopo da revisão visual:** páginas 19, 20, 25, 26 e 36 foram renderizadas para
  inspeção; não houve leitura e conferência visual integral das 18 páginas.

A reprodução automática confere o texto **extraído** e suas relações, sem certificar
fidelidade perfeita à obra visível. A estrutura está disponível para inspeção e
continuidade da validação; o processamento não foi ampliado para o livro inteiro.

Uma segunda execução com a mesma fonte, nome de arquivo, configuração e toolchain
produziu os **oito artefatos idênticos byte a byte**. A revalidação por CLI coincidiu
com o relatório salvo e conferiu novamente o SHA-256 do PDF. A inspeção HTTP do
corpus real retornou o recorte correto, parágrafos, hierarquia, elementos, alertas
e imagem PNG com marcação de origem.
