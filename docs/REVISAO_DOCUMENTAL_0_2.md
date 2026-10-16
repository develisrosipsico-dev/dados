# Revisão documental incremental — versão 0.2.0

Estado da entrega: **`review_required`**. O relatório contém zero erros de
integridade/formato e zero bloqueadores documentais automáticos, mas **14 itens
de revisão continuam abertos**. Portanto, **`chunking_gate.allowed = false`**.
Não houve embeddings, BM25, RAG, resumo ou interpretação conceitual.

## Fontes, escopo e preservação

Foi usado o PDF recebido `story-capitulo-1.pdf`, com 18 páginas, e a extração
da entrega rastreável anterior `story-capitulo-1-corpus-corrigido.zip` (0.1.1).
Os números de registros do relato original pertencem à versão anterior à correção
A; os testes identificam os casos por página, conteúdo e intervalos físicos,
sem tratar a ordem global como identidade permanente.

- SHA-256 do PDF de 18 páginas:
  `dabd10538ffdc866c6fa24187ffb1b9f784f647a01d5286a9c6a91cd7015633d`.
- SHA-256 de `pages_raw.jsonl`, **idêntico byte a byte à entrada**:
  `64e0b2d3cc7adf6c53a663470080fecf2a03ab203c55d5ed08817a248de56811`.
- Versão do corpus: `corpus_d43918f06609b65f21f89425`.
- Os seis arquivos derivados anteriores ficam em `history/`, acompanhados de
  manifesto de hashes. `lineage.jsonl` relaciona os 73 parágrafos anteriores
  aos 72 atuais, inclusive divisões e junções.
- `page_index` continua local, de 0 a 17. A referência às páginas físicas 19–36
  do livro completo fica exclusivamente em `metadata.source_context`, com hash
  da fonte maior e offset 18. Não se inferiu paginação impressa.

O extrator/OCR, os formatos JSON/JSONL, a CLI e a aplicação existentes foram
mantidos. Não foi criado outro projeto ou adotado framework de recuperação.

## Causas e alterações mínimas por responsabilidade

| Defeito | Causa no código anterior | Correção incremental |
| --- | --- | --- |
| Página 3: palavras fora de ordem | `layout._physical_fragments()` usava distância horizontal como corte; a primeira correção ainda dependia de limite estreito. `reading_order()` promovia a continuação larga antes das palavras | Ordenação geométrica por linhas visuais e `x`, estilo e evidência de largura; offsets nativos acompanham cada fragmento. Gutters recorrentes e marcadores de listas mantêm separações legítimas |
| Página 13: citação em três registros | Gap de aproximadamente 26 pontos em fonte 11,25 excedia a regra de dois `em`; uma palavra justificada era tratada como coluna | `is_inline_continuation()` considera a linha larga que atravessa o intervalo; `_ordered_lines()` ordena os objetos. A citação inteira permanece numa unidade |
| Página 8: dois parágrafos unidos | A antiga `structure.segments()` verificava espaço vertical e tamanho de fonte, ignorando recuo e final curto de parágrafo | `composition.paragraph_break()` combina recuo, margem do corpo, linha anterior curta e pontuação terminal. Não há corte por caracteres/tokens |
| Hierarquia ausente no recorte | Os marcadores do livro desapareceram no PDF recortado; a classificação de seções exigia um capítulo já reconhecido | `hierarchy.layout_hints()` vincula o número grande centralizado ao título na mesma fonte; identifica os estilos de seção e uma subseção provisória |
| Citações e notas indiferenciadas | Recuo absoluto de `20%` da largura não reconhecia as citações a 97 pontos; chamadas sobrescritas eram ignoradas | Recuo relativo à margem do corpo, tamanho e proporção de itálico distinguem quatro citações. `special.link_special_elements()` liga seis chamadas sobrescritas a seis notas numeradas |
| 19 falsos candidatos de figuras | `build_structure()` copiava qualquer desenho, sem limites de página ou classificação | `graphics.drawing_elements()` preserva a caixa original, calcula a região visível e distingue 18 fundos brancos de layout e uma regra separadora |
| Bruto alterado e falta de mapa | `build_structure()` gravava `reading_order` dentro da página; a normalização registrava apenas antes/depois | A ordem derivada fica em `structure.page_reading_order`; `--raw-pages` copia o arquivo bruto sem reescrevê-lo. `normalization_map` liga cada intervalo limpo ao texto bruto e ao PDF |
| Falso conforto do relatório | `validate()` conferia cobertura e relações formais sem validar fronteiras visuais, hierarquia esperada, gráficos ou referências de notas | `validate_integrity()` é separado de `quality.assess_document()`. Falhas documentais bloqueiam o fluxo mesmo quando a cobertura bruta é integral |

