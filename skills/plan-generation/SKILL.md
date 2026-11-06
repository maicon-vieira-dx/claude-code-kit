---
name: plan-generation
description: Meta-skill de planejamento E execução — substitui o plan mode nativo. Enquadra a tarefa, decide as SETE variáveis que governam o custo (modo de edição, orçamento de tool calls, profundidade, quem executa, formato do plano, como buscar, quando limpar a janela), grava o plano em .claude/plans/<slug>.md e então EXECUTA ela mesma, verificando ao final. Invoque antes de qualquer implementação não-trivial, quando o usuário pedir plano/planejar/"antes de codar", ou para decidir se vale delegar busca ou execução a subagente. Tarefas de um `tasks.md` em `.specs/` são do `tlc-spec-driven`, não desta skill.
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, Task, AskUserQuestion, Skill, EnterPlanMode, ExitPlanMode, TaskCreate, TaskUpdate
hooks:
  PreToolUse:
    - matcher: "Write|Edit|MultiEdit"
      hooks:
        - type: command
          command: 'test -f "$HOME/.claude/skills/plan-generation/scripts/guard.py" || exit 0; python3 "$HOME/.claude/skills/plan-generation/scripts/guard.py"'
          timeout: 10
  PostToolUse:
    - hooks:
        - type: command
          command: 'test -f "$HOME/.claude/skills/plan-generation/scripts/guard.py" || exit 0; python3 "$HOME/.claude/skills/plan-generation/scripts/guard.py"'
          timeout: 10
  Stop:
    - hooks:
        - type: command
          command: 'test -f "$HOME/.claude/skills/plan-generation/scripts/guard.py" || exit 0; python3 "$HOME/.claude/skills/plan-generation/scripts/guard.py"'
          timeout: 10
metadata:
  version: 1.13.0
---

# O que esta skill é

**O plan mode desta conta.** Não é "gerador de documento" — é o ciclo inteiro: enquadrar → mapear →
decidir → gravar o plano → **executar** → verificar. O plano é o artefato intermediário, não o produto —
e é também o mecanismo de transferência de contexto quando a execução muda de dono (D3).

Ela existe porque as decisões que governam custo e qualidade são tomadas **antes** da primeira edição e
ficam invisíveis depois. Planejar e executar na mesma janela é o default — mas **só dentro do regime em
que isso foi medido** (caixa de regime da D3).

# NUNCA / PROIBIDO

- **NUNCA** começar a mapear ou decidir sem `EnterPlanMode`, nem executar sem `ExitPlanMode`
  aprovado (na retomada, vale o `**Aprovado:**` do `## Estado`). Sem o par, o "planejo antes de editar" não tem mecanismo por trás — é a mesma prosa que
  falha. O bloqueio de edição é do modo de permissão, não seu; não tente reproduzi-lo com disciplina.
- **NUNCA** gravar `D3 = solo` com `D0_exec ≥ 20` sem a conta de break-even escrita no plano. Plano
  nessa condição é **plano REPROVADO: não inicie a Fase 4** — volte e corrija a D3 primeiro.
- **NUNCA** seguir executando depois de o guard dizer `CHECKPOINT COMPENSA`: atualize o `## Estado` e
  devolva ao usuário (`/clear` + `/plan-generation retomar <slug>`). Discordar da conta é permitido,
  com o motivo escrito no plano.
- **NUNCA** invocar o Fato 3 sem antes classificar o regime (`dentro`/`fora`) na D3. Fora da caixa o
  Fato 3 não é evidência de nada — o piloto de construção que rodou lá é k=1 e não estabelece ordem.
- **NUNCA** aplicar a regra do Fato 1 sem dizer **qual linha** da tabela de regime é a sua. "Minimize
  contextos" é a regra de uma linha só; nas outras ela otimiza a rubrica errada.
