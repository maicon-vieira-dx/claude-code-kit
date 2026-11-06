---
paths:
  - 'apps/<app-pwa>/**' # ajuste para o(s) app(s) PWA do projeto
  - '**/*.store.ts'
  - '**/ngsw-config.json'
---

> **Escopo:** rule pessoal para monorepo Angular (Nx). Mora em `~/.claude/rules/`, fora do repositório — não vale para o time. Ajuste os globs e as dependências citadas ao stack do projeto em que for usar.

# Offline-first (PWA de campo)

O usuário trabalha em campo, sem rede confiável. Perder um formulário preenchido é o pior defeito possível de um app de campo — pior que tela feia, pior que lentidão.

## As peças que já existem (não escolher outras)

| Necessidade | Dependência já no `package.json` |
| --- | --- |
| Detectar rede | `@capacitor/network` 6 |
| Chave-valor pequeno (flags, último sync) | `@capacitor/preferences` 6 |
| Dado estruturado e volumoso (rascunho, fila) | `idb` 8 (IndexedDB) |
| Cache de shell e asset | `@angular/service-worker` 19 (`ngsw-config.json`) |

**Não introduzir** SQLite, Workbox, Dexie ou biblioteca de sync sem decisão arquitetural explícita — as quatro acima cobrem o caso e já estão pagas.

## Regras

- **Escrita é otimista, e a fila é durável.** Grave no estado local **e** no IndexedDB antes de tentar a rede. Fila só em memória morre quando o app é morto pelo SO — que é o caso comum em celular de campo.
- **Toda entrada da fila tem `id` idempotente do cliente.** O backend precisa poder receber a mesma entrada duas vezes sem duplicar; sem isso, o retry cria registro fantasma.
- **Conflito resolve com regra escrita, nunca com "o último ganha" implícito.** Declare no código quem vence e por quê.
- **Estado de rede é dado de UI.** O usuário tem que ver que está offline e quantos itens estão pendentes de envio — silêncio aqui vira "sumiu o que eu digitei".
- **`ngsw-config.json` cacheia shell e asset; nunca resposta de API mutável.** Dado de negócio em cache do service worker vira tela inconsistente sem caminho de invalidação.
- Estado offline vive na SignalStore da feature, seguindo o padrão de `libs/**/data-access`. Não criar um segundo mecanismo de estado paralelo à store.

## Critério que reprova

Rode o fluxo com o DevTools em **Offline**: preencher, sair da tela, matar a aba, reabrir. Reprova se o rascunho sumiu, se a fila esvaziou sem ter enviado, ou se a UI não mostrou que havia pendência.

Voltar para online e ver o item subir duas vezes também reprova — é falta de idempotência.
