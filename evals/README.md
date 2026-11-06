# `~/.claude/evals/` — avaliação de topologia de execução

Mede, sobre trabalho real de um repositório, **qual forma de trabalhar com o Claude entrega a tarefa
com os testes verdes gastando menos token**. O resultado alimenta a skill `plan-generation` (D3/D5).

Princípios: `CHARTER.md`. O que já está medido: `FATOS.md` (não re-medir o que está "estabelecido").

## O que vem neste kit

Só o **framework**. O cenário `S010` (replay de PRs reais de um repositório de trabalho), os runs, os
relatórios e os planos de evolução do harness ficaram de fora porque descrevem um projeto específico.
Referências a eles dentro das skills (`plan-generation`, `relatorio-evals`) são históricas.

## Mapa

```text
~/.claude/evals/
├── CHARTER.md          princípios (pré-registro, pass^k, fronteira de honestidade)
├── FATOS.md            livro-razão dos achados de S001–S005
├── scenarios/          (vazio no kit) um diretório por cenário: EXPERIMENT.md, COMO-RODAR.md, tarefas
├── graders/
│   ├── token-usage.mjs        custo real por modelo a partir dos .jsonl de sessão
│   ├── sessoes-reais.mjs      telemetria das sessões reais (observacional; PLANS_DIR opcional)
│   ├── aceite-funcional.mjs   aceite = specs reais da PR, com denominador fixo
│   ├── consolidar-s010.mjs    consolida os runs de um cenário de replay em relatório
│   └── verificar-relatorio.mjs portão do relatório (números só de run medido)
├── evolution/          BACKLOG e CHANGELOG do sistema de agentes
├── trigger/            fixtures de roteamento de skill (citadas no overlay pessoal)
└── sandbox/            diretórios efêmeros (materializados por git archive)
```

Nada deste harness escreve no repositório avaliado: as tarefas saem dele por `git archive`
(somente leitura).
