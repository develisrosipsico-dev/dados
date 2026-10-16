# Validação do protótipo

**Resultado atual do capítulo real:** [revisão incremental 0.2.0](REVISAO_DOCUMENTAL_0_2.md),
72 parágrafos, 14 pendências e chunking bloqueado.

O PDF chegou após a especificação. O capítulo real foi processado separadamente;
consulte [Story — capítulo 1](STORY_CAPITULO_1.md). As evidências desta página
se referem à suíte de testes e ao corpus sintético. O restante do livro não foi processado.

## Evidências

Execução no ambiente: Python 3.12.14, PyMuPDF 1.26.7, pytest 8.4.2.

`python -m pytest -q`: **63 testes passaram**, sem falhas ou skips neste ambiente.
Os novos testes separam integridade bruta, qualidade documental sintética e
regressões obrigatórias com o PDF real; os 35 testes anteriores foram preservados.
Sete regressões de fluxo foram incluídas na versão 0.1.1 após o relato do usuário;
a suíte inicial de 28 casos não cobria palavras justificadas emitidas como linhas
independentes. Consulte a [análise da correção](CORRECAO_FLUXO.md).
O caso de OCR real utilizou o modelo português oficial `tessdata_fast`, revisão
`87416418657359cb625c412a48b6e1d6d41c29bd`, SHA-256
`c4932b937207a9514b7514d518b931a99938c02a28a5a5a553f8599ed58b7deb`.
Em outra máquina sem modelo, esse caso é explicitamente pulado; o script de setup
instala o modelo e executa a suíte.

| Verificação | Evidência |
| --- | --- |
| Fonte imutável | Comparação de bytes entre entrada e `original.pdf`, antes e depois do processamento/renderização |
| Cobertura das páginas | Recorte de duas páginas em livro sintético de três; terceira permanece fora do escopo |
| Falhas explícitas | Erro injetado em uma página e OCR indisponível produzem eventos e estado `blocked` |
| Cobertura textual | Fatias classificadas cobrem integralmente os blocos e reconstroem a extração |
| Ordem de leitura | Duas colunas, incluindo linhas agrupadas num mesmo bloco nativo, ordenadas por geometria |
| Linha justificada | Palavras da mesma linha, inclusive com variação de fonte, permanecem no parágrafo e antes da continuação |
| Separações legítimas | Colunas com gutters de 105 e 17 pt e listas lado a lado não são unidas |
| Validação do erro legado | Fragmentação e inversão são detectadas mesmo com cobertura de 100%, offsets e relações consistentes |
| Separação do corpo | Títulos, notas, margens repetidas e referências mantidos como elementos |
| Hierarquia incerta | Título apenas tipográfico fica candidato; não se cria capítulo arbitrário |
| Marcadores PDF | Número e título separados vinculados ao capítulo; ancestral fora do recorte documentado |
| Bibliografia | Valores declarados só são aceitos com trecho de evidência encontrado na fonte |
| Parágrafo entre páginas | Duas origens físicas e evento da junção explícita; padrão não une automaticamente |
| Transformações | Cadeia `before`/`after`, eventos e preservação de hífens por padrão |
| Integridade negativa | Texto perdido/adicionado, offsets errados, IDs duplicados, vínculos e auditoria adulterados são detectados |
| Outros elementos | Grade de tabela, texto das células, lista, legenda e imagem preservados |
| Repetibilidade | Artefatos completos idênticos em duas execuções com mesma fonte e configuração |
| Inspeção | Requisições HTTP à página e imagem destacada; consultas fora do recorte rejeitadas |

## Corpus de demonstração incluído

[`examples/demo_corpus/validation_report.json`](../examples/demo_corpus/validation_report.json):

- Duas páginas selecionadas e registradas; nenhuma falha de página.
- 14 blocos textuais, todos classificados e cobertos.
- Quatro parágrafos, um com origem nas duas páginas.
- Zero erros de consistência e zero falhas de processamento.
- Dez eventos de alerta, sete pendências documentais; estado **`review_required`**.
- Reconstrução da extração bruta conferida, sem perdas ou duplicações detectadas.

O parágrafo `para_47ede0090298e60d62d44eb4` foi recuperado com sua hierarquia e
duas referências físicas. A região da primeira página foi renderizada e inspecionada
visualmente em [`examples/paragraph_location.png`](../examples/paragraph_location.png).
O arquivo [`examples/paragraph_lookup.json`](../examples/paragraph_lookup.json)
contém o resultado completo da consulta. Os alertas de margens, ordenação,
hifenização e junção permanecem visíveis; não representam aprovação humana.

## Limitações e decisões pendentes

1. Colunas são inferidas por faixas brancas e caixas. Layouts entrelaçados, texto
   vertical, notas laterais, tabelas sobrepostas e diagramas podem exigir revisão
   adicional. A ordenação não é certificada só porque a cobertura é integral.
2. Parágrafos usam blocos, espaçamento e tipografia. Recuos sutis, iniciais
   capitulares, poesia e PDFs mal agrupados podem precisar de segmentação manual.
   Continuações sem os indícios conservadores não são unidas automaticamente.
3. Marcadores textuais e PDF sustentam a hierarquia. Um estilo tipográfico recorrente
   em capítulo conhecido pode formar seções provisórias; casos sem nível
   identificável permanecem candidatos. Numeração isolada pode ser lista; essa
   distinção também exige inspeção.
4. Notas, citações, listas, legendas e margens repetidas usam regras heurísticas.
   Chamadas numéricas sobrescritas são vinculadas quando há evidência; vínculos
   ambíguos de notas ou legendas permanecem pendentes. A interface
   permite inspeção, mas ainda não inclui editor de correções/revisão persistida.
5. Tabelas sem bordas ou células mescladas podem não ser detectadas corretamente.
   Imagens são regiões do original; traçados vetoriais são candidatos sem agrupamento
   semântico em figuras. Não há descrição interpretativa de imagens.
6. Caracteres corrompidos são sinalizados e mantidos. O detector de OCR usa texto,
   caracteres de substituição e área de imagens; não diagnostica todas as fontes
   com mapeamento incorreto. Páginas sem texto exigem inspeção mesmo sem imagem.
7. OCR tem erros possíveis e não foi calibrado no livro do usuário. O texto nativo
   anterior ao OCR é preservado. Reconstrução perfeita da camada OCR não significa
   transcrição perfeita da página visível.
8. Numeração impressa, edição, editora e ano não verificados ficam ausentes.
   As etiquetas PDF e os campos bibliográficos internos não são prova editorial.
9. Segmentação em períodos é provisória; abreviaturas, iniciais e citações podem
   gerar fronteiras incorretas. Não há interpretação semântica.
10. Reprodutibilidade foi demonstrada na mesma plataforma. Não há estabilidade de IDs entre versões; a entrega real inclui um mapa
    de origens entre versões, sem prometer equivalência semântica. Não há controle de concorrência de produtores no mesmo caminho
    nem avaliação de desempenho em livros inteiros.

## Continuidade da validação

O capítulo 1 recebido tem relatório, consulta por ID e marcações nas páginas 19 e 20.
Continuar a revisão documental das fronteiras e classificações indicadas no relatório
antes de aceitar o corpus ou ampliar o processamento para o livro inteiro.
