---
name: bug-hunt
description: Caça-bugs multi-agente no diff da branch antes de abrir o PR — dimensiona os agentes pelo tamanho do diff, submete cada achado a um advogado do diabo que tenta refutá-lo, e entrega uma lista ordenada por criticidade (P0–P3) com veredito CONFIRMADO/PLAUSÍVEL, em UMA rodada. Invoque ao terminar uma implementação e antes de abrir/atualizar PR, ou quando o usuário pedir "revisa antes do PR", "passa o olho", "tem bug aqui?", "posso subir?". NÃO usar para conformidade de estilo (lint + hooks + rules já cobrem). Para sintoma que JÁ está acontecendo (erro em produção, regressão, crash), ver `bug-diagnosis`.
allowed-tools: Bash, Read, Grep, Glob, Task
argument-hint: "[tamanho do diff: pequeno|médio|grande]"
metadata:
  version: 1.4.0
---

# Quando usar

Última passada antes do PR. Objetivo: **achar todo bug que chega no usuário**, com cobertura provada e
custo proporcional ao diff. Precisar rodar de novo para ter confiança é falha desta skill.

| Situação | Ferramenta |
|---|---|
| Passada pré-PR, caçar bug no diff | esta skill |
| Estilo, `any`, `OnPush`, boundaries Nx | lint + hooks + `.claude/rules/` — NÃO reportar aqui |
| Conformidade AGENTS.md (bounded context, erros, package-by-feature) | subagente `agents-md-reviewer` |

# Princípio: profundidade proporcional ao diff

Cobertura provada continua sendo a meta — comprada com o **mínimo de agentes que a entrega**, não com o
máximo que cabe. Fan-out não é profundidade: quatro agentes relendo o mesmo diff produzem quatro cópias
do mesmo contexto, não quatro perspectivas.

Medido numa tarefa **média** (41 arquivos / 1572 linhas) varrida por 10 agentes no nível mais caro do
catálogo: ~1.06M tokens, 79% da janela de uso, ~26k por arquivo. Os 4 agentes de "lentes" releram o que
os 5 lotes já tinham lido e devolveram zero achado. **O teto de agentes sai da tabela abaixo** — nunca
do apetite por profundidade, nunca de o usuário ter dito "pode usar multi-agentes".

# Dimensionamento — contar ANTES de montar lotes

`git diff <base>...HEAD --numstat` dá arquivos e linhas. O par (arquivos, linhas) escolhe a linha;
empate ou dúvida resolve para a linha de **menor** custo.

| Diff comportamental | Lotes | Transversal | Advogado | Teto |
|---|---|---|---|---|
| ≤ 8 arq **e** ≤ 300 linhas | 0 — varrer inline, sem `Task` | — | só se houver P0/P1 | 0–1 |
| ≤ 20 arq **e** ≤ 800 linhas | 2 | — | 1 | 3 |
| ≤ 40 arq **e** ≤ 1600 linhas | 3 | 1 (só se ≥ 3 bounded contexts) | 1 | 5 |
| acima disso | 4 | 1 | 1 | 6 |

**Orçamento por agente: máx. 20 tool calls.** Vai no prompt; o agente reporta quanto usou. Bater no teto
é lote mal dimensionado — PARAR e reportar o que faltou, nunca estourar em silêncio.

## Nível do agente de varredura — critério, não marca

Varrer diff é trabalho de **leitura em volume**: muita entrada, julgamento raso por achado, e o filtro
pesado vem depois (advogado do diabo e Fase 4). O gargalo da cobertura é **quanto de cada arquivo o
agente lê**, não a profundidade de raciocínio dele — por isso pagar pelo topo do catálogo compra pouco
e multiplica pelo número de agentes.

Escolher o **nível intermediário** do provedor em uso: o que segue instrução literalmente e lê código
bem. Regra de decisão, nesta ordem:

1. **Um único nível para a rodada inteira** — lotes, transversal e advogado. Misturar níveis torna a
   cobertura incomparável entre lotes, e o advogado do diabo mais fraco que o lote vira carimbo.
2. **Nunca o nível mais caro por padrão.** Só com autorização explícita do usuário, registrada no
   checkpoint junto do motivo.
3. **Nunca o nível mais barato/rápido**, que perde bug de interação entre arquivos — exatamente o que
   justifica ler o arquivo inteiro em vez do hunk.
