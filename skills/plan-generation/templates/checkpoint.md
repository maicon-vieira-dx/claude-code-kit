> Template da skill `plan-generation`. **Abrir quando** o guard disser `CHECKPOINT COMPENSA`, ou ao fechar
> um passo. Contém: o que o `## Estado` precisa carregar para a sessão nova continuar sem a conversa, e a
> frase de entrega.

# Checkpoint

A sessão nova terá só o plano e os arquivos em disco. O que você sabe e não está num dos dois se perde no
`/clear` — escreva antes.

## `## Estado` no momento do checkpoint

```markdown
## Estado (atualizar a cada passo fechado)
- **Passos fechados:** <N> de <M>
- **Aprovado:** <data do ExitPlanMode aprovado>
- **Próximo passo:** <número + o que fazer, com o primeiro comando>
- **Tentativas no passo atual:** 0
- **Descobertas que mudam o plano:** <o que o código revelou e o plano ainda não diz — nome real de campo,
  assinatura, padrão divergente; uma linha cada>
- **Já verificado (não refazer):** <gates verdes e o comando de cada um>
- **Último checkpoint:** <data> · janela <contexto> (base <base>) · conta do guard: <ganho> > <custo>
```

## Antes de entregar

- [ ] O passo corrente fechou (gate verde), ou o `## Estado` diz exatamente onde ele parou.
- [ ] Toda decisão tomada durante a execução está no plano (D0–D6 atualizadas, se mudaram).
- [ ] Nada essencial mora só na conversa: releia "Descobertas" como se você fosse a sessão nova.

## Frase de entrega (literal)

> Checkpoint gravado em `.claude/plans/<slug>.md` (passo <N> de <M>). Rode `/clear` e depois
> `/plan-generation retomar <slug>`.
