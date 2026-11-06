# Evals de trigger

Trilha separada dos cenários `S00x`. Aqueles medem **execução** (o agente resolveu a tarefa?); estes medem **roteamento** (a skill certa disparou?).

Exigidos pela `struct-rules` para toda skill que auto-dispara **e** tem irmã de gatilho encostado. Skill com `disable-model-invocation: true` é isenta — não disputa gatilho. Rule também é isenta: dispara por glob, não por descrição.

## Como rodar

Sem runner. Cada fixture é uma tabela de prompt → dono esperado. O procedimento:

1. Sessão limpa (`/clear`).
2. Cole **um** prompt, literal, sem contexto adicional.
3. Anote qual skill foi invocada — ou nenhuma.
4. Compare com a coluna **Dono esperado**.

Rodar em lote na mesma sessão contamina o resultado: a skill invocada no prompt 1 enviesa o 2.

## Critério que reprova

Por fixture, sobre os prompts que **têm** dono esperado:

- **Recall** — o dono esperado disparou. Abaixo de **8/10**, a `description` do dono não cobre o vocabulário real.
- **Precisão** — a irmã **não** disparou onde não devia. Qualquer invasão em prompt marcado `NÃO` reprova: significa que o rodapé "Para X, ver Y" está ausente ou fraco na descrição da invasora.

Falhou? Consertar a `description` (fórmula de 5 partes da `struct-rules`), nunca o prompt. Ajustar o teste para passar é o modo de falha desta trilha.

## Fixtures

| Arquivo | Par em disputa |
| --- | --- |
| `T001-bug.md` | `bug-hunt` × `bug-diagnosis` |
| `T005-aula.md` | `aula-de-codigo` × `bug-diagnosis` × `graphify-search` |
