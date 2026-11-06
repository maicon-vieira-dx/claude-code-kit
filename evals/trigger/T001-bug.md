# T001 — `bug-hunt` × `bug-diagnosis`

O par mais provável de colidir: as duas descrições contêm "bug". A fronteira é **sintoma observado** (diagnosis) contra **diff não subido** (hunt).

## Positivos de `bug-diagnosis` (sintoma já aconteceu)

| # | Prompt | Dono esperado | `bug-hunt` pode disparar? |
| --- | --- | --- | --- |
| 1 | "Está dando erro ao enviar documento do cliente, olha esse stack trace" | `bug-diagnosis` | NÃO |
| 2 | "Parou de funcionar depois do último deploy" | `bug-diagnosis` | NÃO |
| 3 | "Por que o valor da parcela sai errado só no fim do mês?" | `bug-diagnosis` | NÃO |
| 4 | "Não consigo reproduzir, mas o cliente diz que a lista vem vazia" | `bug-diagnosis` | NÃO |
| 5 | "A tela trava carregando de vez em quando" | `bug-diagnosis` | NÃO |
| 6 | "Isso aqui quebrou e não sei por quê" | `bug-diagnosis` | NÃO |
| 7 | "Regressão: o filtro parou de resetar a página" | `bug-diagnosis` | NÃO |
| 8 | "Descobre a causa raiz desse comportamento" | `bug-diagnosis` | NÃO |
| 9 | "TypeError: cannot read properties of undefined — de onde vem isso?" | `bug-diagnosis` | NÃO |
| 10 | "O app some com o rascunho quando fica sem internet" | `bug-diagnosis` | NÃO |

## Positivos de `bug-hunt` (diff pronto, ainda não subiu)

| # | Prompt | Dono esperado | `bug-diagnosis` pode disparar? |
| --- | --- | --- | --- |
| 11 | "Revisa antes do PR" | `bug-hunt` | NÃO |
| 12 | "Posso subir?" | `bug-hunt` | NÃO |
| 13 | "Passa o olho no que eu fiz nessa branch" | `bug-hunt` | NÃO |
| 14 | "Tem bug aqui?" | `bug-hunt` | NÃO |
| 15 | "Terminei a implementação, confere pra mim" | `bug-hunt` | NÃO |
| 16 | "Caça-bug no diff" | `bug-hunt` | NÃO |
| 17 | "Antes de abrir a PR, dá uma varrida" | `bug-hunt` | NÃO |
| 18 | "Esse diff mexe em auth, olha com cuidado" | `bug-hunt` | NÃO |

## Near-misses (nenhuma das duas deve disparar)

| # | Prompt | Dono esperado | Por quê |
| --- | --- | --- | --- |
| 20 | "Tira a cara de IA desse layout" | `interface-design` | É craft visual, não defeito funcional |
| 21 | "A tela ficou torta depois que mexi no CSS" | `playwright-validation` | Sintoma **visual** de mudança própria: diagnóstico estático de HTML/CSS |
| 22 | "Simplifica esse código" | `/simplify` (nativo) | Qualidade, não bug |

O prompt 21 é o mais traiçoeiro do fixture: tem sintoma observado e mudança recente, e ainda assim o dono é a validação visual. Se `bug-diagnosis` disparar aqui, falta o rodapé de vizinhança na descrição dela.