- **NUNCA** despachar subagente ou executor frio com plano no formato de decisão. Sem a D5 = literal, o
  executor infere o contrato — e cada inferência divergente volta como rodada de integração no pai.
- **NUNCA** aceitar "escrevi os arquivos X, Y e Z" como retorno de subagente. Caminho de arquivo é
  ponteiro, não resumo: aceitar isso obriga a reler tudo e apaga a economia que motivou delegar.
- **NUNCA** decidir D1 por omissão. Fan-out de ≥3 arquivos sem modo de edição declarado no plano é
  descumprimento — é a maior alavanca de custo medida.
- **NUNCA** gravar a D0 sem contar o `2×` dos artefatos com lógica. Ignorar o ciclo TDD subestima o
  orçamento em ~2× — foi o erro que produziu `~55` onde o real passou de 82.
- **NUNCA** rodar `perl -0pi`/`sed -i` sem os gates de contagem antes/depois, nem sobre glob mais amplo
  que a lista de alvos.
- **NUNCA** executar `git commit`/`push`/`add` sem pedido explícito do usuário nesta sessão.
- **PROIBIDO** N subagentes em paralelo sobre a mesma working tree. Um por lote, em série.
- **PROIBIDO** abrir sessão `claude` separada para o executor enquanto esta segue viva — paga cache frio
  duas vezes. O checkpoint da D6 não é isso: é a mesma tarefa trocando de janela, autorizada pela conta.
- **PROIBIDO** trocar o nível de exploração (D2) no meio da execução.
- **PROIBIDO** trocar de modelo no meio da sessão (planejar num, executar noutro na mesma janela) —
  reescreve o cache e, no S010, custou mais que o solo nas duas tarefas.
- **PROIBIDO** aceitar retorno de subagente sem verificar (`ngc`/`lint`/`git diff`).
- **PROIBIDO** mapear `libs/` com `grep`/`find`/`Read` exploratório sem `graphify-search` antes.
  Leitura de precisão do alvo **já localizado** continua liberada.
- **PROIBIDO** carregar os quatro docs por padrão, ou ler regras que já disparam por glob.
- **PROIBIDO** citar cifra de eval anterior a 2026-07-30 sem recalcular — o `PRICES` do grader cobrava a
  tarifa de uma geração de modelos anterior.
- **PROIBIDO** generalizar os Fatos 2–4 para fora do regime medido (tarefa mecânica, alvos pequenos,
  verificação determinística) sem dizer que está extrapolando.

# Protocolo

> **Fase 0 abre com `EnterPlanMode`; a Fase 4 abre com `ExitPlanMode`. Não é opcional.** O bloqueio de
> edição vem do modo de permissão; a memória vem do `.md`. Por quê: [`references/decisoes.md`](references/decisoes.md).

**Retomada** (`/plan-generation retomar <slug>`): pule as Fases 0–3 — leia o plano com `Read` e siga
`references/retomada.md`.

**Fase 0 — Enquadrar.** **Primeira ação: `EnterPlanMode`.** Só então reformule em 1–2 frases: o que
muda, para quem, critério de "pronto".
Ambíguo → `AskUserQuestion` (opções fechadas, nunca pergunta em prosa) ANTES de ler qualquer arquivo.
O guard informa o contexto na invocação (base e sujo): ele vai para a D6 do plano.

Já estar em plan mode (o usuário entrou por `Shift+Tab` ou prefixou `/plan`) dispensa a chamada —
verifique antes de chamar. Gravar o `.md` da Fase 3 **não** é edição de código e não esbarra no
bloqueio; escrever em `.claude/plans/` é permitido em plan mode.

**Fase 1 — Mapear.** Identifique bounded context e camada. Localize os alvos com caminho preciso,
roteando cada pergunta pela **D4**. Registre também o que **não** ler (legado intocado, testes não
afetados, ruído).

