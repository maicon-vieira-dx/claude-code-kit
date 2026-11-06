# CHANGELOG do sistema de agentes

> Registro de mudanças em Skills / Rules / `CLAUDE.md`/`AGENTS.md` / estratégia de orquestração,
> **cada uma com o efeito medido** (CHARTER P9: mudança sem medição não é melhoria).
> Formato: data · alvo · o que mudou · origem (run-id/BACKLOG) · efeito (antes→depois no leaderboard).

## Template de entrada

```md
### YYYY-MM-DD — <alvo: ex. skill `bug-hunt`>
- **Mudou:** <descrição objetiva>
- **Origem:** <run-id / item do BACKLOG>
- **Hipótese:** <o que esperávamos melhorar>
- **Medição:** rodada `<run-id-antes>` (score X, custo Y) → `<run-id-depois>` (score X', custo Y')
- **Veredito:** melhora confirmada / neutra / regressão revertida
```

---

## Histórico

### 2026-07-31 — skill `plan-generation` (refatoração total: meta-skill planner+executor)
- **Mudou:** deixou de ser gerador de plano + triagem `a/b/c` e virou **plan mode desta conta**: enquadra,
  mapeia, decide, grava o plano e **executa**, verificando ao final. A regra "NUNCA implementar nesta
  skill" foi **revogada**. Triagem `a/b/c` substituída por **quatro decisões**: D1 modo de edição
  (batch vs per-file), D2 effort, D3 executor (com break-even numérico), D4 busca. 217 → 273 linhas
  (acima do teto de 220 do `struct-rules`, autorizado pelo usuário). Backup: `SKILL.md.bak`.
- **Origem:** rodada k=3 de 2026-07-30 (`runs/2026-07-30-k3-results.md`), 39 trials.
- **O que os dados revogaram:** "output domina a fatura" (é `cache_write`, 33–53%); rota (b) delegar
  fan-out ao Haiku (todo braço solo bateu todo braço que delega, dentro de cada cenário); `plano →
  /clear → executor frio` (2,5× mais caro que fazer quente); as cifras do S002 rodada 1 (medidor com
  preço de Claude 3).
- **O que os dados adicionaram:** D1 — o custo é bimodal e a estratégia de edição é a maior alavanca
  isolada (batch ~$0,088 vs per-file ~$0,205, faixas sem sobreposição em 15 trials controlados).
- **Medição:** ⚠️ **não medida.** É correção factual derivada de rodada existente, não uma variante
  testada. A própria D1 nasceu de **observação** dos traces, não de experimento com a estratégia como
  fator — por isso o S005 entrou como P0 no BACKLOG. A D4 (busca) é **derivada** das tarifas de cache,
  nunca observada — S006 no BACKLOG.
- **Veredito:** pendente. Fora do leaderboard por desenho, como a entrada de 2026-07-27.


### 2026-07-27 — skill `plan-generation`: registra o eixo `effort` (correção factual, SEM medição)
- **Mudou:** três fatos de plataforma que a skill omitia (205→208 linhas, teto 220):
  (i) `effort` governa **todo** o gasto da resposta, inclusive **nº de tool calls** — não é dial de
  thinking; (ii) **Haiku 4.5 não suporta `effort`** (API rejeita), logo executor barato não é
  barateável por effort e executor Sonnet é; (iii) trocar `effort` mid-sessão **invalida o prompt
  cache**. Novo campo `**Effort:**` no template do `## Execução`, acima de `Orçamento` (orçamento de
  tool calls sem effort é meta sem alavanca), e um `PROIBIDO` contra troca de effort na execução.
- **Origem:** pesquisa sobre o parâmetro `effort` (2026-07-27), não uma rodada. `grep -rl effort skills/`
  retornava **zero** — a omissão era do harness inteiro, não só desta skill.
- **Hipótese:** nenhuma. **Isto não é uma melhoria hipotética — é correção de omissão factual.**
- **Medição:** **NENHUMA, e deliberadamente.** Não há antes/depois no leaderboard porque não há
  hipótese de performance sendo testada: os três itens são verdades documentadas da plataforma,
  verdadeiras independentemente de rodada. Registrado aqui para rastreabilidade, **fora** do leaderboard
  — contá-lo como "melhoria medida" poluiria a disciplina do P9.
- **Veredito:** n/a (correção factual).
- **NÃO aplicado nesta entrada:** a hipótese de que baixar effort **estreita a janela da rota (b)**
  (delegação ao Haiku). É a H4 exploratória do **S004** e permanece fora da skill até os números de
  k=3 saírem — aplicá-la agora violaria P0 e a própria regra da skill.

### 2026-07-22 — grader `token-usage.mjs`: dedupe por `message.id`
- **Mudou:** o grader somava **cada linha de `usage`** do `.jsonl`, mas o log regrava a mesma mensagem
  assistant a cada snapshot de streaming (com `usage` parcial). Passou a contar **uma entrada por
  `message.id`** (maior snapshot); `usage_entries_raw` preserva a contagem pré-dedupe.
- **Origem:** rodada 2 do S002 (`runs/2026-07-22-S002-rodada2-results.md`).
- **Hipótese:** o custo medido estava inflado por um fator **∝ duração da mensagem** — logo correlacionado
  com o braço, não com o custo real.
- **Medição:** confirmado. Braço D: output 103.413 → **8.184 (12,6×)**. Rodada 1 recomputada: B1 t3
  $1.770 → **$0.136**. O ranking da rodada 2 **inverte**: bugado `C<A<D<F<B` → corrigido `D<C<A<B<F`
  (que bate com o pré-registro). Artefatos antigos mantidos como `tokens*-PRE-FIX.json`.
- **Veredito:** melhora confirmada — todo $/trial anterior a esta data é inválido em valor absoluto.

### 2026-06-25 — criação do subsistema `.claude/evals/`
- **Mudou:** introduzido o ambiente de avaliação contínua (framework + cenário S001 + templates + graders).
- **Origem:** pedido do usuário (desenho inicial).
- **Hipótese:** ter baseline reproduzível para medir evolução de Skills/Rules/CLAUDE.md e orquestração.
- **Medição:** baseline ainda não rodado.
- **Veredito:** N/A (fundação).
