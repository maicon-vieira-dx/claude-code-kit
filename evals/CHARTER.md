# CHARTER — Princípios da Avaliação de Agentes

> Fundamentação direta nas práticas públicas da Anthropic ("Demystifying evals for AI agents" e
> "How we built our multi-agent research system") e na literatura de eval de sistemas agênticos.
> Cada princípio aqui é **vinculante** para o desenho de cenários, rubricas e graders.

## P0 — Por que isto existe

Validar agente não é "rodar e ver se passou". É medir, de forma **comparável entre rodadas**, se
mudanças em Skills/Rules/`CLAUDE.md`/estratégia de orquestração **melhoram ou pioram** a qualidade e o
custo. Sem baseline reproduzível, "ficou melhor" é opinião.

## P1 — Três camadas de avaliação (Anthropic)

Toda rodada é avaliada em três camadas, nunca só na última:

1. **Session / outcome** — o estado final está correto? (a feature builda, os testes passam, o código
   gerado satisfaz o brief). Avalie o **estado final**, não o caminho.
2. **Trace / response quality** — a trajetória foi boa? (delegação coerente, sem retrabalho, handoffs
   limpos, raciocínio arquitetural defensável).
3. **Tool / step correctness** — as ferramentas certas foram usadas? (skills certas invocadas,
   `graphify-search` antes de ler `libs/`, `lint --fix` após editar).

## P2 — Norma híbrida: recompensa verificável + rubrica

Combine sempre os dois tipos de grader (consenso da comunidade + Anthropic):

- **Code-based / determinístico** (rápido, barato, reproduzível): "o código resolve o problema?" —
  lint, `tsc`, testes, cobertura, varredura de violações de Rules, contagem de arquivos, verificação
  de tool-calls. → `graders/deterministic-checks.sh`.
- **Model-based / LLM-as-judge** (flexível, nuançado): "o código é legível, arquiteturalmente são,
  bem delegado?" — rubricas com **dimensões isoladas**. → `team/judge.md` + `rubrics/`.

Nunca confie só em um. O determinístico pega regressão objetiva; a rubrica pega o que os testes não veem.

## P3 — Regras de ouro do LLM-as-judge

- **Uma dimensão por juiz.** Não use um único juiz para notar tudo de uma vez — avalie cada dimensão
  da rubrica isoladamente para reduzir contaminação entre critérios.
- **Dê uma saída de emergência.** O juiz pode (deve) responder `Indeterminado` quando faltar evidência,
  em vez de alucinar uma nota.
- **Avalie o produto, não o caminho.** Não exija uma sequência rígida de passos — o agente pode achar
  um caminho válido alternativo. Cheque o estado/artefato final.
- **Calibre contra humano.** Notas do juiz devem ser periodicamente comparadas ao seu julgamento; a
  divergência vai para `evolution/calibration.md`. Rubrica sem calibração humana é teatro.
- **Escala 0.0–1.0 + pass/fail.** Cada dimensão recebe nota contínua e um veredito binário.

## P4 — Cenário bom (critérios de aceite de um benchmark)

- **Verificável:** "dois especialistas de domínio chegariam ao mesmo pass/fail de forma independente".
- **Solucionável:** existe `reference/` provando que dá para resolver seguindo as instruções.
- **Casos positivos e negativos:** o cenário planta tanto coisas que os agentes *devem* fazer quanto
  armadilhas que eles *não devem* cair (ex.: anti-padrões do "Nunca Fazer" embutidos no `seed/`).
- **Sem ambiguidade injusta:** o agente não pode falhar por adivinhar uma suposição não declarada.
- **Estado isolado por trial:** nenhuma rodada compartilha estado com outra (sandbox limpo sempre).

## P5 — Capability evals vs. Regression evals

- **Capability eval:** começa com pass rate baixo; é alvo de melhoria. Mede o teto do sistema.
- **Regression eval:** mantém ~100%; pega retrocesso. Um capability eval "saturado" (≈100%) **vira**
  regression eval e entra na suíte de proteção.
- Vigie **saturação**: quando um cenário chega a 100% estável, ele parou de informar — promova-o a
  regression e crie um cenário mais difícil.

## P6 — Não-determinismo: pass@k e pass^k

Modelos variam entre execuções. Rode **k trials** por cenário (k≥3 recomendado) e reporte:

- **pass@k** — probabilidade de ≥1 sucesso em k tentativas (bom para "existe solução").
- **pass^k** — probabilidade de **todos** os k trials passarem (mede confiabilidade/consistência).

Para um agente de produção, `pass^k` importa mais que `pass@k`.

## P7 — Métricas que explicam performance (Anthropic, BrowseComp)

Três fatores explicaram ~95% da variância de performance em sistemas multiagente:

- **Uso de tokens (~80% da variância)** — métrica de primeira classe, não detalhe de rodapé.
- **Número de tool-calls.**
- **Escolha de modelo.**

Referências de custo da Anthropic (ordem de grandeza): agente ≈ 4× os tokens de um chat;
**multiagente ≈ 15× os tokens de um chat**. Toda rodada multiagente **deve** reportar tokens/custo
reais (`graders/token-usage.mjs`) — o ganho de qualidade precisa justificar o multiplicador de custo.

## P8 — "Leia as transcrições"

Antes de confiar em qualquer nota agregada, leia transcrições reais. O grader pode estar punindo
solução válida (rigidez) ou passando solução ruim (buraco no rubrica). Amostre transcrições toda
rodada; padrões de falha emergentes viram novos cenários.

## P9 — Sistema vivo e auto-melhorante

Cada handoff é **entrada** do próximo ciclo de melhoria:

1. Falhas reais → novos cenários (`scenarios/`).
2. Padrões de falha → propostas em `evolution/BACKLOG.md` para Skills/Rules/`CLAUDE.md`.
3. Modelos sabem diagnosticar a própria falha — a autoavaliação dos agentes (`self-assessment`)
   alimenta sugestões de melhoria de prompt/Skill.
4. Toda mudança no sistema de agentes é registrada em `evolution/CHANGELOG.md` com **antes/depois**
   medidos no leaderboard. Mudança sem medição não é melhoria — é fé.

## P10 — Isolamento e segurança do monorepo

Código gerado pelos benchmarks **nunca** nasce em `libs/` reais nem entra no grafo do Nx
(`nx.json`/`tsconfig` paths). Nasce em `sandbox/<run-id>/`, é auditado, vira snapshot em
`runs/<run-id>/` e é descartado. Benchmark não pode poluir build, CI nem produção.

## P11 — Fronteira de honestidade

Nunca publicar economia por-repositório ("esta mudança poupou N tokens/linhas aqui"): a versão não
construída nunca foi escrita, então não existe baseline para subtrair. Só número de **braço medido
contra braço medido**, na mesma tarifa, com a data da tarifa registrada ao lado.

Cifra de run anterior a 2026-07-30 não se cita sem recalcular — a tabela de preços do grader cobrava
a tarifa de uma geração de modelos anterior e isso já inverteu um ranking.

Resultado superado não se apaga: recebe tarja e a data em que deixou de valer. Apagar esconde que o
número já foi citado; a tarja impede a próxima citação.
