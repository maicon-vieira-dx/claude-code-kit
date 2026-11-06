> Referência da skill `plan-generation`. **Abrir quando** o guard falar em contexto ou checkpoint, ou a
> conta da D6 for contestada. Contém: o que é contexto sujo, os dados que sustentam a D6, a conta do
> checkpoint termo a termo e o que ainda não foi medido.

# D6 — Higiene de contexto

## O custo que a D0 não vê

Toda chamada à API manda a janela inteira de novo. O que já está em cache sai pela tarifa de leitura de
cache, mas sai em **toda** chamada: o custo de uma tarefa é, em primeira ordem, contexto × chamadas. A D0
conta chamadas; a D6 cuida do outro fator.

Medido em 2026-10-14 nas 19 sessões reais deste projeto em que a skill foi invocada (cache lido depois da
invocação):

| Parcela do cache lido | % |
| --- | --- |
| Releitura do que entrou **durante a execução** | 59 |
| Releitura da **base** (system prompt, CLAUDE.md/AGENTS.md, memória, lista de skills) | 31 |
| Releitura do **sujo** anterior à invocação | 11 |

- Base: mediana **77k tokens**, já na primeira chamada. Nenhum `/clear` desce abaixo dela.
- Sujo na invocação: mediana 11k; 7 de 19 sessões acima de 30k; máximo 107k.
- Pico da janela: mediana 260k; 13 de 19 acima de 200k; uma sessão chegou a 674k em 296 chamadas.
- Só 1 das 19 compactou. Com janela de 1M, a compactação não segura o custo: a janela só cresce.
- Em 110 de 158 sessões reais, a releitura de cache foi a maior rubrica da fatura
  (`~/.claude/evals/evolution/sessoes-reais.md`).

## Vocabulário

| Termo | O que é | De onde vem |
| --- | --- | --- |
| contexto | tamanho do prompt de uma chamada: input + cache lido + cache escrito | `usage` da última chamada no transcript |
| base | contexto da primeira chamada da sessão | idem, primeira chamada |
| sujo | contexto na invocação − base: a conversa anterior à tarefa | guard, na primeira chamada depois da invocação |
| excedente | contexto atual − base: o que um `/clear` tiraria | guard, a cada chamada |
| restabelecer (R) | o que a sessão nova precisa reler: o plano e os arquivos-alvo em disco | tamanho em disco ÷ 2,35 bytes/token |
| base reescrita (B) | a parte da base que o cache perde no `/clear` | 1,0 × base até a calibração medir |
| razão (K) | escrever no cache ÷ ler do cache, para o modelo da sessão | tarifas do `~/.claude/hooks/turn-cost.py`; TTL pelo que a sessão escreveu |
| chamadas restantes (C) | quanto falta | calls ÷ passos fechados nesta sessão × passos que faltam; sem passo fechado, o resto da `D0_exec` |

Para medir a qualquer momento: `python3 ~/.claude/skills/plan-generation/scripts/contexto.py --ultimo`
na raiz do projeto (mede o transcript mais recente, que é o da sessão viva).

## A conta do checkpoint

    checkpoint compensa  ⇔  (excedente − R) × C  >  K × (R + B)

À esquerda, o que se deixa de reler nas chamadas que faltam. À direita, o que se paga para reconstruir a
janela na sessão nova: escrever no cache o plano, os alvos e a parte da base que o cache perdeu.

O guard roda a conta em dois momentos: **ao gravar o plano** (checkpoint de entrada — uma sessão suja não
começa a desenvolver sem passar por aqui) e **a cada edição do plano** (o `## Estado` muda quando um
passo fecha). Deu verdade, ele avisa uma vez por passo, com a conta escrita.

**Exemplo** (nível intermediário, TTL 1 h, K = 20 na tarifa de 2026-10 — recalculável): base 77k, janela
260k, plano e alvos 20k, 30 chamadas restantes → (183k − 20k) × 30 = 4,9M > 20 × (20k + 77k) = 1,94M ⇒
compensa. Com 10 chamadas restantes, 1,63M < 1,94M ⇒ não compensa. Num modelo em que a leitura de cache é
relativamente mais barata (K = 40), o `/clear` precisa de mais chamadas pela frente para se pagar.

## Por que isto não contradiz "plano → sessão nova não pagou"

No S010, o braço P (o nível intermediário grava o plano, sessão nova executa) custou mais que o solo nas duas tarefas, e
a D3 registra isso. A D6 não reabre essa conclusão, porque mede outra situação:

- As sessões do S010 começam **limpas**: não havia excedente a remover, então o lado esquerdo da conta era
  zero e a sessão nova só somava custo.
