> Referência da skill `plan-generation`. **Abrir quando** um número da decisão for
> contestado, quando o orçamento estourar, ou quando você for justificar a escolha para
> outra pessoa. Contém: as medições que sustentam D0–D5 e o método de medida.

# Modelo de custo — o que foi medido, não o que se supõe

Base: 39 trials, 13 braços, k=3, fidelidade 39/39 (`~/.claude/evals/FATOS.md`, linhas F1–F5).
Custos recalculados com a tarifa vigente — o `PRICES` do grader cobrava a geração anterior de modelos.

> **As razões viajam; os valores absolutos não.** Os números abaixo são **relativos** (2,3×, −44%) de
> propósito. A proporção entre constituir contexto, reler cache e gerar saída é estrutural e se mantém
> entre provedores; o preço por token não. Ao trocar de provedor ou de nível, refaça **só** o que depende
> de tarifa — o limiar de break-even da D3 — e mantenha os fatos qualitativos.

**Fato 1 — a maior rubrica da fatura muda com o regime.** Não existe um componente que sempre domina;
existe um por **forma de tarefa**. Só o input frio é constante: nunca passa de 0,1% em nenhum regime.

| Regime | Forma da tarefa | Maior rubrica | Regra que sai daí |
|---|---|---|---|
| Fan-out mecânico | poucos arquivos, 1 camada, edição literal | `cache_write` 33–53% (10 de 13 braços) | **minimize contextos constituídos** — cada sessão e cada subagente paga o seu |
| Construção, 1 contexto | muitos arquivos, várias camadas, com specs | **output** ~49% | **minimize tokens gerados** — construir é emitir código, e código é output |
| Construção, plano → executor frio | idem, 2 contextos | **output** ~55% | idem — e o output se concentra na fase de plano, não na de execução |
| Construção, subagentes em paralelo | idem, N contextos | **`cache_read`** ~51% | **minimize releitura do pai** — quem reintegra relê a janela inteira a cada chamada |

⇒ *Classifique a linha antes de aplicar a regra.* Usar a regra do fan-out em trabalho de construção
inverte a otimização: economiza-se contexto e paga-se em output. As três linhas de construção vêm de
**um trial por braço** — a ordem entre elas não é ranking; o que se afirma aqui é a rubrica dominante
de cada uma, que é propriedade da própria sessão, não comparação entre braços.

> **Revisar com o S010.** Na tarifa vigente (`2026-09-26-modelo-ttl`, cache write de 1 h a 2×), nenhum
> dos 26 runs do S010 teve `output` como maior rubrica: foi `cache_write` ou `cache_read`, inclusive nos
> braços solo e plano → frio. As três linhas de construção acima vêm do piloto S001, na tarifa anterior.
> Trate a rubrica dominante delas como hipótese até recustear o S001.

**Fato 2 — o custo é bimodal, e o seletor é a estratégia de edição.** Mesma tarefa, mesmo modelo, mesmo
prompt: um loop de shell (~4 tool calls) custou **2,3× menos** que abrir arquivo por arquivo (~24 calls).
Em 15 trials controlados as duas faixas **não se sobrepõem**. ⇒ *É a maior alavanca isolada que existe —
maior que escolher modelo, maior que escolher topologia.*

**Fato 3 — delegar não pagou *nesta escala*.** Dentro de cada cenário, **todo braço solo bateu todo braço
que delega**. Sobretaxa medida: o equivalente a **~400–670k tokens lidos de cache** — é dessa conta que
sai o limiar da D3. A rota "plano → `/clear` → executor frio" custou **2,5×** o modelo fazendo quente. ⚠️ É o único Fato com fronteira de validade estreita — **só vale
dentro da caixa de regime da D3**; fora dela não há dado, nem a favor nem contra.

**Fato 4 — a profundidade de exploração é seletor de estratégia, não dial de raciocínio.** P(escolher o
loop de shell) por nível: baixo 2/3, médio 1/3, alto 0/3, máximo 0/3. Tool calls medianos 4 → 20 → 24 →
25. Custo do menor ao maior nível: 2,2×. ⇒ *Nível baixo não "pensa menos": ele consolida operações em
menos chamadas.*

**Fato 5 — a fidelidade saturou em 39/39**, inclusive no nível mais baixo com 3 tool calls. ⇒ *Nada
falhou, então nada foi protegido: esta base **não** autoriza concluir que verificar é inútil, que nível
baixo é seguro fora de tarefa mecânica, ou que modelo grande não vale. Ela só autoriza o que está acima.*

**Escopo honesto.** Os Fatos 2–5 foram medidos em **tarefa mecânica, 8–12 arquivos, uma camada, sem
ciclo TDD, verificação determinística**, com k=3. O próprio registro da rodada anotou: *"onde a
delegação inverte de sinal segue desconhecido"*. O Fato 4 é mecânica de faturamento
e generaliza; o **Fato 3 não** — por isso a D3 tem caixa de regime em vez de default universal.

O cenário de construção (`S001`: 21 arquivos, 4 camadas, com specs) **rodou como piloto k=1** em
2026-09-03 — é de onde vêm as três linhas de construção do Fato 1, a D5 e o contrato de retorno do
prompt de delegação, todos achados de **mecanismo dentro de uma sessão**. O que aquele piloto
**não** autoriza é qualquer ordem entre braços: com um trial não se separa efeito de ruído, e o
precedente está documentado — o veredito *"6/6 na ordem pré-registrada"* do S002 sobreviveu duas
rodadas antes de se revelar artefato do medidor. A passagem 1 do `S010` (replay de PR real) fechou em
2026-10-08: a D3 ganhou uma linha medida para construção com TDD (tabela em `references/decisoes.md`,
D3). Ela **não** recalibra o limiar de break-even, que continua o do regime mecânico: nenhum braço do
S010 isola a sobretaxa de delegar.
Registro completo: `~/.claude/evals/FATOS.md` (linhas F6–F13); protocolo em
o `EXPERIMENT.md` do cenário S010 (não incluído neste repositório).

---