4. **Subir de nível é reativo, não preventivo:** só depois de uma rodada que reprovou no Critério de
   parada nº 5 (zero achados em diff grande) ou em que o advogado do diabo REFUTOU a maioria dos
   achados. Os dois são sintoma de leitura rasa; aí o gasto extra tem evidência.

Reprova a rodada: níveis diferentes entre agentes da mesma rodada, ou nível mais caro sem a autorização
do item 2 no transcript.

# Modo de falha

**Fan-out por reflexo** — o erro que originou a tabela: ler "pode usar multi-agentes" como licença para
gastar o máximo e disparar uma onda que reproduz o trabalho da anterior. Sintoma: dois agentes lendo o mesmo
arquivo; um relatório sem nenhum achado que já não estivesse em outro.

**Teatro de profundidade** — repassar os relatórios quase intactos, de secretário em vez de
sintetizador. Sintomas: achados duplicados com redações diferentes; `arquivo:linha` não conferido pelo
orquestrador; advogado do diabo virando carimbo.

**Cobertura parcial silenciosa** — lote que voltou vago é lote não varrido; declarar 100% ali é mentir
no veredito que autoriza o PR.

# Racionalizações barradas

| Desculpa | Por que está errada | Ação obrigatória |
| --- | --- | --- |
| "o diff é grande, mas é tudo renomeação/mecânico — um lote basta" | A tabela dimensiona por arquivo e linha, não por dificuldade percebida. Renomeação em massa é justamente onde muda assinatura sem ninguém olhar | contar com `--numstat`, aplicar a faixa, e classificar como scaffolding só o que a Fase 0 lista |
| "lint, `ngc` e testes passaram — o resto é detalhe" | Ferramenta pega tipo e estilo, nunca lógica errada que compila. Se lint bastasse, esta skill não existiria | rodar a passada mesmo com CI verde; achado de lógica é o escopo, achado de estilo não se reporta aqui |
| "o achado é evidente, dispenso o advogado do diabo" | O advogado é o que separa CONFIRMADO de ruído. Achado "evidente" que não sobrevive a refutação é o que queima a confiança no veredito | submeter todo achado, inclusive P0 — o advogado é 1 agente, está no teto da tabela |
| "esse PR é crítico, vou rodar no nível mais caro para garantir" | O que acha bug aqui é ler o arquivo inteiro e refutar o achado, não o nível do agente. O custo multiplica pelo nº de agentes e paga por raciocínio que a varredura não usa | manter o nível intermediário; se o PR é crítico, gastar em **cobertura** — lote próprio para o arquivo de risco (Override por risco), não em nível |
| "são 3 linhas num arquivo de auth, não justifica lote próprio" | É exatamente o caso do Override por risco: dimensionar por tamanho erra mais caro aqui | lote próprio, arquivo lido inteiro, achado nasce P0/P1 |

# Checkpoint — preencher ANTES de disparar qualquer agente

Disparar as ondas é caro de refazer. Preencher e mostrar ao usuário:

```
Base: <ref> · Arquivos comportamentais: <N> · Linhas: <L> · Bounded contexts: <C>
Faixa da tabela: <faixa> ⇒ lotes <n> · transversal <0|1> · advogado 1 · TETO <t> agentes
Lotes: L1 <ctx/feature> [n arq] · L2 ... (todo arquivo em exatamente um lote)
Orçamento: <t> agentes × 20 tool calls · nível de varredura: <nível> (o mesmo em todos)
Fora do escopo comportamental: <scaffolding listado>
```

Arquivo comportamental fora de todo lote é erro de montagem — corrigir antes de disparar.
**Plano acima do teto da tabela ⇒ PARAR e pedir autorização**, com o número de agentes explícito.

# Protocolo

**Fase 0 — Recorte, contagem e lotes.** `Bash: git diff <base>...HEAD --numstat`.
Sem branch/PR alvo, usar working tree (`git diff` + `git diff --staged`). Classificar:
- **Comportamental** — `.ts`/`.html` com lógica, template, store, service, componente, migration. É o escopo.
- **Scaffolding** — `tsconfig*`, `*.eslintrc*`, `project.json`, `vite.config.*`, `README`, `test-setup`,
  barrel só com `export *`, lockfile. Varrer em bloco; abrir só se quebra build/alias.
