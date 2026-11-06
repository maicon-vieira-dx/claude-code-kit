> Referência da skill `plan-generation`. **Abrir na Fase 2**, ao decidir D1–D4, ou quando uma regra
> curta do `SKILL.md` for contestada. Contém: as tabelas completas de D1–D4, a aferição da D0, a caixa
> de regime e o break-even da D3 por extenso, e o porquê do par `EnterPlanMode`/`ExitPlanMode`.
> O `SKILL.md` carrega só a regra de cada decisão, para caber inteiro na recarga após a compactação.

## Por que o par `EnterPlanMode` / `ExitPlanMode`

> **Fase 0 abre com `EnterPlanMode`; a Fase 4 abre com `ExitPlanMode`. Não é opcional.**
> Esta skill diz substituir o plan mode nativo, e o que faz o nativo funcionar não é a prosa dele —
> é o **modo de permissão**: enquanto ele está ativo, a edição de código fica **bloqueada pelo
> produto**, não pela boa vontade do executor. Sem essas duas chamadas, "planejo antes de editar"
> volta a ser promessa, que é exatamente o defeito que esta skill existe para eliminar.
>
> O que a skill acrescenta ao nativo é o **arquivo**: o nativo não grava nada, então o raciocínio
> morre no `/clear`. Daí a divisão — o bloqueio vem do modo, a memória vem do `.md`.

---

## D1 — Modo de edição (a maior alavanca)

| Situação | Modo | Por quê |
|---|---|---|
| Mesma transformação **literal** em ≥3 arquivos | **BATCH** — um comando de shell | 2,3× mais barato, 2,2× mais rápido (Fato 2) |
| Transformação idêntica mas em arquivos de **estrutura diferente** | **BATCH com âncora por arquivo** ou per-file | Regex única não casa; medir antes |
| Edição exige **julgamento por arquivo** (nome, camada, se já existe) | **PER-FILE** | Não há atalho; o custo é o preço do julgamento |
| ≤2 arquivos | **PER-FILE** | O comando de batch custa mais para escrever do que economiza |

**Se BATCH, o plano DEVE conter o comando exato** — `perl -0pi -e 's/.../.../g'`, `sed -i`, ou um script.
Não "aplique em lote": o comando literal, testável.

> ⚠️ **Batch é destrutivo e sem preview.** O eval rodou em sandbox descartável; o repositório não é.
> Gates obrigatórios ao usar batch:
> 1. `git status` limpo antes (ou stash consciente) — **o usuário roda o git, não o agente**.
> 2. `grep -c` do padrão-alvo **antes**, com número esperado.
> 3. Rodar o comando.
> 4. `grep -c` **depois** — bate com o esperado? Padrão antigo zerado?
> 5. Um `git diff` de um arquivo para inspeção ocular antes de seguir.
>
> Sem os gates 2 e 4, batch vira mudança silenciosa de escopo. **Nunca rodar `perl -0pi`/`sed -i` sobre
> um glob mais amplo que a lista de alvos do plano.**

## D0 — Orçamento (o número que a D3 vai testar)

Não é chute nem meta: é contagem derivada do inventário da Fase 1, gravada **antes** de escolher o
executor. Sem ela a D3 decide no vácuo — foi assim que um plano saiu com `Orçamento ~55 calls` e
`D3 = solo` em linhas adjacentes, sendo `55 > 20` o próprio gatilho da D3.

São **dois números, não um** — misturá-los inutiliza o gate da D3:

```
D0_exec  ≈ (2×A_lógica + 1×A_simples + 1×G_camadas) × 1,15    ← trabalho RESTANTE; é o que a D3 testa
D0_total ≈ D0_exec + calls_já_gastas                          ← é o que o guard da skill compara
```

| Termo | O que conta |
|---|---|
| `A_lógica` | artefato novo/alterado **com lógica** — vale **2×**: `AGENTS.md` exige RED e GREEN em rodadas separadas |
| `A_simples` | barrel, DTO, enum, interface, `.module.ts` — isentos de spec, 1 rodada |
| `G_camadas` | um gate por camada atravessada (`ngc`, spec da camada, lint) |
| `× 1,15` | retrabalho de hook de lint reaplicando import, gate que volta vermelho |
| `calls_já_gastas` | chamadas da Fase 1 já queimadas nesta janela — entram só no `D0_total` |

**A D3 testa `D0_exec`.** Usar o total ali faria a descoberta sozinha estourar o limiar de 20 em quase
todo plano, e um gate que dispara sempre não decide nada.

> **Aferição (o caso que originou esta decisão):** `A_lógica=5, A_simples=4, G_camadas=5` →
> `D0_exec ≈ 22` (já cruza o limiar de 20 da D3 ⇒ break-even obrigatório) e `D0_total ≈ 52` contra
> **82+ reais**. A fórmula acerta o **gate** e ainda subestima o **total** — trate o `D0_total` como
> piso, não como previsão, até a instrumentação `previsto/real` acumular casos.

