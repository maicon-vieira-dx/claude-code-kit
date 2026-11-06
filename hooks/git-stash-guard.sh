#!/usr/bin/env bash
# PreToolUse (Bash): bloqueia stash de arvore inteira (sem pathspec).
#   Regra e racional completos em git-stash-guard.py (mesma forma dos pares
#   graphify-gate.sh/.py e vitest-pool-gate.sh/.py — evita escape de aspas).
#
# Classe: DENY-GATE DE DADO. Ao contrario dos gates fail-open, este NAO usa
# `2>/dev/null`: para um gate que nega, falhar em silencio e ABRIR o portao.
# Quando o interpretador nao esta disponivel, decide aqui mesmo, no escopo — so
# nega se o payload casar o subcomando em POSICAO DE COMANDO, nunca como
# substring de um argumento ou de um heredoc.
input=$(cat)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$SCRIPT_DIR/git-stash-guard.py"

if ! command -v python3 >/dev/null 2>&1 || [ ! -f "$PY" ]; then
  if printf '%s' "$input" | grep -qE '(^|[;&|(])[[:space:]]*git([[:space:]]+-[^[:space:]]+)*[[:space:]]+stash([[:space:]]|$)'; then
    printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"git-stash-guard nao conseguiu atestar (interpretador ausente) E o comando casa o padrao de risco. Stash que cria estado tem de delimitar paths: use a forma `push` seguida de `--` e os caminhos, ou o patch interativo `-p`. Subcomandos read-only (list/show/pop/apply/drop) sao liberados."},"systemMessage":"⛔ git-stash-guard: sem interpretador, negado por precaucao"}'
  else
    printf '%s\n' '{"systemMessage":"⚠ git-stash-guard: sem interpretador — liberado porque nao casa o padrao de risco"}'
  fi
  exit 0
fi

printf '%s' "$input" | python3 "$PY"
exit 0