> **Checkpoint de ambiguidade — obrigatório, com os arquivos à vista.** O mapeamento revelou decisão que
> a Fase 0 não previu (padrão divergente, spec ausente, enum/contrato a definir, camada dúbia)?
> → `AskUserQuestion` AGORA. A Fase 0 pergunta sobre o enunciado; esta pergunta sobre o que o código
> revelou. Ambiguidade cara descoberta na execução é retrabalho a preço cheio.

**Fase 2 — Decidir.** Aplique **D1 → D0 → D2 → D3 → D5 → D4 → D6** e escreva as **sete** no plano com justificativa.
A D0 sai do inventário da Fase 1; a D3 é decidida **olhando para o número da D0**, nunca antes dele.
Levante os invariantes em risco (`any` proibido, isolamento por ID, `updateState` imutável, CPF via
`Validation`, cobertura de spec) e **confira os valores exatos de enums/DTOs na fonte** — inventar membro
de enum é erro silencioso que só o `ngc` acusa, tarde.

**Fase 3 — Gravar.** `.claude/plans/<slug>.md`, slug **descritivo do problema** (nunca o slug aleatório do
plan mode nativo). Use `templates/plano.md`. Seção vazia sai do arquivo.

**Fase 4 — Executar.** **Primeira ação: `ExitPlanMode`**, com um resumo de até 1.500 caracteres — o que muda, as sete
decisões em uma linha cada, e o caminho do `.md` para quem quiser o detalhe. Não cole o plano inteiro:
ele está no arquivo, e o `ExitPlanMode` é para decidir, não para reler.

A aprovação do usuário é o que **desbloqueia a edição** e escolhe como as edições seguintes são
aprovadas. Reprovou ou pediu mudança → você **continua** em plan mode: corrija o `.md` e chame
`ExitPlanMode` de novo. Nunca contorne uma reprovação editando assim mesmo — em plan mode a edição
nem passa, e insistir só queima chamadas.

Aprovado → grave `**Aprovado:** <data>` no `## Estado`. Se o guard disse `CHECKPOINT COMPENSA` ao
gravar o plano, pare aqui e devolva ao usuário: a execução começa na sessão limpa.

Depois disso: você mesmo executa, salvo D3 dizer o contrário. Siga os passos na ordem; rode o gate de
cada passo antes de seguir para o próximo. Um gate vermelho **para a execução** — não improvise em cima
de um passo que não fechou.

- Invoque as skills que a Fase 2 listou, na ordem listada (a skill de componentes do projeto antes de tocar componente,
  `*-creator` para artefato de domínio, `data-access-feature` para camada de dados).
- **TDD onde o projeto exige:** spec primeiro, RED demonstrado, só então produção. O plano deve dizer
  qual spec e qual asserção — não "escreva testes".
- Desviou do plano? Corrija o plano no mesmo passo. Plano stale é pior que plano ausente.
- **Leitura cirúrgica (D6):** `Grep -n` antes de abrir; `Read` com `offset`/`limit`; saída de teste,
  lint e `ngc` vai para arquivo e volta por `tail`/`grep`; nunca `cat` de arquivo inteiro. O que entra
  na janela é relido em toda chamada seguinte — o guard avisa a saída acima de ~6k tokens.

**Fase 5 — Verificar e fechar.** Rode os comandos da seção `## Verificação` do plano. Reporte o resultado
real — falhou é falhou, com o output. Ao fim: o que ficou fora do escopo e por quê, **e a linha que
`python3 "${CLAUDE_SKILL_DIR}/scripts/calibracao.py" --plano <caminho do plano>` imprime**
(`D0: previsto N / real M …`), copiada para a `## Verificação` — é o par que calibra a D0 e a D6.

# Referências — abra só no gatilho

