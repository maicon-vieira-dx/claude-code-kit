---
paths:
  - 'apps/<app-pwa>/**' # ajuste para o(s) app(s) PWA do projeto
  - 'apps/<app-admin>/**' # ajuste para o painel administrativo
  - '**/*.routes.ts'
  - '**/main.ts'
---

> **Escopo:** rule pessoal para monorepo Angular (Nx). Mora em `~/.claude/rules/`, fora do repositório — não vale para o time. Ajuste os globs e os apps citados ao projeto em que for usar.

# Performance web

O gargalo destes apps **não** é o de uma página pública. São dois, e são diferentes entre si:

| App | Gargalo real | O que medir |
| --- | --- | --- |
| PWA de campo (apps mobile) | Tempo de boot do bundle e primeira interação em celular ruim, offline ou 3G | Tamanho do bundle inicial, TTI, tempo até a primeira tela útil |
| Painel administrativo (autenticado) | INP em tabela grande e re-render de lista | INP, trabalho na thread principal, nº de nós na tabela |

Métrica de página pública (LCP de hero, SEO) quase não se aplica: as telas relevantes ficam **atrás de login**.

## O que fazer, em ordem de retorno

1. **Rota lazy.** Toda feature entra por `loadComponent`/`loadChildren`. Rota carregada no bundle inicial é o custo mais caro e o mais fácil de remover.
2. **`@defer` no que está abaixo da dobra** — mapa, gráfico, modal, lista longa. `@defer (on viewport)` para conteúdo secundário; `on interaction` para o que só abre com clique.
3. **`ChangeDetectionStrategy.OnPush`** em todo componente novo. Com Signals, é o padrão — não é otimização, é o modo correto.
4. **Virtual scroll** (`cdk-virtual-scroll-viewport`) em qualquer lista que cresça com os dados. Já é regra do `AGENTS.md`; aqui é também a maior alavanca de INP.
5. **Imagem** — `NgOptimizedImage` com `width`/`height` sempre declarados (evita layout shift), `priority` só na imagem que aparece de cara.
6. **`trackBy` / `track`** em toda iteração. Sem isso, o Angular recria a lista inteira a cada mudança.

## O que não fazer

- Não trocar biblioteca por causa de bundle size sem medir antes e depois.
- Não adicionar ferramenta de medição ao `package.json` por conta própria.
- Não otimizar imagem ou fonte do painel administrativo achando que é ganho de usuário: é tela autenticada, cacheada depois do primeiro acesso.

## Critério que reprova

Alegação de ganho sem **dois números do mesmo comando**, antes e depois. `npx nx build <app> --configuration=production` imprime o tamanho dos bundles — é a medida mais barata que existe aqui e não depende de instalar nada.

"Ficou mais rápido" sem par de números não é resultado, é impressão.
