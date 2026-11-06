# Estrutura e manutenção da skill `plan-generation`

## Pastas

| Pasta | O que mora ali | Quem lê |
| --- | --- | --- |
| `SKILL.md` | o protocolo: NUNCA, fases, regra curta de cada decisão, tabela de referências | o modelo, sempre que a skill é invocada |
| `references/` | conhecimento sob demanda: tabelas completas, dados medidos, porquês | o modelo, só no gatilho da tabela de referências |
| `templates/` | texto que sai da skill para outro lugar: o plano, o prompt de delegação | o modelo, na hora de escrever o artefato |
| `scripts/` | hooks e utilitários em Python (só biblioteca padrão) | o Claude Code (hooks) e quem roda os utilitários |
| `tests/` | `unittest` dos scripts | quem altera um script, antes de instalar |

## Teto do corpo do `SKILL.md`

Na compactação, cada skill invocada é recarregada com no máximo 5.000 tokens, cortando o fim. O corpo
(o `SKILL.md` sem o frontmatter) mede **~2,35 bytes por token**: 16 invocações reais, corpo injetado ÷
salto de contexto, faixa 2,08–2,95 (2026-10-14). Logo:

- Tudo que precisa sobreviver à recarga — NUNCA, Protocolo e a tabela de Referências — fica nos
  primeiros **11.500 bytes do corpo**. É o que o portão de cada plano mede.
- As decisões curtas vêm depois e podem ser cortadas: a versão completa está em `references/`.
- O plano 009 estimou 3,3 bytes/token e pôs o teto em 16.000 bytes; a medição acima o substitui.

## Antes de mudar qualquer script

```bash
cd ~/.claude/skills/plan-generation && python3 -m unittest discover -s tests
```

Precisa sair `OK`. Teste novo vai junto da mudança, no mesmo padrão de `tests/test_guard.py`.

## Por que o guard é registrado no frontmatter da skill

O `scripts/guard.py` aplica regras DESTA skill — o gate da D3 (seção NUNCA), o orçamento da D0 e a
medição de contexto —, então mora aqui e não no settings global: "registrado quando a skill é
invocada" é a definição exata de "esta sessão está sob a plan-generation". Os hooks de
`~/.claude/hooks/` são os invariantes de repo e de máquina, que valem com ou sem plano.

**Plano da sessão, não o mais recente.** O guard só obedece ao plano que a própria sessão gravou
(`Write`/`Edit`) ou leu (`Read`, na retomada) em `.claude/plans/`. O `budget-guard.sh`, que ele
substituiu, adivinhava pelo ".md mais recente nas últimas 6 h" e cobrou o orçamento de um plano contra
uma tarefa que não era dele (2026-09-04). Plano escrito por shell (heredoc) não vincula.

**Saída só em ASCII.** `json.dumps` sem `ensure_ascii=False`. No Windows o stdout do Python é cp1252:
o `⛔` da mensagem de deny levantava `UnicodeEncodeError`, o `2>/dev/null` engolia o erro, e o gate do
`budget-guard.sh` ficou morto sem ninguém ver até 2026-10-14. `tests/test_guard.py` roda o guard sem
`PYTHONUTF8` e decodifica a saída como ASCII estrito: a regressão reprova a suíte.

**Caminho absoluto e `test -f`.** `${CLAUDE_SKILL_DIR}` NAO e substituido no bloco `hooks:` (so no
corpo da skill e nas regras Bash de allowed-tools). E `python3` com script ausente sai com código 2,
que no PreToolUse significa NEGAR e no Stop significa BLOQUEAR — o `test -f` faz falhar aberto.

**Sem `once:`.** O PostToolUse conta toda chamada; o PreToolUse é gate (removido depois do primeiro
sucesso deixaria de ser gate); o Stop grava a calibração a cada turno.

**Polaridade.** Gate da D3: nega só o caso inequívoco; falha interna libera, com aviso uma vez por
sessão. Medição, orçamento e os módulos opcionais: nudge, abrem sempre. Stop: só registra.

**Módulos opcionais.** O `guard.py` importa `checkpoint`, `acumulo` e `calibracao` se existirem em
`scripts/`. Ausente = recurso desligado, nunca erro.

**Estado por sessão** em `<tmp>/claude-plangen-<session_id>.json`: base e contexto na invocação,
chamadas contadas, plano vinculado e avisos já emitidos (cada aviso sai uma vez por sessão).
