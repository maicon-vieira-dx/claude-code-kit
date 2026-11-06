#!/usr/bin/env bash
# PreToolUse (Bash|PowerShell): exige --pool=forks nas rodadas de Vitest.
# O pool padrao (`threads`) segfaulta (exit 139) nesta maquina Windows, e `pool`
# nao tem variavel de ambiente — so flag de CLI ou arquivo de config versionado.
# Como a config NAO deve ser versionada, a flag e o unico caminho.
# A logica vive em vitest-pool-gate.py.
#
# Classe: DENY-GATE DE SEGURANCA. Por isso NAO usa `2>/dev/null`: para um gate
# que nega, falhar em silencio e ABRIR o portao — aqui, deixar a suite segfaultar.
# Sem interpretador, decide aqui mesmo, no escopo: so nega se o payload parecer
# uma invocacao de Vitest sem a flag. Em todos os caminhos o remedio (o comando
# corrigido) vai junto da negativa.
input=$(cat)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$SCRIPT_DIR/vitest-pool-gate.py"

if ! command -v python3 >/dev/null 2>&1 || [ ! -f "$PY" ]; then
  if printf '%s' "$input" | grep -qE '(vitest|nx[^\n]*(run-many|run)[^\n]*test|nx[^\n]+:test)' \
     && ! printf '%s' "$input" | grep -q -- '--pool=forks'; then
    printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"vitest-pool-gate nao conseguiu atestar (interpretador ausente) E o comando parece rodar Vitest sem o pool exigido. Toda rodada leva `--pool=forks --minWorkers=1`: o pool padrao (threads) segfaulta (exit 139) nesta maquina. NAO passe maxForks nem minForks (o teto vem de VITEST_MAX_FORKS=2; flag pontilhada e re-serializada como JSON e ignorada). Reenvie o comando com `--pool=forks --minWorkers=1`."},"systemMessage":"⛔ vitest-pool-gate: sem interpretador, negado por precaucao"}'
  else
    printf '%s\n' '{"systemMessage":"⚠ vitest-pool-gate: sem interpretador — liberado porque nao casa o padrao de risco"}'
  fi
  exit 0
fi

printf '%s' "$input" | python3 "$PY"
exit 0
