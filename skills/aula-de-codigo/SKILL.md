---
name: aula-de-codigo
description: Ensina em partes, uma por vez, como um mecanismo real do repositório funciona, para o usuário conseguir escrever um igual sozinho depois. Segue PRIMM (prever, rodar, investigar, modificar, criar), exemplos resolvidos que vão sumindo e rastreamento de código, com cada passo ancorado em arquivo:linha e diff reais, uma analogia que atravessa a aula toda e uma pergunta de previsão no fim de cada parte. Invoque quando o usuário disser "me explica didaticamente", "não entendi o fluxo", "me ensina como funciona", "quero entender para criar um próprio", "vamos uma parte de cada vez", "seja meu professor", "me mostra com analogia". Também quando o usuário pedir para aprender um mecanismo (interceptor, guard, store, operador RxJS, decorator) a ponto de reproduzi-lo. Cobre o roteiro, as partes, a correção das previsões e o exercício final, que o usuário escreve. Para descobrir por que um bug acontece, ver bug-diagnosis; para só localizar código em libs/, ver graphify-search.
argument-hint: "[mecanismo ou arquivo a ensinar]"
metadata:
  version: 1.0.0
---

# Quando usar

O usuário quer **entender um mecanismo a ponto de escrever um igual**, e aceita ir por partes.

| Pedido parecido | Vai para |
| --- | --- |
| "Por que isso está dando erro?", stack trace, regressão | `bug-diagnosis`: o objetivo é a causa, não o aprendizado |
| "Onde fica X em `libs/`?", "quem chama Y?" | `graphify-search`: é localizar, não ensinar |
| Pergunta pontual que um parágrafo resolve ("o que faz esse `?? null`?") | resposta direta, sem skill |
| "Implementa X" | a skill de implementação do artefato; esta skill nunca escreve código no projeto |

# Pré-condições: ler antes da Parte 1

Nenhuma linha é citada sem ter sido lida nesta sessão. Antes da primeira mensagem de aula:

1. Leia o mecanismo inteiro, o ponto onde ele é **registrado** (`app.config.ts`, módulo, `providers`), **quem o aciona** (o chamador) e a **porta/contrato** que ele usa. Em `libs/`, a busca passa pelo `graphify-search`.
2. Ache os diffs que contam a história: `git log --oneline -- <arquivo>` e depois `git show <sha> -- <arquivo>`. Diff real ensina melhor que código pronto, porque mostra a decisão.
3. Leia o `.spec.ts` do mecanismo, se houver: os nomes dos `it(...)` são o contrato em português e viram bons distratores para as previsões.

# Fluxo

## 1. Abertura (só na primeira mensagem)

- **Método em três itens**: PRIMM, exemplos resolvidos que vão sumindo, rastreamento. Uma linha cada.
- **Roteiro** em tabela `| # | Parte | Arquivo |`, com 4 a 7 partes, marcando a atual com `← hoje`. As duas últimas são sempre **o mock/variação** (modificar) e **"Você escreve o seu (eu só oriento)"** (criar).
- Depois, a Parte 1 no formato abaixo.

## 2. Cada parte, nesta ordem

| Bloco | O que entra | Reprova se |
| --- | --- | --- |
| **Retomar** | Resposta da previsão ou do "teste de cabeça" da parte anterior | a parte começa sem fechar a pergunta pendente |
| **Problema** | Que problema esta peça resolve; quando há escolha de design, tabela `Jeito \| Como seria \| Problema` | o "por quê" da peça não aparece |
| **Analogia** | A **mesma** da Parte 1, estendida (guichês → post-it no envelope → funcionário que liga para você) | troca de analogia no meio da aula |
| **Código** | Trechos de até 15 linhas com `arquivo:linha` e anotação inline `// └── ...`; diff real quando existir | trecho sem caminho e linha, ou colado de memória |
| **Rastrear** | Um caso concreto seguido passo a passo: lista numerada ou diagrama ASCII de ida e volta | só descreve, sem seguir um caso |
| **Regra para guardar** | Uma frase em negrito que o usuário leva para o próximo mecanismo | regra ausente, ou mais de uma |
| **Prever** | `AskUserQuestion`: 1 pergunta (2 só se forem do mesmo conceito), 4 opções, 1 certa, distratores = equívocos reais | a resposta aparece no texto antes da pergunta |

**Um conceito novo por parte.** Se a parte precisa de glossário com mais de três termos novos, ou de dois "por quê" independentes, divida em duas partes antes de enviar. Na primeira execução, a parte que juntou `catchError` + `from`/`switchMap` + contexto de injeção + recursão + cópia de `FormData` foi exatamente onde o usuário parou para esclarecer.

**A pergunta de previsão** pede para **prever comportamento** ("o que o usuário vê?", "o backend recebe?"), nunca para lembrar nome ("qual operador captura o erro?"). Cada distrator é um modelo mental errado que alguém de fato tem ("o backend sempre recebe", "a ordem não importa").

## 3. Corrigir a resposta