- **Teste** (`*.spec.ts`) — pertence ao lote do código que ele cobre, no eixo de alinhamento.

Contar, aplicar a tabela de dimensionamento, **então** montar lotes por bounded context/feature (coesão
vence tamanho). **Todo arquivo comportamental pertence a exatamente um lote.**

**Nunca excluir um trecho por proveniência de merge.** Se a PR entrega o commit, o bug dele chega ao
usuário por esta PR — proveniência *atribui* achado, nunca reduz escopo. Pedido do usuário para
"limpar/separar o diff" é pedido de **apresentação**, não de escopo.

**Fase 1 — Onda de lotes.** Um `Task` por lote, todos numa onda só (o teto da tabela já cabe em 4):

```
Task(subagent_type: "general-purpose", model: "<nível de varredura — ver critério acima>",
  prompt: "Lote <id>: <lista de caminhos>. Base do diff: <ref>.
   ORÇAMENTO: máx. 20 tool calls. Priorize ler os arquivos do lote INTEIROS (não só o hunk) — é o que
   pega bug de interação. Abra arquivo de apoio só quando um contrato do lote depender dele; se o
   orçamento acabar, PARE e reporte o que faltou em vez de estourar.
   Aplique os Vetores de falha e o Teste do cenário da skill bug-hunt (~/.claude/skills/bug-hunt/SKILL.md).
   Devolva: (a) 'Cobertura: <n>/<n> lidos integralmente · tool calls: <x>/20' — se não leu algum, diga qual;
   (b) achados com arquivo:linha, o trecho literal citado e o cenário Dado/Hoje/Esperado.
   Sem resumo, sem narração, sem elogio ao código.")
```

**Fase 2 — Transversal (condicional).** Só quando o diff cruza **3+ bounded contexts**. UM `Task` que
recebe os achados dos lotes e o mapa arquivo→lote e **não relê o diff inteiro**: procura só a interação
ENTRE lotes que cada dono, por construção, não via — contrato que um lote mudou e outro consome, estado
compartilhado, ordem de efeito.

**Fase 3 — Advogado do diabo.** Só se houver candidato a P0/P1/P2. Consolidar os achados brutos e
submeter a UM agente cuja tarefa é **refutar**, não confirmar:

```
Task(subagent_type: "general-purpose", model: "<mesmo nível dos lotes>",
  prompt: "<achados brutos consolidados> · Diff base: <ref>.
   Sua tarefa é DERRUBAR cada achado, não confirmá-lo. Para cada um, procure ativamente: o guard que já
   trata o caso, o tipo que impede a entrada, o caller que garante a pré-condição, o default do banco.
   Você PODE rodar teste alvo (nx test <proj> -t '<nome>') e ngc/build escopado no projeto tocado —
   nunca a suíte inteira. Redirecione saída para arquivo e leia só o trecho relevante.
   Devolva por achado: REFUTADO (com a evidência que o derruba, arquivo:linha) | CONFIRMADO (com a
   evidência que prova o cenário) | PLAUSÍVEL (não deu para provar nem derrubar — diga o que faltou).
   Se a refutação expuser um bug adjacente real, reporte-o; máx. 3.")
```

**Fase 4 — Síntese pelo orquestrador.** Não é repasse. Deduplicar achados com redações diferentes,
**conferir cada `arquivo:linha` no trecho** (não de memória), atribuir severidade, ordenar e emitir.
Descartar em silêncio o que veio REFUTADO.

# Vetores de falha

Perguntar do hunk, não do arquivo. Descartar em silêncio o que não aplica. Os **grupos** são as antigas
"lentes": mesma cobertura, aplicada por cada dono de lote, sem o custo de reler o diff 4x.

