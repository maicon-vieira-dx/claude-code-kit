#!/usr/bin/env bash
# PreToolUse (Task|Agent): impede o ENXAME de subagentes concorrentes sob um plano
# de rota (a). A rota (a) é single-session/serial (ver plan-generation/SKILL.md) —
# o executor não deve abrir vários agentes paralelos sobre a mesma working tree
# (foi a topologia que estourou o custo ~30× e causou git-stash near-miss num incidente real).
#
# Regra calibrada (um read-only é legítimo; o enxame de escrita não):
#   - plano ativo NÃO é rota (a)      -> libera (rota b/c decidem topologia própria)
#   - 1º subagente sob rota (a)       -> libera em silêncio (ex.: 1 Explore read-only)
#   - 2º dentro da janela             -> libera + nudge (pode ser fan-out de escrita)
#   - 3º+ dentro da janela            -> DENY (enxame: o padrão do incidente)
# Estado por-sessão em $TMPDIR; janela de 300s.
#
# Classe: DENY-GATE DE DISPATCH. A polaridade quando não consegue atestar é
# ABRIR — negar todo Task por um payload quebrado travaria a sessão inteira, e
# o custo do enxame que escapa é recuperável, o da sessão travada não. Mas
# avisa: gate mudo é portão invisível.
input=$(cat)
# BOM UTF-8 antes do JSON quebra o parse e o guard fica inerte em silêncio.
input="${input#$'\xef\xbb\xbf'}"

RA_WARN="${TMPDIR:-/tmp}/claude-routea-warned"
if ! command -v python3 >/dev/null 2>&1; then
  if [ ! -f "$RA_WARN" ]; then
    : > "$RA_WARN" 2>/dev/null
    printf '%s\n' '{"systemMessage":"⚠ route-a-guard: sem interpretador — freio de enxame e gate de base quebrada não estão atuando"}'
  fi
  exit 0
fi

