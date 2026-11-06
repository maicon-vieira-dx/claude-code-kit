# Claude Code kit

A personal set of Claude Code skills, hooks, rules and settings, plus a small framework for measuring the cost and quality of agent setups. It was written for daily work in an Angular/Nx monorepo on Windows, then cleaned of project-specific content. Some files still assume that stack (see "Known limits").

## Contents

| Path | What it is |
| --- | --- |
| `CLAUDE.md` | Global instructions (the `/graphify` trigger). |
| `settings.json` | Global settings: model, effort, three global hooks, one plugin. |
| `settings.local.repo-exemplo.json` | Per-repository permissions and hook wiring (copy to `<repo>/.claude/settings.local.json`). |
| `overlay-pessoal.md` | Notes on choosing between skill, rule and hook, plus skill routing (in Portuguese). |
| `skills/` | 8 skills (below). |
| `hooks/` | 14 files (Python, Bash, Node): guards, nudges and helper libraries called by other hooks. |
| `rules/` | 5 glob-triggered rules (accessibility, Angular API reference, offline-first, web performance, graphify search). |
| `evals/` | Charter, ledger of findings, five Node graders, trigger fixtures, backlog. |

### Skills

`aula-de-codigo` (teaching a mechanism step by step), `bug-diagnosis` (root cause of an existing bug), `bug-hunt` (multi-agent review of a diff with a refutation step), `graphify-search`, `plan-generation` (planning plus execution, with scripts and tests), `playwright-validation`, `struct-rules` (safe editing of CLAUDE.md, skills and rules), and one adapted skill, `improve`.

## Install

1. Copy `skills/`, `hooks/`, `rules/` to `~/.claude/` (merge with what you have).
2. Merge `settings.json` into `~/.claude/settings.json`. Hook commands use `$HOME/.claude/hooks/...` and, for Python hooks, a Windows path under `$LOCALAPPDATA`; change it to your interpreter.
3. Copy `settings.local.repo-exemplo.json` to a repository as `.claude/settings.local.json`. Add `@~/.claude/overlay-pessoal.md` to that repository's `CLAUDE.local.md` if you want the overlay.
4. Requirements: Python 3 (as `python3`), Node 20+, Git Bash on Windows, and `graphify` (`pip install graphifyy`) for `graphify-search` and the `graphify-gate` hook.

Review every hook before enabling it: they can deny tool calls.

## Evals: results and limits

`evals/FATOS.md` is the ledger. In the mechanical regime (edits across 8 to 12 files), the ledger records 39 trials with 39/39 passing fidelity checks. In that regime a single warm agent cost 2.5x less than a plan handed to a cold executor and 3.3x less than three subagents. Cost split into two bands that did not overlap across 15 trials (about US$0.09 for a shell loop versus US$0.21 file by file), and `--effort` changed the strategy more than the cost.

Limits, stated plainly:

- The raw runs and result files were deleted in 2026-09; the ledger holds the author's transcribed numbers. They cannot be re-checked from this repository.
- Each arm had k=3 or fewer trials, one prompt family, one model family, and prices from a single date.
- Fidelity was 39/39, so the regime says nothing about quality differences.
- Construction tasks were k=1 and give mechanisms, not a ranking. A later replay scenario on real PRs (S010) is not included; the graders that process it (`consolidar-s010.mjs`, `aceite-funcional.mjs`, `verificar-relatorio.mjs`) need scenario folders that are not here.
- The 2.5x to 3.3x range applies to mechanical tasks only.

## Known limits of the kit

- Some rules and skills assume Angular and Nx (`libs/`, `*.component.ts`). Adjust globs and examples.
- Several files are written in Portuguese.
- Some skills and docs mention skills not shipped here (for example a component skill) as examples.
- Left out on purpose: skills tied to a specific team workflow (ticket tracker and pull-request conventions), the skill that depends on the missing S010 data, and personal memory files.

## Credits

- `skills/improve`: by shadcn, MIT (`skills/improve/LICENSE.md`), https://github.com/shadcn/improve. Adapted here.
- Not included (third-party, referenced only): `graphify` by safishamsi (Apache-2.0 / MIT), https://github.com/safishamsi/graphify; `find-skills` from vercel-labs/skills (MIT), https://github.com/vercel-labs/skills. Install them from their origin.
- Eval charter follows Anthropic's public article "Demystifying evals for AI agents".

## License

MIT, see `LICENSE`. `skills/improve` keeps its own MIT notice.

## Resumo em português

Kit pessoal de Claude Code: 8 skills, 14 arquivos de hooks, 5 rules, configurações e um framework de evals de custo e qualidade de agentes. Foi escrito para um monorepo Angular/Nx no Windows e depois limpo de conteúdo de projeto. Nos evals, em tarefas mecânicas (39 trials, todos com fidelidade ok), um agente único saiu 2,5 a 3,3 vezes mais barato que a delegação. Limites: os dados brutos foram apagados, com no máximo 3 repetições por braço, e a faixa vale só para tarefas mecânicas. A skill `improve` (shadcn, MIT) é adaptada; `graphify` e `find-skills` são de terceiros e ficam de fora. Instalação: copie `skills/`, `hooks/` e `rules/` para `~/.claude/` e mescle os settings.
