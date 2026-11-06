---
paths:
  - '**/*.component.html'
  - '**/*.component.ts'
  - 'libs/**/ui/**'
  - 'libs/**/ui-mobile/**'
---

> **Escopo:** rule pessoal para monorepo Angular (Nx). Mora em `~/.claude/rules/`, fora do repositório — não vale para o time. Ajuste os globs e as bibliotecas citadas ao stack do projeto em que for usar.

# Acessibilidade (WCAG 2.2 AA)

Produto com formulário pesado e dado pessoal tem exposição regulatória real. O alvo é **AA**; AAA só onde o time decidir explicitamente.

## O que quebra na prática, nesta ordem

| Falha | Como aparece aqui | Correção |
| --- | --- | --- |
| Campo sem nome acessível | `<input>` com placeholder no lugar de `<label>` | `<label for>` real, ou `aria-label`. Placeholder **não** é rótulo — some ao digitar |
| Erro de formulário mudo | Mensagem aparece na tela, leitor de tela não anuncia | `aria-describedby` apontando para a mensagem + `aria-invalid="true"` no controle |
| Erro em lote sem foco | Submit falha, a página não move o foco | Mover foco para o primeiro campo inválido, ou para um resumo com `role="alert"` |
| Controle inventado | `<div (click)>` como botão | `<button>`. Se precisa mesmo ser custom: `role`, `tabindex="0"`, Enter **e** Space, e foco visível |
| Modal que vaza foco | Tab sai do diálogo para a página atrás | `cdkTrapFocus` (`@angular/cdk/a11y`), ou o componente de modal do `ng-zorro-antd` |
| Foco invisível | `outline: none` sem substituto | `:focus-visible` com contraste ≥ 3:1 contra o fundo |
| Alvo pequeno no PWA mobile | Ícone de 24px em tela de celular | Mínimo **24×24 CSS px** (WCAG 2.2 AA, critério 2.5.8). O confortável é 44×44 |
| Estado só por cor | Pendência sinalizada só em vermelho | Cor **mais** ícone ou texto. Contraste de texto ≥ 4.5:1; ≥ 3:1 para texto grande e para borda de controle |
| Conteúdo que muda sem aviso | Lista recarrega após filtro | `aria-live="polite"` na região que muda |

## Regras desta base

- **Ionic e ng-zorro já entregam semântica** — use o componente da biblioteca antes de escrever ARIA na mão. ARIA manual em cima de componente pronto costuma **piorar**: papel duplicado, rótulo duplicado.
- **`@angular/cdk/a11y`** é a ferramenta padrão para foco: `cdkTrapFocus`, `FocusMonitor`, `LiveAnnouncer`.
- **Não instalar scanner por conta própria.** `@axe-core/*` não está no `package.json`; adicionar dependência é decisão do time.
- Rótulo, mensagem de erro e texto alternativo em **português**, como todo texto de usuário.

## Critério que reprova

Percorra a tela **só com Tab, Shift+Tab, Enter, Space e Esc**, sem mouse. Reprova se: algum controle não recebe foco, o foco não é visível em algum passo, o foco entra num modal e não sai com Esc, ou você não consegue submeter e corrigir um formulário com erro.

Não vale dizer "está acessível" sem ter feito esse percurso.
