# Correção A — palavras justificadas separadas em parágrafos

Versão da aplicação: **0.1.1**. Fonte do teste real: `story-capitulo-1.pdf`,
página física 3, correspondente à página física 21 do livro completo.

## Causa

O bloco que começa em “Estórias falsas e defeituosas…” contém uma linha visual
com “poderosa. Quando uma sociedade experimenta repetitivamente”. O PyMuPDF a
representa em seis objetos `lines`, com espaços horizontais de aproximadamente
16,2 pontos entre suas caixas. Esses objetos não são seis linhas tipográficas.

O código separava qualquer gap horizontal acima de 12 pontos. A continuação que
começa em “repetitivamente” se tornava um fragmento largo, promovido na ordenação
antes das palavras intermediárias. Daí os registros indevidos 9–13 relatados.

## Correção

- Fragmentos alinhados da mesma linha, em ordem horizontal e com espaçamento
  compatível com o tamanho da fonte permanecem no fluxo do mesmo bloco.
- Uma faixa branca recorrente em várias linhas preserva a separação de colunas,
  inclusive com gutter pequeno; marcadores de itens impedem a junção de listas.
- Mudança de fonte ou tamanho dentro da mesma linha não abre outro parágrafo.
- A normalização reaproveita o espaço já presente antes de um separador de objetos,
  evitando duplicá-lo. A transformação registra `before`/`after`.
- A extração bruta e seus offsets são preservados. O evento
  `inline_line_reconstruction` registra a decisão geométrica.

O validador agora rejeita `inline_paragraph_split` e `inline_reading_order`.
O corpus antigo, que passava na validação de cobertura, apresenta cinco ocorrências
do primeiro erro e uma do segundo. Cobertura integral não basta para atestar fluxo.

## Resultado no capítulo

O trecho pertence integralmente ao **parágrafo global 8**, que começa em
“Estórias falsas e defeituosas…”. A sequência é:

> …poderosa. Quando uma sociedade experimenta repetitivamente pseudoestórias…

No corpus gerado do PDF de 18 páginas, o identificador é
`para_e819e28b37515935f9211f2f`. A origem tem `page_index = 2`, bloco
`p000002_b00002`, intervalo local `[0,880)` e intervalo na página `[859,1739)`.
Sua caixa é aproximadamente `[76.99,299.38,535.02,522.99]` pontos.
Os IDs da versão anterior permanecem apenas no corpus histórico: a mudança de
implementação e segmentação gera nova versão, sem sobrescrever registros antigos.

| Verificação | Resultado |
| --- | --- |
| Páginas extraídas | 18 de 18 |
| Blocos textuais preservados e classificados | 97 de 97 |
| Parágrafos antes / depois | 78 / 73 |
| Parágrafos atravessando páginas | 10 |
| Palavras isoladas “Quando”, “uma”, “sociedade”, “experimenta” na página 3 | Nenhuma |
| Consistência do corpus corrigido | Zero erros |
| PDF de entrada | Bytes preservados |
| Extração do livro completo, no mesmo recorte | Texto bruto e blocos idênticos em todas as 18 páginas |
| Suíte automatizada | **35 testes passaram**, sem skips neste ambiente |

O corpus derivado do PDF do capítulo mantém **51 alertas** e estado
`review_required`. A correção desse erro não certifica toda a segmentação da obra.
Os hífens, as classificações incertas e as demais limitações continuam registradas.

O ZIP `story-capitulo-1-corpus-corrigido.zip` inclui os oito artefatos documentais,
o registro integral do parágrafo em `inspection/problema-a-paragrafo.json`, sua
imagem de origem em `inspection/pagina-3-corrigida.png` e este relatório. A marcação
foi comparada com a página renderizada. A estrutura sem marcadores do PDF recortado
continua sujeita às limitações de hierarquia já documentadas.

## Reproduzir localmente

Após encerrar o inspetor antigo com Ctrl+C, na pasta do projeto:

```bash
git pull --ff-only
source .venv/bin/activate
corpus process Corpora/story-capitulo-1.pdf --pages 1-18 --merge-pages \
  --output Corpora/story-capitulo-1-corrigido
corpus inspect Corpora/story-capitulo-1-corrigido
```

A pasta de saída deve ser nova. Alternativamente, extraia o ZIP corrigido dentro
de `Corpora/` e use diretamente `corpus inspect Corpora/story-capitulo-1-corrigido`.
Não é necessário alterar ou extrair novamente o PDF para esta correção.

## Limites da regra

A regra cobre objetos adjacentes do mesmo bloco com direção horizontal. Fragmentos
em blocos distintos, ordem nativa horizontal invertida e duas colunas de uma única
linha com gap pequeno ainda podem exigir revisão. Não foi introduzida interpretação
semântica, segmentação por tokens ou vetorização.
