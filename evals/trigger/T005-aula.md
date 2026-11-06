# T005 — `aula-de-codigo` × `bug-diagnosis` × `graphify-search`

A fronteira é o **objetivo** do pedido: aprender o mecanismo para reproduzi-lo (aula), achar a causa de um sintoma (diagnosis) ou só localizar código (graphify-search). "Por que..." aparece nos três.

## Positivos de `aula-de-codigo`

| # | Prompt | Dono esperado | `bug-diagnosis` pode disparar? |
| --- | --- | --- | --- |
| 1 | "Me explica didaticamente como funciona o interceptor de refresh de token" | `aula-de-codigo` | NÃO |
| 2 | "Ainda não entendi o fluxo dessa store, vamos uma parte de cada vez" | `aula-de-codigo` | NÃO |
| 3 | "Me ensina como esse guard funciona pra eu conseguir criar um próprio" | `aula-de-codigo` | NÃO |
| 4 | "Seja meu professor nesse switchMap" | `aula-de-codigo` | NÃO |
| 5 | "Me mostra com analogia como o HttpContextToken funciona" | `aula-de-codigo` | NÃO |
| 6 | "Por que o interceptor precisa ficar por último? Quero entender de verdade" | `aula-de-codigo` | NÃO |
| 7 | "Explica passo a passo o fluxo do dialog até o reenvio" | `aula-de-codigo` | NÃO |
| 8 | "Quero aprender a escrever um decorator de validação igual a esse" | `aula-de-codigo` | NÃO |

## Near-misses (`aula-de-codigo` não deve disparar)

| # | Prompt | Dono esperado | Por quê |
| --- | --- | --- | --- |
| 9 | "Por que o dialog não abre quando o token expira? Está quebrado" | `bug-diagnosis` | Sintoma em produção: o objetivo é a causa |
| 10 | "Onde fica o interceptor de refresh de token em libs?" | `graphify-search` | Localizar, não ensinar |
| 11 | "Quem chama o SessaoExpiradaDialog?" | `graphify-search` | Localizar chamadores |
| 12 | "O que significa esse `?? null`?" | nenhuma | Pergunta pontual de um parágrafo |
| 13 | "Cria um interceptor que adiciona o header de tenant" | nenhuma (implementação) | Pede código, não aula |

O prompt 6 é o mais traiçoeiro: começa com "por que", que é vocabulário da `bug-diagnosis`, mas não há sintoma, e "quero entender" decide. Se a `bug-diagnosis` disparar ali, o rodapé "para aprender como um mecanismo funciona, sem sintoma a investigar, ver aula-de-codigo" da descrição dela está fraco.
