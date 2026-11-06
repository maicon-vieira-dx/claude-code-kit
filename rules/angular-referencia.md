---
paths:
  - '**/*.component.ts'
  - '**/*.service.ts'
  - '**/*.store.ts'
  - '**/*.guard.ts'
  - '**/*.resolver.ts'
---

> **Escopo:** rule pessoal para monorepo Angular (Nx). Mora em `~/.claude/rules/`, fora do repositório — não vale para o time. Ajuste os globs e as bibliotecas citadas ao stack do projeto em que for usar.

# Angular 19 — referência de API

Recorte curado do material oficial do time do Angular (`angular/skills`), limitado ao que **existe na 19.0.0** e ao que este repositório usa.

> **Precedência:** quando o material oficial do Angular divergir do `AGENTS.md`, **o `AGENTS.md` vence**. Conteúdo de primeira parte é o mais perigoso quando diverge da norma interna, porque soa autoritativo. Esta rule é consultiva; a porta de entrada para escrever componente é a skill de componentes do projeto, se houver.

## Versão importa — o que NÃO existe aqui

| Não usar | Por quê |
| --- | --- |
| **Signal Forms** (`@angular/forms/signals`) | API da **v21**. Este monorepo está em `@angular/core 19.0.0`. Formulário aqui é **Reactive Forms** tipado |
| `@angular/aria` | Pacote **não instalado**, e instalar dependência não é decisão do agente. Para foco e ARIA use `@angular/cdk/a11y`, que já está no `package.json` |
| `provideZonelessChangeDetection()` | Estável só a partir da v20 |

Sugestão de API que não compila na 19 é pior que nenhuma sugestão: custa um ciclo inteiro de build para descobrir.

## O que usar

**Reatividade** — `signal()`, `computed()`, `linkedSignal()`, `effect()`. `input()` / `input.required()` / `model()` / `output()` no lugar dos decorators. `viewChild()` / `contentChild()` como signal queries.

**Dado assíncrono** — `resource()` e `httpResource()` existem na 19 e são **experimentais**. Em código de produção, o padrão do repositório continua sendo `rxMethod` da SignalStore (ver `AGENTS.md` → Assincronicidade na Store). Não troque um pelo outro sem decisão do time.

**DI** — `inject()` em campo `private readonly`, nunca parâmetro de construtor. É também a ordem de membros exigida pelo `AGENTS.md`.

**Controle de fluxo** — `@if` / `@for` (sempre com `track`) / `@switch` / `@defer`. Sem `*ngIf` e `*ngFor` em código novo.

**Componente** — standalone por padrão na 19 (não declarar `standalone: true`, é redundante), `ChangeDetectionStrategy.OnPush`.

**Rota** — `withComponentInputBinding()`; parâmetro chega por `input()` com `transform`, nunca lendo `ActivatedRoute` na mão.

## Critério que reprova

Antes de propor qualquer API que você não viu escrita neste repositório, confirme que ela existe na 19: procure o símbolo em `node_modules/@angular/core` ou num arquivo do próprio projeto. "É assim que o Angular moderno faz" sem confirmar a versão é exatamente como Signal Forms entraria aqui.