- O plano do braço P era **literal** (1.100+ linhas): a fase de plano sozinha custou quase o solo inteiro.
  O checkpoint usa o plano de **decisão** que já existe, mais o `## Estado`.
- A D6 só recomenda o `/clear` quando a conta dá verdade — com janela suja e trabalho pela frente, que é a
  situação das sessões reais (pico mediano de 260k), não a do eval.

## Por que B começa em 1,0

Depois do `/clear`, o system prompt continua igual e tende a sair do cache. Mas o primeiro bloco da
conversa traz o `gitStatus` da sessão, que muda depois de qualquer edição, e o cache é reescrito dali em
diante. Quanto da base se perde nunca foi medido. Até a calibração juntar 3 retomadas, a conta assume o
pior caso (a base inteira) — o que faz o checkpoint ser recomendado **menos** vezes, nunca mais.

## O que fazer quando compensa

1. Feche o passo corrente (gate verde). Checkpoint no meio de um passo perde o que não está no arquivo.
2. Atualize o `## Estado` pelo `templates/checkpoint.md`.
3. Devolva ao usuário: "Checkpoint gravado. Rode /clear e depois /plan-generation retomar <slug>". O
   agente não executa `/clear`: quem limpa é o usuário.

Sem usuário disponível (sessão headless), a alternativa é a **conversão tardia** da D3: despachar os passos
restantes a um subagente por camada, que começa com janela própria.

Discordar da conta é permitido — por exemplo, o próximo passo depende de algo que só está na conversa e
não cabe no plano. Escreva o motivo no `## Estado`; o aviso não se repete no mesmo passo.

## O que não foi medido

- **Qualidade depois do `/clear`.** Evidência indireta: no S010, o braço P (sessão nova executando um plano)
  passou no aceite em 6 de 6 trials. Mas aquele plano era literal, com mais de 1.100 linhas; um plano de
  decisão na retomada carrega menos. O braço R do S010 mede isso.
- **B real.** Ver acima.
- **2,35 bytes/token** foi medido em texto em português com markdown (o corpo da skill). Código costuma
  render menos bytes por token, então o R de alvos de código pode estar subestimado.

## Freio de acúmulo (o que não deixar entrar)

Nas mesmas 19 sessões, o que fez a janela crescer depois da invocação:

| Origem | % do crescimento |
| --- | --- |
| Saída de Bash | 49 — dentro dela, `cat`/`sed -n` lendo arquivo ≈ 42% e `nx`/vitest ≈ 19% |
| `Read` | 37 — 7 leituras acima de 20 mil caracteres somaram 18% de todo o volume de `Read` |
| `ExitPlanMode` | 4 — o plano volta inteiro no resultado, ~7 mil caracteres por chamada |
| Resto (Grep, Edit, Write, perguntas) | 10 |

Ler arquivo, por `Read` ou por shell, é ~58% de tudo que entra. Daí a regra da Fase 4: `Grep -n` antes
de abrir, `Read` com `offset`/`limit`, saída de teste/lint/`ngc` para arquivo e de volta por `tail`/`grep`,
nunca `cat` do arquivo inteiro, e `ExitPlanMode` com resumo de até 1.500 caracteres.

O guard (`scripts/acumulo.py`) avisa uma vez por ferramenta quando uma saída passa de ~6k tokens, com a
projeção de releitura até o fim do plano. É nudge e não bloqueia: a saída já entrou, e o aviso existe
para a próxima.

## Calibração (o que transforma as estimativas em medida)

O Stop do guard grava, a cada turno de uma sessão com plano vinculado, uma linha por sessão em
`~/.claude/evals/evolution/calibracao-plan-generation.tsv` (`scripts/calibracao.py`): D0 prevista,
chamadas reais, base, sujo na invocação, pico, releitura e a primeira escrita de cache da sessão.

- **D0:** `python3 ~/.claude/skills/plan-generation/scripts/calibracao.py --plano <caminho>` imprime a
  linha `D0: previsto N / real M …` somando todas as sessões do plano. A Fase 5 a copia para o plano.
  Antes disso, só 1 de 9 planos do repositório tinha o par (previsto 23, real ≈ 72).
- **B (base reescrita):** numa retomada, a primeira chamada escreve no cache o que ele perdeu. Com 3
  retomadas registradas, `fracao_base_reescrita()` devolve a mediana de `escrita_primeira ÷ base`, e o
  `checkpoint.py` passa a usá-la no lugar do 1,0. A medida superestima um pouco (a primeira chamada também
  escreve o pedido e o corpo da skill), o que mantém a conta do lado conservador.
- `--resumo` mostra a mediana de real ÷ previsto e a fração medida, quando houver.
