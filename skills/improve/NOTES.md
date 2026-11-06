# improve (shadcn) — staging, NÃO adotado

Baixado em 09/09/2026 de https://github.com/shadcn/improve (MIT).
Está em `skills-staging/`, **fora de `~/.claude/skills/`** — não entra na listagem
e não compete por trigger enquanto não for movido.

## Verificação feita

| Item | Resultado |
| --- | --- |
| Installs (coluna `Installs`, não `8W Activity`) | 32,5K |
| Stars / forks / watchers | 9.095 / 408 / 35 |
| Manutenção | criado 10-jun-2026, último push 15-jun-2026; 17 issues abertas |
| Scripts / hooks / rede | zero — só markdown. Nenhum `.sh/.py/.mjs`, nenhum hook, nenhum `curl`/`fetch` |
| Licença | MIT |
| Stack | agnóstico; roda em Angular/Nx sem atrito |

## O que NÃO foi baixado

`.claude-plugin/plugin.json` e `marketplace.json` — o plugin só embrulha este mesmo
skill, não entrega comando nem hook. `README.md` — é a página de pitch, redundante
com o `SKILL.md`.

## O buraco que ele preenche

Nenhuma skill pessoal olha o **repo inteiro** e devolve "estas N coisas valem a pena,
nesta ordem". Todas partem de um diff, uma branch ou uma tarefa já nomeada. A variante
`next`/`roadmap` (direção de produto ancorada no código) idem.

## O que revisar antes de mover para `skills/`

1. **Descrição rouba trigger.** O frontmatter diz "audit a codebase, find improvement
   opportunities (bugs, security, performance…)" — colide de frente com `bug-hunt`
   (diff antes do PR) e `bug-diagnosis` (sintoma acontecendo). Estreitar para o caso
   de survey/direção antes de ativar.
2. **Variantes redundantes.** `branch` → já é `bug-hunt` + `/code-review`.
   `plan <desc>` e `execute <plano>` → já são `plan-generation`, que decide as 6
   variáveis de custo e tem o `budget-guard.sh`. Remover ou redirecionar.
3. **Sem teto de tool calls.** `deep` = até 8 Explore concorrentes, sem limite de
   chamadas. Em monorepo de 66 projetos isso queima a janela (precedente: 1,06M tokens
   no `bug-hunt` antes da tabela de dimensionamento). Aplicar teto no mesmo molde.
4. **Diretório de planos.** Ele escreve em `plans/` na raiz; aqui é `.claude/plans/`.
5. **Ordem spec → teste → código.** O `plan-template.md` não tem essa noção, e ela é
   inegociável no repo. Precisa entrar no template e nas done criteria.

## O que ele tem de bom (vale copiar mesmo se o skill não for adotado)

- Vetting explícito contra as 3 classes de falso positivo de subagente: comportamento
  by-design, evidência mal-atribuída, duplicata entre agentes.
- "Excerpts vêm da sua própria leitura, nunca do relatório do subagente."
- Stamp de `git rev-parse --short HEAD` em cada plano, para detecção de drift.
- Regra de que achados de credencial citam `file:line` + tipo, nunca o valor.
- `references/audit-playbook.md` é o ativo mais reaproveitável — serve como
  `references/` do `plan-generation` mesmo sem adotar o skill.

## Para ativar

    mv ~/.claude/skills-staging/improve ~/.claude/skills/improve

Vai a 13 skills pessoais. O teto que dói é o de 25K tokens re-anexados na compactação,
não a contagem — o `SKILL.md` tem 15KB, então ele sozinho passa do limite de 5K por
skill e perde parte de si na primeira compactação. Mais um motivo para enxugá-lo antes.
