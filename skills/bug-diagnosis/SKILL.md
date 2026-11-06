---
name: bug-diagnosis
description: Encontra a causa raiz de um bug que JÁ está acontecendo — erro em produção, regressão, crash, comportamento intermitente ou falha inexplicada. Levanta hipóteses concorrentes, investiga em paralelo com agentes read-only e devolve um diagnóstico ranqueado por evidência. Invoque quando o usuário disser "está dando erro", "parou de funcionar", "quebrou depois do deploy", "por que isso acontece?", "não consigo reproduzir", ou colar um stack trace. Para revisar um diff pronto antes do PR, ver bug-hunt; para validar visualmente uma correção, ver playwright-validation; para aprender como um mecanismo funciona, sem sintoma a investigar, ver aula-de-codigo.
allowed-tools: Read, Grep, Glob, Bash, Task
disallowed-tools: Edit, Write, NotebookEdit
argument-hint: "[nº de hipóteses: 3|4|5]"
metadata:
  version: 1.3.1
---

# Quando usar

Existe um **sintoma observado** e a causa é desconhecida.

**Fronteira com `bug-hunt` — a confusão mais provável entre as duas:**

| | `bug-diagnosis` (esta) | `bug-hunt` |
| --- | --- | --- |
| Ponto de partida | Sintoma que já ocorreu | Diff que ainda não subiu |
| Pergunta | "Por que isso acontece?" | "Isso aqui tem bug?" |
| Escopo | O caminho de código que produz o sintoma, mexido ou não | Só as linhas que a branch mudou |
| Saída | Causa raiz ranqueada + como confirmar | Achados P0–P3 + veredito de PR |

Sintoma que aparece **enquanto** se revisa um diff: continua sendo `bug-hunt`. Erro que o usuário viu rodando: aqui.

# Passo 1 — Pacote do bug (antes de qualquer agente)

Sem isso, a investigação vira busca livre e cara. Preencher:

- **Sintoma exato** — mensagem, stack trace, screenshot, ou o que o usuário descreveu, literal.
- **Onde** — app, rota, endpoint, ambiente (local / homologação / produção).
- **Quando começou** — sempre foi assim, ou apareceu depois de algo? `git log --oneline -15 -- <caminho>` é a pergunta mais barata que existe e resolve boa parte dos casos sozinha.
- **Reprodução** — passos, ou "não reproduz" declarado.
- **O que já foi tentado** — para não repetir.

Falta o sintoma exato ou o "onde"? **Pergunte com `AskUserQuestion`** (opções fechadas) antes de gastar qualquer tool call.

# Passo 2 — Hipóteses concorrentes

Escreva **3 a 5 hipóteses mutuamente distintas** antes de investigar qualquer uma. Uma hipótese só é hipótese se disser *onde* e *o quê*.

O ponto de escrever várias: cada agente busca **evidência que derruba**, não evidência que confirma. Hipótese que ninguém tentou derrubar não é diagnóstico, é palpite com endereço.

Fontes típicas neste repositório, como gatilho de hipótese:

| Camada | Suspeita recorrente |
| --- | --- |
| Store / rxMethod | Operador de concorrência errado (`switchMap` em escrita), estado atualizado antes do retorno |
| Contrato front↔back | DTO divergente entre `libs/shared/domain` e o que a API devolve |
| Firestore / Postgres | Conversão de `Timestamp`, campo nulo que o mapeamento não previu |
| Auth / guard | Token expirado, rota protegida sem redirect |
| PWA de campo | Estado offline, fila não drenada, cache do service worker servindo dado velho |

# Passo 3 — Investigar em paralelo

Dimensione pelo número de hipóteses, **nunca acima de 4 agentes**:

| Hipóteses | Agentes | Teto de tool calls por agente |
| --- | --- | --- |
| 1–2 | 0 (investigue direto) | — |
| 3–4 | 2 | 15 |
| 5 | 3 | 15 |

Cada agente: **read-only** (sem Edit/Write), uma hipótese só, e o pacote do bug no prompt. Exige a devolução no formato:

```
Hipótese: <a que recebeu>
Veredito: SUSTENTADA | DERRUBADA | INCONCLUSIVA
Evidência: <arquivo:linha + o trecho que prova>
O que derrubaria: <o que você procurou e não achou>
```

**Nunca** dois agentes lendo o mesmo arquivo — sobreposição é custo, não redundância.

