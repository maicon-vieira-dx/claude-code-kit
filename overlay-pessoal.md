# Overlay pessoal (Claude Code)

Camada individual, fora do repo (mora em `~/.claude/`). Complementa o
`CLAUDE.md` do repositório — não o substitui. Importado no repo por um `CLAUDE.local.md` com a linha
`@~/.claude/overlay-pessoal.md`.

Três mecanismos pessoais, com custos diferentes — a escolha entre eles não é estética:

| Mecanismo | Onde | Como dispara | Custo |
| --- | --- | --- | --- |
| **Skill** | `~/.claude/skills/` | Pela `description` — **e por glob, se declarar `paths:`** | Uma entrada na listagem, **sempre**. Corpo só ao disparar |
| **Rule** | `~/.claude/rules/` | Por glob de `paths:`, ao tocar o arquivo | Zero de listagem. Mas o corpo inteiro entra em contexto quando casa |
| **Hook** | `~/.claude/hooks/`, ligados em `.claude/settings.local.json` | Determinístico, no evento | Zero de contexto; é a única garantia de verdade |

**O gatilho deixou de ser o critério** (verificado na doc em 04/09/2026). Skill aceita `paths:` desde
que o campo existe, então "skill dispara por descrição, rule por glob" virou falso. O que separa os
dois hoje são duas outras coisas:

| Pergunta | Resposta → mecanismo |
| --- | --- |
| Precisa de corpo grande, ou de arquivos sob demanda em `references/`? | **skill** — só ela tem os três níveis de carregamento |
| É meia dúzia de linhas que valem sempre que o glob casa? | **rule** — não paga entrada na listagem |
| Precisa acontecer **sempre**, sem depender de decisão do modelo? | **hook** — os outros dois são contexto, não garantia |

**Converter as 5 rules em skills com `paths:` está descartado**, e o motivo é medido: o nome da skill
**nunca** sai da listagem (só a `description` é descartada, começando pelas menos invocadas), então
5 rules viram 5 entradas permanentes em troca de nada — as rules já são pequenas e não precisam de
corpo sob demanda. Skill com `paths:` vale para o caso inverso: conhecimento **grande** de uma camada,
que hoje não caberia numa rule.

**E o "já no teto" era falso.** São **10** skills neste kit (o diretório `synced/` é bucket interno
do produto, não skill), não 15–25, e o orçamento é 1% da janela
(ajustável por `skillListingBudgetFraction`), não um número fixo. O teto que de fato dói é outro: na
compactação, cada skill é re-anexada com no máximo **5.000 tokens**, e o conjunto com **25.000** —
preenchido da mais recente para a mais antiga. É por isso que `plan-generation` foi dividida em
`references/`: ela sozinha passava de 8.000 tokens e perdia um terço de si na primeira compactação.

Medir com `/doctor` e a linha **Skills** do `/context` — nunca por instinto.

Hooks vivos — os 8 que algum arquivo de settings de fato registra: `git-stash-guard`,
`graphify-gate`, `vitest-pool-gate` e `route-a-no-subagent-guard` (PreToolUse); `subagent-router`
(SubagentStart); `circuit-breaker` e `dead-pointer` (PostToolUse); `stop-check` e `turn-cost`
(Stop). **São os invariantes de repo e de máquina** — valem em toda sessão, independentemente do
que se esteja fazendo.

**A polaridade quando um hook não consegue atestar é por classe, não uniforme** (21/09). Deny-gate
de dado ou segurança (`git-stash-guard`, `vitest-pool-gate`) **nega**, mas só no escopo do padrão
de risco — senão um payload quebrado derruba comando sem relação. Deny-gate de escopo
(`graphify-gate`) mantém o dual: interpretador morto libera, contagem que não parseia nega.
Nudge (`circuit-breaker`, `dead-pointer`, `turn-cost`) **abre**. `stop-check` **bloqueia** quando
o checker está ausente, porque ali silêncio era lido como "compilou". Hook de injeção
(`subagent-router`) é **fail-open em todo caminho**: falhar fechado seria perder a instrução sem
ninguém perceber. Em todos, o aviso sai **uma vez por sessão por hook** — por invocação, a falha
recorrente dispararia o próprio `circuit-breaker`. E todo hook que nega **entrega o remédio junto**.

Em disco e **não registrados por escolha**: `ngc-touched-libs.sh`, `ngtsc_template_check.py`,
`graphify-gate.py` e `vitest-pool-gate.py` não são órfãos — são bibliotecas chamadas por outro
hook via stdin. **Órfão de verdade é hook que nenhum settings registra e nenhum hook chama**, e hoje
não há nenhum (`posttooluse-lint.sh` foi apagado em 21/09: duplicava o `lint-fix.mjs` do repo, que
está registrado).

**A lista acima só vale se casar com o disco.** O comando que reprova:

```bash
for h in ~/.claude/hooks/*.sh ~/.claude/hooks/*.py; do n=$(basename "$h")
  grep -qs "$n" ~/.claude/settings.json .claude/settings.local.json .claude/settings.json \
    || grep -qs "$n" ~/.claude/hooks/*.sh || echo "ORFAO: $n"; done
```

