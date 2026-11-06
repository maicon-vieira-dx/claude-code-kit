# BACKLOG de melhorias do sistema de agentes

> Entrada do loop de auto-melhoria (CHARTER P9). Cada item nasce de uma rodada: de uma falha
> observada, de uma autoavaliação de agente, ou de um padrão de transcrição. Item sem rodada de
> origem é palpite — marque como tal.

## Como usar

1. Toda melhoria proposta vira um item aqui com: **origem** (run-id), **alvo** (skill/rule/CLAUDE.md/
   estratégia), **hipótese** e **como medir** (qual cenário/métrica valida).
2. Ao aplicar, mova para `CHANGELOG.md` com o antes/depois medido no `leaderboard.md`.
3. Priorize: curto prazo (corrige falha recorrente), médio (refina rubrica/skill), longo (estrutural).

## Curto prazo

- [x] ~~**Rodar k=3 dos braços de mix de modelo do S002 (C/D/E/F)**~~ — feito 2026-07-30 junto com S003 e
  S004 (39 trials). Veredito em `runs/2026-07-30-k3-results.md`. **Achado que muda tudo:** o `PRICES` do
  grader cobrava tarifa de Claude 3 e inverteu o ranking; corrigido, Opus-solo sai do 6º para o 3º lugar.