| Arquivo | Abra quando |
| --- | --- |
| `references/decisoes.md` | Fase 2, ao decidir D1–D4, ou quando uma regra curta for contestada |
| `references/formato-do-plano-d5.md` | a D3 estiver decidida e for escrever o plano |
| `templates/plano.md` | for gravar `.claude/plans/<slug>.md` |
| `templates/prompt-de-delegacao.md` | **só** se D3 = subagente |
| `references/modelo-de-custo.md` | um número for contestado, o orçamento estourar, ou for justificar a escolha |
| `references/retomada.md` | sessão limpa ou compactada no meio, ou passo falhou pela 2ª vez |
| `references/contexto.md` | o guard falar em contexto ou checkpoint, ou a conta da D6 for contestada |
| `templates/checkpoint.md` | o guard disser `CHECKPOINT COMPENSA`, ou ao fechar um passo |
| `references/precedencia-specs.md` | o pedido citar `.specs/`, um `tasks.md` ou o `tlc-spec-driven` |

# As sete decisões

Toda invocação decide as sete e grava cada uma no plano com a justificativa. Ordem: **D1 → D0 → D2 →
D3 → D5 → D4 → D6**: a D1 muda a contagem da D0 (batch ≈ 6× menos calls), a D0 é o número que a D3 testa, e
a D3 decide o formato da D5. Tabelas completas, aferição e exemplos de cada decisão:
[`references/decisoes.md`](references/decisoes.md) — **abra na Fase 2**, na hora de decidir.

## D1 — Modo de edição (a maior alavanca)

Mesma transformação **literal** em ≥3 arquivos → **BATCH**: um comando de shell, 2,3× mais barato
(Fato 2), com o comando exato no plano e `grep -c` do padrão antes e depois. Estrutura diferente entre
os alvos → batch com âncora por arquivo, ou per-file. Julgamento por arquivo, ou ≤2 arquivos →
**PER-FILE**.

## D0 — Orçamento (o número que a D3 vai testar)

```
D0_exec  ≈ (2×A_lógica + 1×A_simples + 1×G_camadas) × 1,15    ← trabalho RESTANTE; é o que a D3 testa
D0_total ≈ D0_exec + calls_já_gastas                          ← é o que o guard da skill compara
```

`A_lógica` vale 2× (RED e GREEN em rodadas separadas); com D1 = BATCH, cada lote vale 1. O `D0_total`
é piso, não previsão. Grave `D0 previsto` no plano e o real ao fechar.

## D2 — Profundidade de exploração

Mecânica com verificação determinística → **baixo**. Descoberta com ambiguidade real, ou decisão de
camada → **médio/alto**. Nível mais alto não raciocina melhor: fragmenta o mesmo trabalho em mais
chamadas (Fato 4). Decida aqui e **não troque no meio** — o nível está no prefixo do cache.

## D3 — Quem executa

**Não existe default universal.**

> **Caixa de regime — classifique antes de decidir, e grave `dentro`/`fora` no plano.**
> Solo é default forte **se todas** valerem: ≤12 arquivos · ≤2 camadas · sem ciclo TDD · **`D0_exec` < 20**.
> **Fora do regime → sem default.** Rode o break-even e **grave a conta no plano**.

**→ Devolver ao usuário:** decisão de produto/UX, credencial, comando interativo, migração de dados, ou
uma linha óbvia que ele faz mais rápido que a orquestração.

**→ Delegar a subagente** só se **`tokens_poupados × calls_restantes > 400 000`** — na prática, >20k
tokens fora da janela do pai **e** `D0_exec` > 20. O 400 000 depende de tarifa: recalcule ao trocar de
modelo ou de provedor.

**Topologia:** orquestrador magro, **um subagente por camada, em série**; cada camada fecha no seu gate
(spec verde, `ngc` limpo) antes de despachar a próxima.

**Construção com TDD (S010):** ≤2 libs → solo, lendo os dublês dos specs antes de consumir store; ≥3
libs com gate próprio → pai que não edita + subagente de nível baixo por lib, em série (~0,5–0,6× o
custo do solo, mesmo tempo). Plano → sessão nova, troca de modelo e revisor de nível alto não pagaram. Tabela:
`references/decisoes.md`, D3.