Saída vazia passa. Prosa que afirma hook que não executa é um modo de falha real — e o `dead-pointer` não pega, porque ele só dispara quando
**este** arquivo é editado.

**Hook de skill é outra coisa, e mora dentro dela** (`skills/<nome>/scripts/`, registrado no
`hooks:` do frontmatter): só existe depois que a skill é invocada, e some quando a sessão acaba.
Use quando o invariante é **da skill**, não do ambiente — assim ele não vira hook órfão nem dispara
em sessão que não tem nada a ver. Hoje há um: `plan-generation/scripts/guard.py` (gate da D3, orçamento e
medição de contexto). **Não use `${CLAUDE_SKILL_DIR}` no bloco `hooks:`** — ele não é substituído ali; caminho
absoluto, sempre precedido de `test -f "<caminho>" || exit 0`, porque interpretador com script
ausente sai com código 2, e código 2 significa **negar** no `PreToolUse` e **bloquear** no `Stop`.

**Antes de criar skill nova, pergunte se não é rule — ou hook.** Conhecimento de camada pequeno
(acessibilidade, performance, API de framework) tem arquivo para se pendurar → rule. Procedimento com
momento próprio de invocação, ou conhecimento grande que precisa de `references/` → skill. E o que
precisa valer **sempre**, sem depender de o modelo escolher → hook: prosa é probabilística.

## Roteamento pessoal (skills em `~/.claude/skills/`)

| Vou trabalhar em…                                          | Use                          |
| ---------------------------------------------------------- | ---------------------------- |
| Planejar **e executar** implementação não-trivial (plan mode) | skill `plan-generation`   |
| Validar comportamento visual por screenshots               | skill `playwright-validation`|
| Caçar bug no diff **antes** de abrir PR                     | skill `bug-hunt`             |
| Achar a causa de um bug que **já** está acontecendo         | skill `bug-diagnosis`        |
| Buscar qualquer coisa dentro de `libs/`                     | skill `graphify-search`      |
| Aprender um mecanismo do repo a ponto de escrever um igual  | skill `aula-de-codigo`       |
| Editar `CLAUDE.md`/`AGENTS.md`/`SKILL.md`/`.claude`         | skill `struct-rules`         |

**A fronteira que mais erra:** `bug-hunt` é diff que ainda não subiu; `bug-diagnosis` é sintoma que já aconteceu. Fixtures de trigger para esse e outros pares em `~/.claude/evals/trigger/`.

## Rules pessoais (`~/.claude/rules/`, disparam por glob)

| Rule | Dispara ao tocar | Assunto |
| --- | --- | --- |
| `libs-graphify` | `libs/**` | Busca obrigatória via graphify antes de ler ou editar |
| `angular-referencia` | `*.component.ts`, `*.service.ts`, `*.store.ts`, `*.guard.ts`, `*.resolver.ts` | API que existe na v19 — e o que **não** existe (Signal Forms é v21, `@angular/aria` não está instalado) |
| `acessibilidade` | `*.component.html/.ts`, `libs/**/ui/**` | WCAG 2.2 AA, foco em formulário e alvo de toque no PWA |
| `performance-web` | apps, `*.routes.ts`, `main.ts` | Boot do PWA de campo e INP do painel administrativo — não performance de página pública |
| `offline-first` | apps PWA, `*.store.ts` | Fila durável, idempotência de retry, o que já existe no `package.json` |

São pessoais: não estão no repo. As quatro últimas pressupõem um monorepo Angular/Nx — ajuste os globs ao projeto em que forem usadas.

**Pedido composto = mais de uma skill.** Um pedido pode disparar várias linhas da tabela; invocar **todas**, nunca só a mais óbvia.

**A skill é o padrão, não a sugestão.** Se a tabela cobre a tarefa, a saída sai do protocolo da skill — improvisar "porque é rápido" é o erro; skill existe justamente para o que parece simples. Nada de padrão de saída mora só em memória: memória é lembrete, skill é protocolo.

## Notas operacionais (pessoal)

- Higiene de output em Bash: comando verboso (`nx ... --verbose`, `test` com log longo, `install`) infla o contexto e cada tool call seguinte re-lê isso a preço de cache. Não use `--verbose` por padrão; redirecione saída grande para arquivo (`> /tmp/... 2>&1`) e leia só o trecho necessário (`tail`/`grep`).

- **Toda rodada de Vitest leva `--pool=forks --minWorkers=1`.** O pool padrão (`threads`) segfaulta (exit 139) na máquina do autor (Windows), e `pool` **não tem variável de ambiente** — só flag de CLI ou arquivo de config. Config de pool **não deve ser versionada** (é problema desta máquina, não do time), então a flag é o caminho. Vale para `nx test`, `nx run <proj>:test`, `nx run-many -t test` e `vitest` direto. **Nunca `--poolOptions.forks.minForks=1`:** o yargs do Nx aninha flag pontilhada e o `@nx/vite` a re-serializa como JSON string, que o Vitest ignora — o `RangeError` volta. O teto já vem de `VITEST_MAX_FORKS=2` do ambiente: **não** passe `maxForks`, **não** defina `VITEST_MIN_FORKS`. Enforcement: hook `vitest-pool-gate` (nega e devolve o comando corrigido). 
