---
paths:
  - "libs/**"
---

# Pesquisa obrigatória em libs/

`graphify-out/graph.json` indexa **exclusivamente `libs/`** (`apps/` não é coberto).

- **ANTES** de ler, buscar ou editar qualquer arquivo em `libs/`: invocar a skill `graphify-search`.
- **PROIBIDO** `grep`/`find`/`Read` exploratório de **código** em `libs/` sem graphify. Fora de `libs/`: liberados.
- **Exceção:** localizar arquivo de **config/build** (`project.json`, `tsconfig*`, `*.json`) não é busca de código — `ls`/`Read` direto liberados.
- Antes de criar interface/componente/util: `graphify query "<artefato> <domínio>" --dfs`. Criar só se ausente.
- Pesquisar `libs/shared/*` antes de criar artefato novo; Lodash para lógica genérica.

> A obrigatoriedade está aqui; o protocolo de execução está na skill `graphify-search` (mais específica, vence em conflito).
