> Referência da skill `plan-generation`. **Abrir quando** a D3 já estiver decidida e você
> for escrever o plano. Contém: a D5 completa — que formato cada executor exige, o critério
> falseável Edit÷Write e o modo de falha da decisão.

## D5 — Formato do plano (contrato de handoff)

A D3 decide **quem** executa; a D5 decide **o que o plano precisa carregar** para essa pessoa conseguir
executar. São decisões diferentes e a segunda é a que costuma faltar — plano suficiente para você mesmo
é insuficiente para quem começa do zero.

| D3 escolheu | Formato exigido | Por quê |
|---|---|---|
| **eu, mesma janela** | plano de decisão: alvos, gates, aceite, invariantes | o contexto do código já está na janela; repetir literal é output pago duas vezes |
| **subagente** ou **executor frio** | **conteúdo literal por artefato** — o código que vai no arquivo, não a descrição da ação | o executor não tem a janela; tudo que o plano não ditar, ele **infere** — e inferência divergente vira retrabalho de integração |
| **usuário** | passos em linguagem de operação + comando exato | ele não vai ler o seu raciocínio, vai colar o comando |

**Critério falseável — razão Edit÷Write.** `~/.claude/evals/graders/token-usage.mjs` emite
`tool_calls.by_owner.*.edit_write_ratio`.
Executor que transcreve um plano literal fecha em **~0**; executor que infere e se corrige sobe. No
piloto de construção: executor frio com plano literal **0,00**; orquestrador reintegrando o que 3
subagentes escreveram **8,00** (24 Edit para 3 Write); solo **0,23**. Razão acima de ~1 no dono que
**não** escreveu os arquivos originais é diagnóstico de plano frouxo, não de executor ruim.

**Modo de falha desta decisão:** gravar `D3 = subagente` e um plano no formato "arquivo/exato.ts —
`<ação>`". É o formato do template de decisão aplicado a quem não tem contexto, e o resultado é o
executor reinventando assinatura, caminho de import e nome de campo — cada divergência custa uma
rodada de integração no pai, a preço de releitura da janela inteira.

> **Regra de bolso:** se o plano não permite que o executor produza o arquivo **sem abrir mais nada além
> dos arquivos-alvo**, ele não está no formato da D5. Teste isso lendo o passo como se você fosse o
> executor frio, antes de despachar.

---