**Conversão tardia:** o guard avisou 1.0× do `D0_total` com >30% do plano por fazer → feche a
camada corrente, grave o estado no plano e entregue as camadas restantes. O handoff é o arquivo do
plano, não a janela do pai.

## D4 — Como buscar

Dentro de `libs/` → `graphify-search` (grep/find cru ali é proibido). Alvo localizado, ≤5 arquivos, ou
trecho que vira literal no plano → `Read` inline. Varredura ampla fora de `libs/` cuja resposta é uma
conclusão → `Explore`, se passar no break-even da D3. Buscar é barato; o que custa é o fan-out depois.

## D5 — Formato do plano (contrato de handoff)

**Eu mesmo** → plano de decisão (alvos, gates, aceite). **Subagente ou executor frio** → conteúdo
**literal** por artefato. **Usuário** → passos de operação com o comando exato.

## D6 — Higiene de contexto (quando limpar a janela)

Toda chamada relê a janela inteira: o custo é **contexto × chamadas**, e nas sessões reais 70% do cache
lido depois da invocação foi releitura do que estava acima da base. O guard mede base, sujo e excedente
e, ao gravar o plano e a cada passo fechado, roda
`(excedente − restabelecer) × calls_restantes > razão × (restabelecer + base reescrita)`. Deu verdade →
checkpoint (`templates/checkpoint.md`), `/clear`, `retomar`. Termos e dados: `references/contexto.md`.

# Modo de falha

O erro plausível **não** é pular a Fase 2 — é **aplicar o Fato 3 como se fosse universal**: ler o negrito
("todo braço solo bateu todo braço que delega"), não classificar o regime, cravar `D3 = solo` por reflexo,
e descobrir no call 82 que delegar já ficou caro porque o contexto afundou na sua janela. O erro irmão é
gravar a D0 e nunca confrontá-la com o gatilho da D3 — os dois números saem no mesmo plano, em linhas
adjacentes, e nada os compara a não ser você. Vale igual para D1=PER-FILE e D2=medium por piloto
automático: decisão sem confronto com a tabela é decisão não tomada.

# Racionalizações barradas

| Desculpa | Por que está errada | Ação obrigatória |
| --- | --- | --- |
| "a tarefa é pequena, gravo o plano depois se precisar" | O arquivo em `.claude/plans/` é o único estado que atravessa `/clear` e compactação. "Depois" é depois de o contexto ter ido embora | gravar o plano antes do primeiro `Edit`, mesmo curto — D0–D4, alvos, gates |
| "D0 é estimativa grosseira, não vale gastar call calculando" | A D0 existe para ser confrontada com o gatilho da D3. Sem o número não há gatilho, e a D3 vira preferência | escrever a D0 mesmo grosseira, e comparar explicitamente com a D3 na mesma passada |
| "escrever o código inteiro no plano é duplicar trabalho — o executor resolve os imports" | O código no plano não é duplicação: é o **único** contexto que o executor vai ter. O que ele "resolve" sozinho é o que ele **inventa**, e o pai paga a divergência na integração — medido em 24 Edit para 3 Write | se D3 ≠ eu, o plano sai com bloco literal por artefato (D5) ou não sai |
| "esse gate falhou duas vezes, na terceira vai" | A terceira tentativa idêntica nunca passa — o que falta é informação, não insistência | seguir o protocolo de três tentativas: registrar em `## Estado` e mudar de abordagem, ou parar e reportar |
| "copio as tarefas do `tasks.md` aqui, fica tudo num lugar" | Duas listas divergem no primeiro `- [x]` marcado de um lado só | referenciar o `tasks.md`; o plano guarda decisões, gates e estado |

## Aviso de Cobertura

Se o protocolo não cobre o cenário atual, prosseguir e notificar com uma linha:
> ℹ️ A skill `plan-generation` não cobre este passo — prosseguindo com [breve descrição].