## Casos de regressão e identificadores derivados

| Página local | Resultado atual | Ordem global | ID |
| --- | --- | --- | --- |
| 3, índice 2 | “Quando uma sociedade experimenta repetitivamente…” no parágrafo que começa em “Estórias falsas…” | 8 | `para_2132df9c18928f71a0f20a40` |
| 8, índice 7 | “Se escrevesse esse relatório…” termina em “emprego.” | 32 | `para_3bd4bbea6c13882c16abfcc9` |
| 8, índice 7 | “A placa sobre a porta…” é outro parágrafo, com continuação na página seguinte | 33 | `para_f312bc1ce3f790ac4458b49a` |
| 13, índice 12 | Uma citação completa, incluindo “pega acidentalmente aquela-coisa…” | 51 | `para_0a7b2d7830743a84b0bbda13` |

Os IDs derivam da versão e das fatias físicas; junções registram os IDs
predecessores no log. Os testes verificam essa derivação, a sequência, as
fronteiras e os vínculos, além do texto esperado.

## Demonstração completa: citação da página 13

Caminho: **obra → capítulo “O PROBLEMA DA ESTÓRIA” → seção “ESTÓRIA E VIDA” →
parágrafo 51, classificado `block_quote`**.

- Página local: índice 12; página física do recorte: 13.
- Bloco: `p000012_b00002`.
- Intervalo bruto no bloco: `[0,1121)`; na página: `[1175,2296)`.
- Caixa em pontos: aproximadamente `[97.24,307.23,512.49,485.43]`.
- Consulta integral: `inspection/pagina_13.json`.
- Regiões destacadas: `inspection/pagina_13.png`.
- Cada trecho normalizado tem um `normalization_map` com referências à página,
  bloco e intervalos de origem. `acidentalmente` conserva uma correspondência
  de identidade com os caracteres originais.

```bash
corpus paragraph Corpora/story-capitulo-1-revisao-documental-v0.2.0 \
  para_0a7b2d7830743a84b0bbda13
corpus render Corpora/story-capitulo-1-revisao-documental-v0.2.0 --page 13 \
  --paragraph para_0a7b2d7830743a84b0bbda13 --output /tmp/citacao-pagina-13.png
```

As imagens dos quatro casos foram conferidas visualmente. Isso é uma inspeção
pontual de limites e ordem, não uma conferência visual exaustiva do capítulo.

## Indicadores e critérios objetivos

| Indicador | Resultado |
| --- | --- |
| Páginas processadas | 18 de 18 |
| Blocos textuais cobertos | 97 de 97 |
| Parágrafos | 72 |
| Parágrafos de palavra única | 0 |
| Parágrafos atravessando páginas | 10 |
| Capítulos / seções / subseções | 1 / 6 / 1 |
| Citações formatadas | 4 |
| Notas finais / chamadas vinculadas | 6 / 6 |
| Desenhos tipados e com origem preservada | 19 de 19 |
| Artefatos de layout / regras separadoras | 18 / 1 |
| Erros formais / bloqueadores documentais automáticos | 0 / 0 |
| Pendências documentais | 14 |
| Testes automatizados | **63 passaram, sem falhas ou skips neste ambiente** |

`raw_integrity` verifica cobertura, preservação, offsets e transformações.
`documentary_quality` verifica ordenação visual, limites, tipos, hierarquia,
gráficos, notas e mapas. A cobertura de 100% dos blocos é apenas uma propriedade
da extração; não é um índice de qualidade documental.

| Estado | Critério |
| --- | --- |
| `blocked` | Algum erro de integridade, relação formal ou critério documental bloqueante |
| `review_required` | Esses critérios automáticos passaram, mas há casos inseguros pendentes |
| `approved` | Todos os critérios implementados passaram e não restam pendências identificadas; não significa fidelidade visual certificada |

