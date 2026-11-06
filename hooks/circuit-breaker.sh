#!/usr/bin/env bash
# PostToolUse (Bash): circuit breaker de retry loop.
# Detecta o MESMO comando executado consecutivamente N vezes (sinal de loop de
# retry — o ralo de tokens do turno 47) e injeta additionalContext pedindo mudança
# de abordagem. Não bloqueia: só nudge. Estado por-sessão em $TMPDIR.
#
# Classe: NUDGE. Quando não consegue atestar, ABRE (sai 0) — mas avisa, uma vez
# por sessão. Este é o hook em que o "uma vez" mais importa: avisar por invocação
# faria a própria falha recorrente disparar o disjuntor que ele é.
input=$(cat)
# BOM UTF-8 antes do JSON quebra o parse e o hook morre calado.
input="${input#$'\xef\xbb\xbf'}"

CB_WARN="${TMPDIR:-/tmp}/claude-circuit-warned"
avisar_uma_vez() {
  [ -f "$CB_WARN" ] && return 0
  : > "$CB_WARN" 2>/dev/null
  printf '%s\n' "{\"systemMessage\":\"$1\"}"
}

if ! command -v python3 >/dev/null 2>&1; then
  avisar_uma_vez "⚠ circuit-breaker: sem interpretador — loop de retry não está sendo detectado"
  exit 0
fi

parsed=$(printf '%s' "$input" | python3 -c '
import sys, json, hashlib
try: d = json.load(sys.stdin)
except Exception:
    print("PARSE_FAIL"); sys.exit(0)
sid = d.get("session_id") or "nosession"
cmd = ((d.get("tool_input") or {}).get("command") or "").strip()
if not cmd: sys.exit(0)
h = hashlib.sha1(cmd.encode()).hexdigest()[:16]
print(sid, h)')

if [ "$parsed" = "PARSE_FAIL" ]; then
  avisar_uma_vez "⚠ circuit-breaker: payload ilegível — loop de retry não está sendo detectado"
  exit 0
fi

[ -n "$parsed" ] || exit 0
read -r sid h <<<"$parsed"
[ -n "$h" ] || exit 0

THRESHOLD=3
state="${TMPDIR:-/tmp}/claude-circuit-${sid}"
prev=""; count=0
[ -f "$state" ] && read -r prev count < "$state"
[ -n "$count" ] || count=0

if [ "$h" = "$prev" ]; then
  count=$((count + 1))
else
  count=1
fi
printf '%s %s\n' "$h" "$count" > "$state"

if [ "$count" -ge "$THRESHOLD" ]; then
  printf '%s 0\n' "$h" > "$state"   # zera para não avisar a cada execução seguinte
  python3 -c '
import json, sys
n = sys.argv[1]
ctx = ("Circuit breaker: o MESMO comando foi executado " + n + "x seguidas. "
       "Se está falhando, PARE de repetir — leia o erro real, isole a causa ou "
       "confirme com o usuario antes de continuar. Loop de retry queima tokens sem progresso.")
print(json.dumps({
  "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": ctx},
  "systemMessage": "⚠ circuit-breaker: " + n + "x o mesmo comando seguido"
}))' "$count"
fi
exit 0