| Resposta | Ação |
| --- | --- |
| Certa | Confirmar em 1–2 linhas **com o porquê** e ligar à regra da parte anterior quando for a mesma ("é a regra da Parte 1 de novo") |
| Errada | Dizer que é o equívoco mais comum, sem julgamento; **re-rastrear com o diagrama na condição exata da pergunta**; dar a resposta certa; fechar com a regra para guardar |
| "Não sei" / "não entendi X" | Desmontar **só X**: analogia curta + tabela de rastreio com 2–3 casos; então refazer a pergunta original com a peça no lugar e responder |
| Pede esclarecimento, ou rejeita a pergunta | **Parar.** Não emendar outra `AskUserQuestion`; esperar o usuário escrever a dúvida |

## 4. Avançar

Ofereça a próxima parte, mais um exercício ou um espaço para dúvida, e avance só quando o usuário escolher. Depois de uma rejeição (linha final da tabela acima), não ofereça nada: espere.

## 5. Modificar e criar (o exemplo resolvido some)

- **Modificar**: o usuário prevê o efeito de uma mudança pequena no código existente ("e se o mock ficasse antes?", "e se o padrão do token fosse `true`?").
- **Criar**: entregar no chat **só o esqueleto** (assinatura, guard clauses com `TODO`, onde registrar) e os critérios de pronto. **O usuário escreve.** Nada de `Write`/`Edit` em arquivo do projeto durante a aula; testar e revisar só depois que o usuário avisar que terminou.

# Formato fixo

- Português; termo em inglês ganha a tradução entre parênteses na primeira aparição (`catchError`, capturar o erro). Identificador de código não é traduzido.
- Seções com `##`/`###`, sem parágrafo longo: tabela quando houver comparação, diagrama quando houver ida e volta.
- Fontes da pesquisa pedagógica só na primeira mensagem em que a pesquisa foi citada.

# Critério que reprova a parte

Antes de enviar, a parte falha se qualquer item for falso:

1. Todo `arquivo:linha` citado foi aberto com `Read`/`Bash` nesta sessão e a linha bate.
2. Existe **exatamente um** conceito novo (contar os termos novos do glossário: até 3).
3. A analogia é a mesma da Parte 1.
4. Há uma frase "regra para guardar".
5. A parte termina em `AskUserQuestion` de previsão cujas 4 opções não estão respondidas no próprio texto. A exceção é uma resposta a pedido de esclarecimento, que termina sem pergunta.
6. Nenhum `Write`/`Edit` em arquivo do projeto desde o início da aula.

# Modo de falha

| Erro (comete mesmo tendo lido isto) | Sinal | Contra-ação |
| --- | --- | --- |
| Despejar o arquivo inteiro numa parte | glossário com 5 termos, 3 blocos de código de funções diferentes | dividir antes de enviar |
| Citar linha de memória | número de linha sem `Read` correspondente na sessão | abrir o arquivo e conferir |
| Entregar a resposta no texto | a explicação antes da pergunta já diz o resultado | mover a explicação para a parte seguinte (bloco Retomar) |
| Fazer pergunta de decoreba | opções são nomes de API | trocar por "o que acontece quando..." |
| Insistir com pergunta depois de rejeição | duas `AskUserQuestion` seguidas rejeitadas | parar e esperar |

# Racionalizações barradas

| Desculpa | Por que está errado | Ação obrigatória |
| --- | --- | --- |
| "Ele pediu para entender tudo, mando o fluxo completo" | sobrecarga é o que fez o usuário travar na Parte 3 da primeira execução | roteiro + Parte 1; o resto vem por partes |
| "Já sei como interceptor funciona, não preciso ler" | a aula é sobre **este** código: linha errada destrói a confiança | Pré-condições, item 1 |
| "Errou, só digo a certa e sigo" | sem re-rastrear, o modelo mental errado sobrevive | linha "Errada" da tabela de correção |
| "É mais rápido eu escrever o exercício para ele" | quem aprende é quem escreve | esqueleto no chat; o usuário escreve |
| "Ele não entendeu a pergunta, faço outra por cima" | empilhar pergunta é pressão, não ensino | parar e esperar |

# Fallback

- **O mecanismo não existe no repositório**: procure um análogo real (`grep -rn "HttpInterceptorFn" apps/ libs/ --include=*.ts`). Só se nada aparecer, monte um exemplo mínimo no chat marcado **"ilustrativo, não existe no repo"**.
- **O usuário pede para pular a previsão**: pule nessa parte e nas seguintes, sem insistir.
- **O usuário pede tudo de uma vez**: roteiro + resumo de 5 linhas do fluxo inteiro + Parte 1.
- Caso não coberto: siga e avise numa linha: `ℹ️ A skill aula-de-codigo não cobre este passo — prosseguindo com [descrição].`

# Base

- PRIMM (Sue Sentance, Raspberry Pi Computing Education Research Centre): https://faq.computersciencewiki.org/index.php/intro/article/primm
- Exemplos resolvidos e esmaecimento (*fading*): https://static.raspberrypi.org/files/curriculum/quickreads/2-Pedagogy_Summary_Worked_Examples_V6_2023.pdf
- Rastreamento de código: https://digitaltechnologieshub.edu.au/teach-and-assess/effective-pedagogies/teaching-programming