`chunking_gate.allowed` só é verdadeiro quando **todos** os critérios registrados
em `blocking_criteria` passam, incluindo a ausência de casos inseguros pendentes.
Neste capítulo ele é falso. `corpus check-ready` retorna código **2** enquanto
esse bloqueio persistir. O teste positivo usa apenas um PDF sintético simples,
sem pendências, para verificar que a condição pode ser satisfeita.

## Testes e trilha de auditoria

- `tests/test_raw_integrity.py`: bytes do PDF/bruto/histórico, uma propriedade por
  caractere primário, intervalos físicos, mapa de origem, repetibilidade e detecção
  de alteração de hashes, inclusive numa segunda revisão incremental.
- `tests/test_documentary_regressions.py`: PDF real, páginas 3/8/13 e IDs derivados,
  hierarquia e ancestralidade de cada parágrafo, ordem visual, quatro citações,
  seis notas/chamadas, 19 geometrias e ausência de palavras órfãs.
- `tests/test_documentary_synthetic.py`: PDFs sintéticos, recuo em bloco único,
  justificação, ordem nativa invertida e proveniência não contígua, além de
  corrupções documentais que mantêm o bruto íntegro mas fecham o gate.
- Os 35 testes anteriores foram preservados; apenas o novo vocabulário de estados
  e a exigência de corroboração de hifenização alteraram contratos esperados.

Elementos `reference` — chamadas e representações das citações — apontam ao texto
primário; não contam como duplicações de conteúdo. A não sobreposição e a cobertura
são verificadas nos proprietários `primary` e nos parágrafos.

## Pendências e limitações

As 14 pendências são sete níveis hierárquicos por tipografia, quatro classificações
de citação, duas hifenizações e o glifo marginal “Ó” da página 7. Os sete níveis
compreendem seis seções e uma subseção; a subseção “Boa estória bem contada” é
explicitamente provisória. Os parágrafos herdam a necessidade de revisar seu
ancestral, sem perder seus vínculos.

As hifenizações ambíguas incluem `revela-`/`se` e `pré-`/`requisi-tos`; elas foram
mantidas e sinalizadas. O hífen lexical da longa expressão da página 13 foi
preservado, removendo apenas a quebra de layout quando a forma exata aparecia
também sem quebra no próprio bruto. A opção `--join-hyphens` exige corroboração
para remover um hífen e mantém essas alterações sob revisão.

Continuam limitados: layouts entrelaçados, texto não horizontal, fragmentos
repartidos em blocos nativos diferentes, casos de uma única linha que poderiam
ser colunas, fontes com mapeamento incorreto e fronteiras linguísticas de períodos.
NFC de casos Unicode complexos pode produzir mapas com intervalos de origem
agrupados, em vez de correspondência um a um.

A interface mostra o estado do gate e permite inspecionar o resultado; não inclui
um editor nem um fluxo de assinatura de aprovação humana. Por isso nenhuma
pendência foi marcada como aprovada apenas para liberar processamento posterior.

## Usar a entrega

Após encerrar o inspetor anterior com Ctrl+C, na pasta do repositório:

```bash
git pull --ff-only
source .venv/bin/activate
unzip -n story-capitulo-1-revisao-documental-v0.2.0.zip -d Corpora
corpus inspect Corpora/story-capitulo-1-revisao-documental-v0.2.0
```

Para reconstruir a partir dos seus arquivos anteriores, em uma pasta de saída nova:

```bash
corpus process Corpora/story-capitulo-1.pdf --pages 1-18 --merge-pages \
  --raw-pages Corpora/story-capitulo-1-corrigido/pages_raw.jsonl \
  --source-context examples/story_excerpt_context.json \
  --output Corpora/nova-revisao-documental
corpus validate Corpora/nova-revisao-documental
corpus check-ready Corpora/nova-revisao-documental
```

O último comando retorna 2 neste estágio. O JSON `metadata.json` deve acompanhar
`pages_raw.jsonl`, para conferir que a extração pertence ao mesmo PDF. Com fonte,
configuração e bruto diferentes, os IDs derivados também podem diferir dos exemplos.
