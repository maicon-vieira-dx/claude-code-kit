> Template da skill `plan-generation`. **Abrir quando** for gravar o arquivo em
> `.claude/plans/<slug>.md`. Contém: o template literal, seção a seção.

# Template do plano

```markdown
# Plano: <título>

## Problema
<1–2 frases: o que muda e critério de pronto>

## Decisões de execução
- **D1 modo de edição:** batch | per-file — <justificativa>
  - <se batch: o comando exato + contagem esperada antes/depois>
- **D0 — Orçamento:** ~T tool calls no total (execução: ~E · já gastas: ~J)
  - <a conta, com o número de cada termo: A_lógica, A_simples, G_camadas → D0_exec = E; +J = T>
- **D2 profundidade:** baixa | média | alta — <justificativa>
- **D3 executor:** eu, mesma janela | subagente por camada, em série | usuário
  - **Regime:** dentro | fora — <arquivos, camadas, TDD sim/não, `D0_exec`>
  - <se FORA do regime: a conta de break-even é OBRIGATÓRIA aqui — tokens poupados × calls restantes>
- **D5 formato do plano:** decisão | literal por artefato | operação — <decorre da D3>
  - <se literal: confirmar que TODO passo abaixo carrega o bloco de código, não a descrição da ação>
- **D4 busca:** graphify-search | Read inline | Explore — <justificativa>
- **D6 contexto:** na invocação ~C (base ~B · sujo ~S) — <os números que o guard informou>
  - <checkpoints previstos: depois dos passos N, M — limites naturais, com gate verde>
  - <se o guard recomendou checkpoint de entrada: a conta dele e o que foi feito>

## Contexto a carregar
- **Skills (na ordem):** <ex.: skill-de-componente → skill-de-acesso-a-dados>
- **Docs:** <só os relevantes, ou "nenhum">
- **Regras (auto por glob):** <ex.: frontend-angular.md rege o arquivo X>

## NÃO ler / NÃO tocar
- <ruído; legado intocado>

## Arquivos-alvo
- `caminho/exato.ts` — <o que muda>

## Estratégia
Cada passo é uma **fatia vertical** — entrega comportamento observável ponta a ponta, não uma camada
horizontal inteira. "Todos os DTOs, depois todos os handlers" só é verificável no fim; "um caso de uso
completo" é verificável hoje.

1. **<passo>** — `arquivo/exato.ts` — <ação>
   - **Depende de:** <passo N, ou "nada">
   - **GATE:** `<comando>` → `<output esperado>`
   - **Aceite:** <o fato verificável que prova este passo, não "implementado">
   - <se D5 = literal: o bloco de código completo do arquivo, com os imports resolvidos — o executor
     transcreve, não interpreta>

## Estado (atualizar a cada passo fechado)
- **Passos fechados:** <N> de <M> — em números: é o que o guard lê para estimar as chamadas restantes
- **Aprovado:** <data do ExitPlanMode aprovado — libera a retomada sem novo plan mode>
- **Próximo passo:** <o único a executar agora — número + o que fazer>
- **Tentativas no passo atual:** <0–3>
- **Descobertas que mudam o plano:** <o que se aprendeu lendo o código e contradiz o que foi assumido>
- **Último checkpoint:** <data · janela antes do /clear · conta do guard — só se houve>

## Invariantes em risco
- <proibido `any`; isolamento por ID; updateState imutável>
- <enums/DTOs: valores exatos conferidos na fonte e listados aqui>

## Verificação (comando → output esperado)
- `npx ngc --noEmit -p <lib>/tsconfig.lib.json` → sem erros nos alvos
- `npx nx run <project>:lint --fix` → limpo
- `git diff` → sem `: any` / `as any`
- `python3 ~/.claude/skills/plan-generation/scripts/calibracao.py --plano <este arquivo>` → colar a linha
  `D0: previsto N / real M …` (calibra a D0 e a D6)
- Só se D3 = subagente — modelo efetivo de cada um (o apelido muda de modelo entre versões do CLI):
  `grep -ho '"model":"[^"]*"' ~/.claude/projects/<pasta-do-projeto>/<id-da-sessão>/subagents/*.jsonl | sort | uniq -c`
  → registrar o id
- STOP se: <condição de parada>

## Testes
- <spec a criar/atualizar — caminho + caso feliz + exceção de domínio>

## Critérios de aceite
- [ ] <verificável por comando>
```

---
