# `sandbox/` — working dir efêmero

Código gerado pelos benchmarks nasce aqui, em `sandbox/<run-id>/`, espelhando os caminhos que teriam
em `libs/` (ex.: `sandbox/<run-id>/libs/<dominio>/feature-<nome>/...`).

**Invariante (CHARTER P10):** nada aqui entra no grafo do Nx, no build ou no CI. É descartável.

- O conteúdo de `sandbox/*` é **gitignored** (ver `.claude/evals/.gitignore`).
- O artefato que você audita e que fica versionado é `runs/<run-id>/sandbox-snapshot/`, copiado ao
  fim da execução (passo 4 do `runbook.md`).
- Pode apagar `sandbox/<run-id>/` a qualquer momento depois do snapshot.
