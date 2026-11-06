# Livro-razão — o que o harness já mediu

> Fonte única dos achados de S001–S005. Cenário novo **parte daqui**: não re-mede o que está
> "estabelecido", e só mede de novo o que está "k=1" ou "não medido". Tarifa: `prices_version
> 2026-08-14-real` (Sonnet 3/15/3,75/0,30 · Haiku 1/5/1,25/0,10 · Opus 5/25/6,25/0,50 US$/M).
>
> **Os arquivos da coluna "Fonte" foram apagados em 2026-09-25** (cenários S001–S005, `runs/` e
> results), por decisão do dono. Este arquivo passou a ser o registro: os números aqui são citações
> conferidas antes da remoção, e a "Fonte" fica só como procedência histórica.

## Grau de evidência

- **estabelecido** — k=3, faixas separadas, mecanismo explicado. Não re-medir.
- **mecanismo k=1** — propriedade observada dentro de uma sessão (vale a k=1); ordem entre braços não.
- **não medido** — dedução, tese externa ou braço que nunca rodou.

| # | Fato | Regime | Evidência | Fonte |
|---|---|---|---|---|
| F1 | Custo é bimodal: loop de shell (~4 calls, US$0,088) vs arquivo-a-arquivo (~24 calls, US$0,205); faixas não se sobrepõem em 15 trials | mecânico 8–12 arq. | estabelecido | runs/2026-07-30-k3-results.md §"custo é bimodal" |
| F2 | `--effort` é seletor de estratégia, não dial de custo: P(batch) low 2/3 · medium 1/3 · high 0/3 · xhigh 0/3; calls 4→20→24→25 | mecânico | estabelecido | idem, S004 |
| F3 | Solo quente bateu todo braço com delegação (plano→frio 2,5×; 3 subagentes 3,3×) | mecânico | estabelecido | idem |
| F4 | Opus-solo não é o mais caro no mecânico (3º de 6; 1,29× Sonnet-solo) | mecânico | estabelecido | idem, S002-E |
| F5 | Fidelidade 39/39 — o regime mecânico não discrimina qualidade | mecânico | estabelecido | idem |
| F6 | Rubrica dominante muda com o regime: mecânico `cache_write`; construção solo/plano→frio **output**; construção com subagentes paralelos **`cache_read`** | todos | mecânico estabelecido; construção mecanismo k=1 | runs/2026-09-03-S001-results.md Achado 1 |
| F7 | Plano→executor frio Haiku move a janela crescente para o modelo barato: `cache_read` do Sonnet cai para 23,8% | construção 21 arq. | mecanismo k=1 | idem Achado 2 |
| F8 | Subagente que devolve arquivo (não resumo) obriga o pai a reintegrar: Edit÷Write do pai 8,00; ~70 erros de tsc | construção | mecanismo k=1 | idem Achado 3 |
| F9 | Plano com conteúdo literal por arquivo → executor frio com 0 Edit | construção | mecanismo k=1 | idem Achado 4 |
| F10 | Ordem de custo P < S < M na construção (P 0,89× S) | construção | **k=1 — não é ranking** | idem |
| F11 | Troca de modelo no meio da sessão (swap) | — | **não medido** (braço G nunca rodou; não há post do Akita que meça swap — o que ele mede é planejador+executor) | S003/EXPERIMENT.md H1 |
| F12 | Subagente por camada, em série, com contrato de retorno destilado (topologia prescrita pela D3 da plan-generation) | — | **não medido** | plan-generation SKILL.md D3 |
| F13 | Multiplicador 2× do TDD na fórmula D0 | — | **não medido** (nenhum trial teve ciclo de spec executado) | BACKLOG P0 "TDD como fator" |
| F14 | Grader com `grep -r` sem `-h` tem filtro de comentário morto | harness | estabelecido | runs/2026-09-03-S001-results.md |

## Externos (corroboram, não substituem medição)

- Anthropic, sistema multiagente: ~15× tokens de chat; tokens explicam ~80% da variância.
- Anthropic, doc de effort: subagente em tarefa mecânica não precisa do effort do orquestrador.
- Anthropic, prompt caching: cache é chaveado pelo prefixo do request; trocar de modelo reescreve o cache.
- Akita, "LLM benchmarks — vale a pena misturar 2 modelos" (25/04/2026): planejador caro + executor
  barato pode ganhar, mas em outro benchmark dele a delegação **nem disparou** em 7/7 runs.

## Números superados (não citar)

- `runs/2026-07-17-S002-k3-results.md` e `runs/2026-07-22-S002-rodada2-results.md`: tarifa de
  geração anterior. Superados em 2026-07-30.