**Nível dos agentes:** o **intermediário** do provedor em uso, o mesmo em todos. Testar hipótese é ler
código à procura de evidência que derruba — trabalho de leitura, não de raciocínio longo; o nível mais
caro multiplica pelo nº de agentes sem comprar cobertura. Nível diferente entre agentes torna os
vereditos incomparáveis: uma hipótese DERRUBADA por um agente mais fraco não é a mesma coisa que a
derrubada por um mais forte, e o ranking do Passo 4 depende dessa comparação.

# Passo 4 — Diagnóstico

Ranqueie por **força de evidência**, não por plausibilidade. Uma hipótese SUSTENTADA com `arquivo:linha` vence três INCONCLUSIVAS bem argumentadas.

**Antes de emitir `Correção mínima:`, enumere os chamadores.** Se a causa está numa função ou
método compartilhado, rode `graphify explain "<Símbolo>"` (para alvo em `libs/`) ou
`grep -rn "<nome>(" apps/ --include=*.ts` (fora de `libs/`) e liste o que voltou. A correção vai na
função compartilhada, não no caminho que o relato nomeia: um guard na raiz é diff menor que um
guard por chamador, e corrigir só o caminho relatado deixa os irmãos quebrados.

Diagnóstico que emite `Correção mínima` sem essa lista está incompleto — declare isso em vez de
omitir.

```
CAUSA RAIZ (confiança alta|média|baixa)
<uma linha> — caminho/arquivo.ts:123
Evidência: <o trecho que prova>
Como confirmar: <comando ou passo que o usuário roda para fechar a questão>
Correção mínima: <a menor mudança que fecha o cenário>

DESCARTADAS
<hipótese> — derrubada por <evidência>
```

Se **nada** ficou sustentado, diga isso e liste o que falta observar. Diagnóstico honesto vazio é melhor que causa inventada — a correção errada custa mais que a investigação parada.

# Modo de falha

O erro plausível é **parar na primeira hipótese que encaixa**. O primeiro arquivo suspeito quase sempre tem algo estranho; estranho não é causa. Sem uma segunda hipótese que foi ativamente derrubada, o que você tem é confirmação, não diagnóstico.

O erro irmão é corrigir durante a investigação. Esta skill **diagnostica**; a correção é passo seguinte, com o usuário ciente.

# Mutações e efeitos

**Nenhuma.** Esta skill não escreve arquivo — e isso não é promessa de prosa: o frontmatter declara
`disallowed-tools: Edit, Write, NotebookEdit`, então as ferramentas de escrita **saem do pool**
enquanto a skill está ativa. A restrição cai na sua próxima mensagem, que é exatamente o "aval do
usuário" da tabela abaixo: para corrigir, o usuário responde e o passo seguinte começa com as
ferramentas de volta.

O que a skill escreve, então, é só o **relatório** no chat. Se você se pegar querendo editar durante
a investigação, a ferramenta não vai estar lá — e isso é o desenho, não uma falha do ambiente.

# Racionalizações barradas

| Desculpa | Por que está errada | Ação obrigatória |
| --- | --- | --- |
| "Já sei o que é, vou direto ao arquivo" | É a forma mais cara de errar: uma correção errada custa mais que quatro leituras | Três hipóteses escritas antes de abrir o segundo arquivo |
| "Já achei, aproveito e conserto" | Diagnóstico e mutação no mesmo passo tiram do usuário a chance de discordar da causa | Reportar a causa. Corrigir só depois do aval |
| "O `git log` não vai dizer nada" | "Quando começou" resolve regressão sozinho e custa uma chamada | Rodar sempre no Passo 1 |
| "Disparo cinco agentes para ir mais rápido" | Agentes concorrentes relendo o mesmo arquivo é custo puro | Respeitar a tabela de dimensionamento |
| "O bug é grave, uso o nível mais caro nos agentes" | Gravidade do sintoma não muda a natureza do trabalho: continua sendo procurar evidência em arquivo. O que aumenta a chance de achar é mais hipótese distinta, não agente mais caro | manter o nível intermediário; se sobra orçamento, gastar numa 4ª hipótese |

## Aviso de Cobertura

Se o protocolo não cobre o cenário, prosseguir e notificar:
> ℹ️ A skill `bug-diagnosis` não cobre este passo — prosseguindo com [breve descrição].