Se **D1 = BATCH**, `A_lógica`/`A_simples` colapsam em 1 chamada por lote — é por isso que a D1 vem antes.

> **O multiplicador 2× do TDD é deduzido do `AGENTS.md`, não medido** — nenhum dos 39 trials teve ciclo de
> teste. Grave `D0 previsto` no plano e o **real** ao fechar (Fase 5): é o par que calibra esta fórmula.
> Fórmula que erra com número declarado é corrigível; ausência de número não é.

## D2 — Profundidade de exploração

Quanto o executor explora antes de agir. Cada provedor expõe isso de um jeito — um seletor de esforço, um
orçamento de raciocínio, ou nada. O nome não importa; o comportamento do Fato 4 importa: nível mais alto
**não** raciocina melhor, ele fragmenta o mesmo trabalho em mais chamadas.

| Tarefa | Nível | Base |
|---|---|---|
| Mecânica + verificação determinística (lint, `ngc`, grep de âncora, suíte) | **baixo** | Fidelidade 3/3 no nível baixo; −44% custo, −58% tempo vs. médio |
| Descoberta com ambiguidade real, ou decisão de camada/padrão | **médio/alto** | Fato 5: a base não cobre este caso |
| Nunca medido aqui | máximo | +122% sobre o nível baixo sem ganho observável **nesta classe** |

**PROIBIDO trocar o nível no meio da execução** — ele é renderizado no prompt, então mudá-lo invalida
os breakpoints de cache e repaga o prefixo. Decida aqui, mantenha até o fim. Para variar um turno só, use
steering na última mensagem ("pense com cuidado"), que não toca o prefixo.

**Nem todo modelo aceita o seletor** — os mais baratos costumam recusá-lo. Executor barato não é
barateável por nível: se o provedor rejeita o parâmetro, a alavanca da D2 não existe para aquele executor
e o ajuste tem de sair da D1.

## D3 — Quem executa

**Não existe default universal.** O Fato 3 só vale dentro do regime em que foi medido:

> **Caixa de regime — classifique antes de decidir, e grave `dentro`/`fora` no plano.**
> Solo é default forte **se todas** valerem: ≤12 arquivos · ≤2 camadas · sem ciclo TDD · **`D0_exec` < 20**.
> Esse foi o regime dos 39 trials — e é exatamente onde o break-even abaixo *prevê* que solo ganha.
>
> **Fora do regime → sem default.** Rode o teste e **grave a conta no plano**. Invocar o Fato 3 fora da
> caixa é o modo de falha nomeado desta skill, não um atalho.

**→ Devolver ao usuário** quando a execução exige decisão de produto/UX, credencial, comando interativo,
migração de dados — ou é uma linha óbvia que ele faz mais rápido que a orquestração.

**→ Delegar a subagente** só quando passar no **teste de break-even**:

> Delegar tem custo fixo (medido: constituir o contexto do subagente + o pai vivo esperando). Isso só se
> paga se o subagente **mantiver fora da janela do pai** um volume que o pai releria em cada call
> seguinte, a preço de `cache_read`:
>
> **`tokens_poupados × calls_restantes > 400 000`**
>
> O 400 000 é `sobretaxa de delegação ÷ tarifa de cache_read` na medição. **Recalcule-o ao trocar de
> provedor ou de modelo** — é o único número desta skill que depende de tarifa.
>
> Na prática: **>20k tokens fora da janela E `D0_exec` > 20 calls.** O segundo termo é a D0, não palpite
> — e é o `D0_exec` (trabalho restante), nunca o `D0_total`.

**Topologia de delegação: orquestrador magro, um subagente por camada, em série.** Numa feature
multi-camada a camada é o lote natural — cada uma fecha num gate determinístico (spec verde, `ngc` limpo).
O pai fica só com o plano e o resultado dos gates; saída de vitest, avisos do hook de lint e greps de
verificação ficam na janela do subagente — e é justamente esse volume que o break-even está contando.

**Conversão tardia — o orçamento estourou no meio da execução.** Ao bater 1.0× do `D0_total` (é o aviso do
guard da skill) com **>30% do plano ainda por fazer**: feche a camada corrente, escreva o estado no plano (o que está verde, o que falta) e entregue
**as camadas restantes**. "Delegar agora sai mais caro" é verdade sobre o contexto já afundado e **falso
sobre o trabalho restante**: o handoff é o arquivo do plano, não a janela do pai. Se o plano não estiver
literal o bastante para isso, o defeito está na Fase 3 — corrija o plano, não a topologia.

### Medido no S010 (construção com TDD, PR real, 2026-10-08)

Duas tarefas reais do monorepo, refeitas a partir do commit pai do PR, com os specs do PR como aceite.
Sessões no nível intermediário do provedor; o executor barato, no nível baixo. T1: 2 libs, 10 arquivos.
T2: 3 libs, 12 arquivos. Custo = razão sobre o ponto médio do solo da mesma tarefa (depende da tarifa
vigente — recalculável); aceite funcional; minutos = janela de trabalho do agente (mediana).