parsed=$(printf '%s' "$input" | python3 -c '
import sys, json, glob, os, re, time
try: d = json.load(sys.stdin)
except Exception: sys.exit(0)
if d.get("tool_name","") not in ("Task","Agent"): sys.exit(0)

# Bypass: fan-out READ-ONLY de skill conhecida NAO e o alvo deste guard. O que
# o incidente provou caro/perigoso foi escrita concorrente em src/ — ler o mesmo
# working tree em paralelo nao corrompe nada e nao dispara git-stash.
#   - /graphify -> subagentes escrevem so em graphify-out/, fora do src.
#   - /bug-hunt -> subagentes so LEEM o diff (a skill PROIBE editar) e ela
#     mesma limita a onda a 4 agentes, entao o freio de enxame ja existe la.
# Detecta pelo marcador que a propria skill injeta no prompt/description do
# subagente, nunca pelo plano ativo. IMPORTANTE p/ quem despacha bug-hunt:
# cite "bug-hunt" no prompt de TODO subagente (lote, lente e advogado do
# diabo) — sem o marcador, o 3o spawn da onda leva DENY.
ti = d.get("tool_input", {}) or {}
blob = json.dumps(ti, ensure_ascii=False)
READONLY_SKILL_MARKERS = ("graphify-out/", "bug-hunt")
if any(marker in blob for marker in READONLY_SKILL_MARKERS):
    sys.exit(0)

# Plano ativo = plan.md modificado mais recentemente.
# Varre os DOIS destinos: o repo (.claude/plans/) e o overlay pessoal
# (~/.claude/plans/). A preferencia atual e a segunda — varrer so o repo
# deixava este guard inerte, sem freio de enxame nem gate de base quebrada.
proj = os.environ.get("CLAUDE_PROJECT_DIR",".")
plans = (glob.glob(os.path.join(proj,".claude","plans","*.md"))
         + glob.glob(os.path.expanduser("~/.claude/plans/*.md")))
if not plans: sys.exit(0)
active = max(plans, key=os.path.getmtime)
# Só age se o plano foi tocado nas últimas 6h (evita plano velho travar sessão nova).
if time.time() - os.path.getmtime(active) > 6*3600: sys.exit(0)
try:
    txt = open(active, encoding="utf-8").read()
except Exception: sys.exit(0)

# Extrai a secao de decisoes de execucao. Dois formatos convivem:
#   - ANTIGO (ate 2026-07-30): "## Execução" com "Rota:** (a)" / "Topologia:** ... uma janela"
#   - NOVO   (2026-07-31+):    "## Decisões de execução" com os campos D1..D4
# Sem casar o formato novo este guard fica INERTE em todo plano novo — silenciosamente,
# que e o pior modo de falha para um freio de enxame.
m = re.search(r"##\s*(?:Decis[õo]es de execu[çc][ãa]o|Execu[çc][ãa]o)(.*?)(\n##\s|\Z)", txt, re.S)
sec = m.group(1) if m else txt

# Formato antigo: so a rota (a) era single-session/serial.
is_serial = (bool(re.search(r"Rota:\*\*\s*\(a\)", sec))
             or bool(re.search(r"Topologia:\*\*[^\n]*uma janela", sec)))

# Formato novo: o veto a subagentes PARALELOS sobre a mesma working tree e
# INCONDICIONAL (plan-generation D3: "UM subagente por lote, em serie"). Logo,
# basta o plano usar o template novo para o freio valer — inclusive quando a
# D3 escolheu delegar, que e justamente quando o enxame tenta acontecer.
# O campo D3 aparece em duas grafias, e casar so uma deixa o guard INERTE em
# silencio (medido em 21/09: "### D3 — Quem executa:" nao casava "**D3...executor:"):
#   - inline em negrito:  "**D3 — executor: ..."
#   - como cabecalho:     "### D3 — Quem executa: ..."
if re.search(r"(?:\*\*|#{1,6}\s*)D3\b[^\n]*execut(?:or|a)", sec):
    is_serial = True

if not is_serial: sys.exit(0)

sid = d.get("session_id") or "nosession"
print(sid + " " + os.path.basename(active))' 2>/dev/null)

[ -n "$parsed" ] || exit 0
read -r sid plan <<<"$parsed"
[ -n "$sid" ] || exit 0

# Gate de BASE-QUEBRADA: nao despache subagente sobre uma base que nao compila.
# Reusa o mesmo script do stop-check (fonte de verdade unica do "ngc das libs
# tocadas"). So roda aqui porque ja passamos o gate de rota (a) acima -> custo do
# ngc limitado aos dispatches desse regime. Foi o furo desta sessao: agentes
# despachados sobre um *-api.service.ts antes de os imports de barrel dos
# novos Input/Output entrarem -> executor frio herda base quebrada e re-deriva errado.
ngcmsg=$(printf '%s' "$input" | bash "${HOME}/.claude/hooks/ngc-touched-libs.sh" 2>/dev/null)
if [ -n "$ngcmsg" ]; then
  python3 -c 'import json,sys; print(json.dumps({"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Nao despache subagente: a base nao compila (ngc) em arquivo(s) que esta sessao alterou. Um executor frio herda a base quebrada e re-deriva errado. Corrija o build e reverifique antes de delegar. Rode `npx ngc --noEmit -p <lib>/tsconfig.lib.json`:"+sys.argv[1]},"systemMessage":"⛔ route-a-guard: base nao compila (ngc) — dispatch bloqueado"}))' "$ngcmsg"
  exit 0
fi

WINDOW=300
now=$(date +%s)
state="${TMPDIR:-/tmp}/claude-routea-${sid}"
first=0; count=0
[ -f "$state" ] && read -r first count < "$state"
[ -n "$count" ] || count=0
[ -n "$first" ] || first=0

# Reinicia a contagem se a janela expirou.
if [ $((now - first)) -gt "$WINDOW" ]; then first=$now; count=0; fi
count=$((count + 1))
printf '%s %s\n' "$first" "$count" > "$state"

if [ "$count" -ge 3 ]; then
  printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Enxame de subagentes concorrentes sobre a mesma working tree (3o+ spawn na janela) e PROIBIDO — plan-generation D3. Foi a topologia que estourou ~30x o custo e causou git-stash near-miss num incidente real; e, medido na rodada k=3, o braco de 3 subagentes paralelos foi o mais caro dos 13. Um agente read-only tudo bem; fan-out de ESCRITA -> UM subagente por lote, EM SERIE, e voce verifica o diff. Ver ~/.claude/skills/plan-generation/SKILL.md secao D3."},"systemMessage":"⛔ route-a-guard: 3o subagente concorrente bloqueado"}'
  exit 0
fi

if [ "$count" -eq 2 ]; then
  python3 -c '
import json
ctx = ("2o subagente na mesma janela sob o plano ativo. Se este e read-only (mapear/explorar), ok. "
       "Se e fan-out de ESCRITA, PARE: plan-generation D3 manda UM subagente por lote, EM SERIE, "
       "com voce verificando o diff — nunca agentes paralelos sobre a mesma working tree. "
       "E confira o break-even antes de delegar de novo: tokens_poupados x calls_restantes > 400000.")
print(json.dumps({
  "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": ctx},
  "systemMessage": "⚠ route-a-guard: 2o subagente sob rota (a)"
}))'
fi
exit 0