| Grupo | Vetor | Pergunta |
|---|---|---|
| **Concorrência / ciclo de vida** | Corrida | Duas chamadas em voo — a lenta sobrescreve a rápida? `mergeMap` onde devia cancelar? |
| | Stream morta | `rxMethod`/pipe sem `catchError` — erro mata o stream e a tela trava carregando? |
| | Rollback | Update otimista reverte no erro, ou a tela mente sobre o que foi salvo? |
| | Ciclo de vida | `subscribe` sem `takeUntilDestroyed`, timer/listener vivo após navegar? |
| **Dados / persistência** | Data | Timezone/UTC vs local, virada de dia, fim de mês (o projeto usa meio-dia em `parseCalendarDate`). |
| | Número/dinheiro | Arredondamento, float somado, divisão por zero. |
| | Backend/TypeORM | Escrita composta sem transação, migração `NOT NULL` sobre dados, `Promise.all` parcial. |
| **Escopo / contrato** | Escopo/permissão | Query ou rota sem filtro de tenant/usuário — dado de um vaza para outro? |
| | Regressão de contrato | Assinatura/DTO alterado sem atualizar todo consumidor, endpoint mudado sem o front, campo obrigatório sem produtor. |
| **Estado / UI / spec** | Estado vazio/nulo | Lista volta vazia, `find()` não acha, ou renderiza antes do 1º load? |
| | Paginação/filtro | Off-by-one, página além do total, filtro novo sem resetar para a página 1? |
| | Formulário | `disabled` fora do `.value`, `patchValue` parcial com resíduo, `reset` que não limpa validators. |
| | Template | `@for` com `track` instável perdendo estado ao reordenar; `@if` sobre signal não chamado. |
| | Spec | O `*.spec.ts` tocado ainda cobre o comportamento que mudou, ou fixa o bug? |
| **Segurança** | Autenticação/autorização | Rota, guard ou handler novo sem checagem de ator — ou checagem que confia em valor vindo do cliente? |
| | Segredo | Chave, token ou credencial em código, log, mensagem de erro ou arquivo versionado? |
| | Chamada externa | Entrada não validada indo para SQL, shell, path de arquivo ou URL; resposta de terceiro consumida sem validar formato? |
| | Transferência de valor | Pagamento, estorno, reembolso: valor ou destinatário derivado de entrada do cliente sem reconferir no servidor? |
| | **Validação removida** | O diff **apagou** um `if`, um guard, um decorator de `class-validator` ou um filtro `WHERE`? Remoção de checagem é o vetor mais fácil de passar batido, porque some do diff como linha vermelha e não chama atenção como código novo |

## Override por risco (fura a tabela de dimensionamento)

A profundidade é função do tamanho do diff — **exceto** quando o diff toca um dos cinco vetores de
segurança acima. Nesse caso:

- O arquivo tocado entra num lote **próprio**, lido por inteiro, mesmo que o diff nele seja de 3 linhas.
- Achado de segurança nasce **P0 ou P1**, nunca P2/P3, e passa pelo advogado do diabo como qualquer outro.
- O teto de agentes pode subir em **+1** sem autorização; acima disso, perguntar.

Diff pequeno em arquivo de auth é o caso onde o dimensionamento por tamanho erra mais caro.

> Vetores adaptados do método de revisão diferencial da Trail of Bits (`differential-review`,
> CC-BY-SA-4.0). Reescritos para o vocabulário desta skill — nenhum texto copiado.

# Teste do cenário (filtro obrigatório)

Um achado só existe se couber nesta forma, **com valores concretos**:

> **Dado** \<entrada/estado instanciável> · **o código** \<faz X> · **deveria** \<fazer Y>.