- [x] **P0 — Braço SOLO no S001 (o cenário certo, nunca rodado).** — **superado 2026-09-25 pelo S010** O item de maior retorno do backlog.

  - **Origem:** falha de produção em 2026-08-07 (sessão real, não trial): feature de ~20 arquivos em 5
    camadas com TDD; plano orçou ~55 calls, `D3 = solo`, real passou de 82 com 3/8 passos faltando.
  - **Diagnóstico:** os 39 trials são todos S002/S003/S004 — 8–12 arquivos, **uma** camada, **zero** ciclo
    TDD. O S001 (16–20 arquivos, 4 camadas, com specs, ancorado em exec-log real de ~533k tokens /
    398 tool_uses) é o **único no regime que dói e tem 0 rodadas**. Pior: o `manifest.yaml` dele fixa a
    topologia multi-agente (TL+EM+3 Haiku+Judge) como dado do cenário, **sem braço solo** — então nem
    rodando hoje ele produz o dado que a D3 precisa.
  - **Alvo:** a caixa de regime da D3 da `plan-generation` (escrita em 2026-08-07 com limiares
    *deduzidos*: ≤12 arquivos · ≤2 camadas · sem TDD · `D0_exec` < 20). Nenhum limiar é medido.
  - **Braços:** (i) solo-quente; (ii) orquestrador magro, 1 subagente por camada em série; (iii) o
    multi-agente que o manifest já descreve.
  - **Hipótese:** o sinal inverte entre 12 e 20 arquivos / entre 2 e 5 camadas — (i) vence em S002-escala
    e **perde** em S001-escala. Se não inverter, a caixa de regime está errada e solo volta a ser default.
  - **Como medir:** `runs/2026-07-30-k3-results.md:127` ("onde a delegação inverte de sinal segue
    desconhecido") é a pergunta literal; este item é a resposta.

- [ ] **P0 — TDD como fator (ameaça de validade em TODOS os 39 trials).**
  - **Origem:** mesma sessão de 2026-08-07. O `AGENTS.md` exige RED e GREEN em rodadas separadas para
    todo código com lógica; **nenhum cenário do harness tem ciclo de teste**. Todo trial mediu "edição
    literal sem spec" — um regime em que o repositório não opera para código novo.
  - **Consequência:** o `2×` por artefato com lógica na fórmula D0 da `plan-generation` está **deduzido
    do AGENTS.md, não medido**. É o multiplicador dominante do orçamento e não tem número.
  - **Alvo:** a fórmula `D0_exec = (2×A_lógica + A_simples + G_camadas) × 1,15`.
  - **Como medir:** mais barato que cenário novo — acrescentar exigência de spec ao rubric de um seed
    existente e rodar o mesmo braço com e sem. A variável é calls por artefato, não custo total.
  - **Hipótese:** o multiplicador real fica entre 2× e 3× (RED + GREEN + rodada de vitest + reaplicação
    do hook de lint), o que explicaria 55 previsto → 82+ real melhor que o 2× puro.

- [ ] **P1 — Instrumentar `previsto vs. real` em toda rodada (não é experimento, é medidor).**
  - **Origem:** 2026-08-07. A D0 agora manda gravar `D0: previsto N / real M` no fechamento, mas nada
    agrega isso entre rodadas.
  - **Alvo:** calibrar a fórmula D0 de graça, a partir de rodadas que já vão acontecer de qualquer forma.
  - **Como medir:** capturar `orçado` (regex do plano, o mesmo do `budget-guard`) e `real` (contagem de
    tool calls do trial) no `graders/`; série temporal em `leaderboard.md`. Deve vir **antes** de qualquer
    cenário novo — sem ele, cada cenário mede um ponto e nenhum calibra a previsão.

- [ ] **P0 — Decidir o fix do `PRICES` em `graders/token-usage.mjs`.**
  - **Origem:** rodada k=3 de 2026-07-30. `PRICES` traz Claude 3 Opus ($15/$75) e Haiku 3.5 ($0,80/$4);
    os modelos reais são `claude-opus-5` ($5/$25), `claude-sonnet-5` ($3/$15), `claude-haiku-4-5` ($1/$5).
  - **Alvo:** o medidor. Enquanto não corrigir, **toda cifra do harness está errada** exceto as de Sonnet.
  - **Decisão pendente (do dono):** corrigir e **reescrever** os results de 17-jul/22-jul/23-jul, ou
    corrigir e **anotar** que os antigos usam o medidor velho. Não fiz porque muda o significado de três
    documentos já registrados.
  - **Junto:** trocar o comentário `PRICES é placeholder` por um teste que falha se o preço estiver stale.

- [x] **P0 — S005: instrução de estratégia de edição como FATOR.** — **superado 2026-09-25 pelo S010** A maior alavanca medida, e nenhum
  cenário a controla.
  - **Origem:** rodada k=3. O custo é bimodal — batch (~4 calls, $0,088) vs per-file (~24 calls, $0,205),
    faixas **sem sobreposição** em 15 trials de Sonnet warm-solo com prompt/seed/modelo idênticos.
  - **Alvo:** a decisão D1 da `plan-generation` (hoje escrita a partir de observação, não de experimento).
  - **Braços:** (i) prompt livre; (ii) prompt exigindo loop de shell único; (iii) prompt exigindo Read+Edit
    por arquivo. Fidelidade como **variável** — batch pode quebrar em arquivo de estrutura divergente.
  - **Hipótese:** (ii) < (i) < (iii) em $, com (ii) empatando em fidelidade — e a instrução explícita
    eliminando a variância bimodal, que é o ganho real.

- [ ] **P1 — Cenário com ERRO PLANTADO.** Sem ele o harness não mede o que verificação vale.
  - **Origem:** fidelidade saturou em 39/39 na k=3, inclusive em `--effort low` com 3 tool calls.
    Consequência: nenhuma conclusão sobre valor de verificador, de modelo grande, ou risco de effort baixo
    é sustentável — nada falhou, então nada foi protegido.
  - **Alvo:** justificar (ou aposentar) o verificador Sonnet dos braços A/B/F/T, hoje custo morto medido.
  - **Como medir:** seed com armadilha que o executor barato erra (âncora ambígua, decoy que casa o regex,
    enum com membro parecido). Fidelidade vira variável de verdade.
  - **Alvo adicional (2026-08-03): a skill `bug-hunt` reescrita.** Ela agora assume três coisas que
    NENHUM eval mediu: (a) fan-out por lote acha mais bug que varredura solo; (b) a onda de lentes
    transversais acha o que os lotes perdem; (c) o advogado do diabo derruba alucinação sem matar achado
    real. Um cenário de detecção — diff com N bugs plantados de classes distintas (corrida, escopo/tenant,
    off-by-one, contrato quebrado) — mede recall e precisão por braço: solo × lotes × lotes+lentes, com e
    sem advogado. É a única forma de saber se a profundidade nova se paga ou é só teatro.

- [ ] **P1 — S006: busca delegada vs busca inline.** É a única das quatro decisões da `plan-generation`
  que está escrita **sem medição**.
  - **Origem:** pergunta do usuário em 2026-07-31 ("vale usar subagente para busca?"). A skill hoje
    responde com um break-even *derivado* das tarifas de cache (`tokens × calls > 400000`), não observado.
  - **Braços:** (i) descoberta inline no pai; (ii) subagente `Explore` devolvendo conclusão; (iii) idem com
    retorno verbatim `arquivo:linha`. Variar **trabalho restante após a busca** (curto vs longo) — é a
    variável que o break-even diz ser decisiva, e que o S003 não tinha (lá a tarefa acabava logo depois).
  - **Hipótese:** com trabalho curto depois, (i) vence (replica o S003, onde descoberta foi 26% da fatura);
    com trabalho longo, (ii)/(iii) viram — e o ponto de virada é o número que a skill precisa.

- [x] **P2 — Elevar k nos braços bimodais.** — **superado 2026-09-25 pelo S010** k=3 não serve para a variável real.
  - **Origem:** a ponte de validade S004[M] ≡ S003[A] não fechou (medianas 2× apart, mas U=2, p≈0,2).
  - **Diagnóstico:** a variável não é custo, é **P(batch)** — proporção binomial. Com n=3 o IC vai de ~10%
    a ~90%. Para separar 1/3 de 2/3 com confiança é preciso k≈20 por braço.
  - **Alternativa mais barata:** fixar a estratégia por prompt (S005 acima) e **medir custo condicional à
    estratégia** — aí a variância bimodal some e k=3 volta a ter poder.

- [x] **Rodar o braço G do S003 (troca de modelo no meio da sessão — tese do Akita).** — **superado 2026-09-25 pelo S010** Último braço sem
  dado: exige sessão interativa (`/model`), e o `run-trial.sh` só cobre A, K e T (todos já medidos a k=3).
  - **Origem:** S003 (EXPERIMENT.md H1, pré-registrado 2026-07-20).
  - **Alvo:** decisão D3 da `plan-generation` — se existe caso em que trocar de modelo no meio ganha de
    simplesmente seguir solo (hoje o default forte, vencedor em 39/39).
  - **Hipótese:** **G ≥ A** — o Haiku reingere o contexto de descoberta como input frio, e a economia de
    rate não cobre. Contexto novo: **A já bateu K por 2,5×**, então G precisa bater A, não K.
  - **Como medir:** roteiro manual `armG-manual.txt`, duas janelas de tempo; comparar com A ($0,088) e
    K ($0,216) já medidos na k=3 de 30-jul.

- [x] ~~**Rodar o sweep L/M/H/X do S004 (effort)**~~ — **feito 2026-07-30 (k=3)**. H1 ✅ custo monótono
  `L<M<H<X`; **H2 ❌ não há joelho** — `fid(L)=1,00` estável (pass^3), inclusive em trials de 3 tool calls;
  H3 ~ fidelidade igual mas custo só 1,08× (previa >1,5×); **H5 ✅** tool calls 4→20→24→25.
  - **Mecanismo achado (não previsto):** effort não é dial de custo, é **seletor de estratégia** —
    P(loop de shell) cai 2/3 → 1/3 → 0/3 → 0/3 de `low` a `xhigh`. O custo é bimodal, não contínuo.
  - **Ponte de validade `M ≡ S003[A]` NÃO fechou** (U=2, p≈0,2) porque ela mede P(batch), uma proporção
    binomial sem poder a k=3. Ver item P2 acima.
  - **Aplicado:** decisão **D2** da `plan-generation` (refatorada 2026-07-31). **Não** mexi no
    `settings.json` global — um cenário só, e o mais favorável possível ao `low`.

- [x] ~~**Aplicar em `plan-generation` os 3 fatos de effort**~~ — **feito 2026-07-27**, ver `CHANGELOG.md`.
  Correção factual sem medição (fora do leaderboard, por desenho). A parte **hipotética** — se baixar
  effort estreita a janela da rota (b) — continua aberta e é a H4 do S004 acima.

- [ ] **Estender os 3 fatos de effort ao resto do harness.** `grep -rl effort ~/.claude/skills/` retornava
  **zero** antes de 2026-07-27: a omissão nunca foi só da `plan-generation`.
  - **Origem:** mesma pesquisa (2026-07-27), descoberta durante a edição.
  - **Alvo:** candidatos por natureza de tarefa — `bug-hunt` e `interface-design` (deliberativas, hoje
    sub-esforçadas no `medium` global); `graphify-search` e skills de geração de código
    (determinísticas, hoje super-esforçadas); `playwright-validation` (heterogênea —
    diagnóstico e validação querem effort oposto **na mesma skill**).
  - **Bloqueio conhecido:** não existe effort por skill nem por subagente no Claude Code (7 issues
    abertas no repo oficial) — qualquer recomendação por skill é **protocolo humano** (`/effort` antes de
    invocar), não config. Verificar se isso mudou antes de escrever.
  - **Como medir:** o S004 é o precedente metodológico (fator único, fidelidade como variável). Não
    replicar por skill — esperar o S004 dizer se o joelho de fidelidade é generalizável ou específico
    da tarefa.

## Médio prazo

- [ ] **Cenário de escolha de modelo na DESCOBERTA** (orquestrador Haiku vs Sonnet), separado da topologia.
  - **Origem:** alternativa rejeitada no desenho do braço T do S003 (2026-07-22) — rodar o orquestrador em
    Haiku quebraria a comparabilidade com A/G/K e dessaturaria a fidelidade, que ali é **controle**.
  - **Alvo:** triagem de modelo da `plan-generation` (quando a fase de descoberta pode ser barateada).
  - **Hipótese:** distinguir 8 alvos de 4 decoys é a parte difícil; um orquestrador Haiku **erra a
    classificação** (fidelidade cai abaixo da saturação) e a economia de rate não se sustenta.
  - **Como medir:** cenário próprio com fidelidade como **variável** (não controle), reusando o seed do S003.

- [ ] Calibrar o `judge` contra revisão humana em ≥3 rodadas; registrar divergência em `calibration.md`.
- [x] Promover S001 a regression eval — **superado 2026-09-25 pelo S010** quando o pass rate estabilizar ≈100% (CHARTER P5) e criar S002 mais difícil.

## Longo prazo

- [ ] Automatizar o disparo da suíte (cenário → graders → scorecard) num único comando/skill.
- [ ] Cobrir os demais bounded contexts (backend NestJS/CQRS, criação de Agregado/VO) com cenários próprios.
- [ ] Estudar se a estratégia multiagente justifica o ~15× de tokens (CHARTER P7) frente a single-agent Opus.