| Topologia | T1 — custo · aceite · min | T2 — custo · aceite · min |
| --- | --- | --- |
| Solo, nível intermediário | 0,9–1,1× · 1 de 3 · 6,1 | 0,8–1,2× · 3 de 3 · 12,2 |
| Pai que não edita + 1 subagente de nível baixo por lib, em série | 1,1–1,8× · 3 de 3 · 12,3 | 0,5–0,6׹ · 3 de 3 · 12,1 |
| Plano no intermediário → sessão nova no baixo | 1,6–2,3× · 3 de 3 · 8,8 | 1,3–1,5× · 3 de 3 · 12,1 |
| Plano no intermediário → troca para o baixo na mesma sessão | 1,5–2,1× · 3 de 3 · 8,5 | 1,6× · 1 de 1 · 13,7 |
| Nível alto planeja, intermediário executa, alto revisa | 3,7× · 1 de 1 · 10,5 | 3,5–3,6× · 3 de 3 · 18,0 |

¹ Custo do CLI, que inclui o subagente: o grader não tarifava o modelo de nível baixo em que ele rodou na T2.

O que isso autoriza — mecanismo, não ranking (k=3 em parte dos braços, k=1 no resto):

- **≤2 libs → solo.** Mais barato e mais rápido na T1. As 2 reprovações vieram de o componente ler
  `store.error()`, membro que a store falsa do spec não expõe, onde os outros leram `hasError()`. Ao
  consumir store ou facade num componente que já tem spec, leia o dublê do spec e use só o que ele expõe.
- **≥3 libs, cada uma com gate próprio → pai que não edita + subagente de nível baixo por lib, em série**, quando
  custo pesa mais que prazo. Na T2 custou ~0,5–0,6× o solo, com o mesmo tempo de agente (mediana). A
  fronteira "3 libs" é o que separa as duas tarefas medidas, não um limiar medido.
- **Não pagou em nenhuma das duas:** plano → sessão nova; troca de modelo na mesma sessão; nível alto
  como planejador e revisor (a revisão não mudou nenhum diff em 4 trials). Só a fase de plano já custou
  quase o solo inteiro: ~1,0× o solo na T1, ~0,95× na T2.
- **Tempo:** em série, delegar não foi mais rápido que solo (T2 empatou; T1 levou ~2×). Subagentes em
  paralelo na mesma working tree são proibidos; em worktrees isoladas, nunca foram medidos.
- **Modelo do executor:** por token, o nível baixo custava 0,5× o intermediário em toda rubrica (tarifa
  de 2026-10 — recalculável). Seguindo um plano, o executor intermediário custou 1,5× o de nível baixo
  (T2, k=1, planos diferentes): gasta menos tokens, mas não a metade.
- **O 400 000 do break-even não foi recalibrado:** nenhum braço isola a sobretaxa de delegar. Plano solo
  com `D0_exec ≥ 20` passa no gate da D3 (`scripts/guard.py`) se a D3 trouxer uma linha `break-even:` citando esta tabela.

Fonte: relatório do S010 (não incluído neste repositório; os números são citações do autor, sem dados brutos para conferir aqui).

## D4 — Como buscar

| Pergunta | Ferramenta |
|---|---|
| Existe? onde vive? quem usa? — **dentro de `libs/`** | `graphify-search` (obrigatório pela rule `libs-graphify`; grep/find cru em `libs/` é PROIBIDO) |
| Alvo já localizado, ou ≤5 arquivos | `Read` inline |
| Trecho que vira **código literal, assinatura ou nome de campo** no plano | `Read` inline — **sempre**. Resumo perde o literal e você releria de qualquer forma |
| Varredura ampla fora de `libs/` cuja resposta é uma **conclusão**, com trabalho substancial depois | subagente `Explore` — **se passar no break-even da D3** |

> **Não medido:** busca delegada vs. inline nunca foi comparada. O critério acima é *derivado* das tarifas
> de cache, não observado — hipótese operacional (backlog de evals, S006).

Na única medição relacionada, a fase de descoberta custou **26% da fatura** (não 80%, como o cenário
previa). ⇒ *Buscar é barato; o que custa é o fan-out depois.* Não otimize a busca antes de otimizar a D1.

> **"Buscar" não é "escrever o plano".** Onde a D5 abaixo exige conteúdo literal, a fase de plano deixa
> de ser leitura e vira emissão de código — no piloto de construção ela respondeu por ~84% da fatura do
> braço e ~82% do output. Isso não contradiz o 26% acima: é outra fase, com outro produto. O que se
> desloca é **quem** paga o output, não quanto trabalho existe.

## D6 — Higiene de contexto

A D6 completa — dados, vocabulário e a conta termo a termo — está em
`references/contexto.md`. O `SKILL.md` carrega a regra; `scripts/checkpoint.py` roda a conta.