Não conseguiu instanciar a entrada? **Descartar.** É PROIBIDO reportar suspeita genérica ("pode causar
problema", "talvez race condition", "considere validar").

**Severidade (o quão grave) e confiança (o quão certo) são eixos independentes.**

| Nível | Critério |
|---|---|
| 🔴 **P0 Bloqueador** | perda ou vazamento de dado, escopo/permissão furado, corrupção irreversível. Nunca sobe. |
| 🔴 **P1 Quebra** | usuário final vê erro, dado errado ou tela travada. Corrigir antes do PR. |
| 🟠 **P2 Risco** | cenário plausível, mas depende de condição não comprovada no diff. |
| 🟡 **P3 CI/Manutenção** | quebra teste, build, lint ou deploy — NÃO atinge usuário. |

| Confiança | Significado |
|---|---|
| **CONFIRMADO** | o advogado do diabo tentou derrubar e falhou; existe evidência do cenário. |
| **PLAUSÍVEL** | não foi possível provar nem refutar; o relatório diz o que faltou. |

**Regra dura:** achado em `*.spec.ts` nunca é P0/P1/P2 — é 🟡 P3 por definição (teste não chega ao
usuário). Ordenar por (severidade, confiança, blast radius), decrescente.

# Critério de parada — reprova se qualquer item falhar

1. **Cobertura 100%:** todo arquivo comportamental tem dono e voltou com "lido integralmente". Faltou um
   → reabrir **só para ele**, nunca uma onda inteira. Declarar 100% sem isso é PROIBIDO.
2. Todo achado tem `arquivo:linha` **conferido pelo orquestrador na Fase 4**, não herdado do subagente.
3. Todo P0/P1 passou pelo advogado do diabo e carrega CONFIRMADO ou PLAUSÍVEL.
4. Todo 🔴/🟠 sobrevive a "que usuário, em que tela, vê o quê de errado?". Não sobrevive → rebaixar.
5. **Zero achados num diff com > 5 arquivos comportamentais reprova a rodada** — é sinal de varredura
   rasa, não de código limpo. Reabrir o lote de maior densidade, não todos.
6. **Nº de agentes disparados ≤ teto da tabela**, ou existe autorização explícita do usuário no
   transcript. Estourar sem autorização reprova a rodada mesmo que os achados sejam bons. Idem para o
   nível: o mesmo em todos os agentes, e o nível mais caro só com autorização registrada.
7. Usuário pediu lista "diferente" da de um revisor automático de PR? Conferir os comentários já
   existentes na PR antes de emitir.

# Output

❌ "Talvez haja uma condição de corrida no `rxMethod`; vale revisar se todas essas validações são
   necessárias neste momento."

✅ `pedido.store.ts:88 — 🔴 P2 · CONFIRMADO`
   Dado: `patchState` mutando o ninho `filtros.status` direto.
   Hoje: a referência antiga vaza para o `computed` e a tela não re-renderiza.
   Esperado: `updateState(...)` de `@org/shared-utils`.
   Evidência: `AGENTS.md:498`; mesma regra em `.claude/rules/data-access.md:47`.

O ❌ é a saída default. Achado sem arquivo, linha e substituto nomeado **não entra na lista**.

Ordenado por severidade. Cada achado em exatamente 5 linhas:

```
🔴 P1 · CONFIRMADO — <resumo em uma linha> — caminho/arquivo.ts:123
Dado: <entrada/estado concreto>
Hoje: <o que acontece>
Esperado: <o que deveria acontecer>
Evidência: <o que provou o cenário, ou o que faltou se PLAUSÍVEL>
```

Fechar com duas linhas:
```
Cobertura: <N>/<N> arquivos lidos integralmente · <k> lotes · <t> agentes (teto <t>) · não lido: <lista ou "nada">
Veredito: PRONTO PARA PR | NÃO SUBIR — <n> P0/P1 confirmados | DECIDIR — <n> P1 plausíveis
```

`PRONTO PARA PR` exige zero P0 e zero P1 (confirmado ou plausível). P2/P3 não bloqueiam.

Nada de score, nota por dimensão, "pontos positivos", resumo geral ou lista do que foi verificado.
Usuário pediu formato explícito (tabela, agrupado por arquivo)? O formato dele vence — os critérios de
conteúdo (cenário instanciável, evidência, sem narração) valem igual.

# NUNCA

- Reportar estilo, preferência, nomenclatura ou padrão de arquitetura — mesmo estando certo. Escopo é bug.
- Reportar achado sem cenário instanciável, ou P0/P1 sem veredito do advogado do diabo.
- Repassar relatório de subagente sem deduplicar e sem reconferir `arquivo:linha` no trecho.
- Declarar cobertura que um lote não confirmou.
- **Disparar agente que relê material que outro agente já leu** — sobreposição é custo, não redundância útil.
- **Exceder o teto da tabela de dimensionamento sem autorização explícita do usuário.**
- Sugerir refatoração ampla como correção — a correção proposta é a mínima que fecha o cenário.
- Rodar a suíte inteira (risco real de OOM). Teste alvo e build escopado, sim — só no projeto tocado.
- Disparar mais de 4 agentes numa onda.
- **NUNCA** reportar excesso de engenharia, dívida estrutural ou oportunidade de simplificação
  nesta passada — não é o escopo. Roteie para `improve`.
- **NUNCA** propor remover a spec, o guard ou o teste que cobre o caminho tocado. É o piso, não
  excesso — mesmo quando o diff encolheria com a remoção.

## Aviso de Cobertura

Se o protocolo não cobre o cenário atual, prosseguir e notificar com uma linha:
> ℹ️ A skill `bug-hunt` não cobre este passo — prosseguindo com [breve descrição].
