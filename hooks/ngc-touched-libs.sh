#!/usr/bin/env bash
# Compartilhado (stop-check + route-a-guard): computa erros de compilacao (ngc)
# nas libs que ESTA sessao REALMENTE ALTEROU NO DISCO.
#
# Entrada: payload de hook (JSON) no stdin — precisa conter `transcript_path`.
# Saida:   o bloco "[lib]\n  <erros>" para todo .ts tocado pela sessao que falha
#          `ngc --noEmit`; NADA quando os arquivos tocados compilam limpo.
#          Sempre sai 0 — quem chama decide como apresentar um resultado nao-vazio.
#
# Escopo (identico ao stop-check original): "realmente alterou" = aparece em
# `git diff` (working tree), `git diff --cached` ou como untracked. Arquivo que a
# sessao abriu mas cujo resultado voltou ao HEAD NAO conta — o build real nao ve
# mudanca, entao o gate tambem nao deve. Erro pre-existente em irmao/codigo-morto
# que a sessao NAO tocou e ignorado (o esbuild do app tambem o ignora por tree-shaking).
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0

input=$(cat 2>/dev/null)

# Arquivos .ts editados nesta sessao, derivados do transcript_path do payload.
# Usados so para RESTRINGIR o pathspec do git (nao varrer a arvore suja inteira).
# Exclui .claude/evals (artefatos de avaliacao onde 'any'/quebras sao proposital).
# O payload vai por ENV (HOOK_PAYLOAD), nao por stdin: `python3 - <<'PY'` le o
# PROGRAMA do heredoc pelo stdin; um pipe no lugar seria sobrescrito pelo heredoc.
files=$(HOOK_PAYLOAD="$input" python3 - <<'PY'
import json,os,sys
try:
    payload=json.loads(os.environ.get("HOOK_PAYLOAD",""))
    tp=payload.get("transcript_path")
except Exception:
    sys.exit(0)
if not tp:
    sys.exit(0)
seen=[]
try:
    for line in open(tp):
        try: o=json.loads(line)
        except Exception: continue
        msg=o.get("message",o)
        cont=msg.get("content") if isinstance(msg,dict) else None
        if not isinstance(cont,list): continue
        for b in cont:
            if not (isinstance(b,dict) and b.get("type")=="tool_use"): continue
            if b.get("name") not in ("Edit","Write","MultiEdit"): continue
            fp=(b.get("input") or {}).get("file_path")
            if not (isinstance(fp,str) and fp.endswith(".ts")): continue
            if ".claude/evals" in fp: continue
            if fp not in seen: seen.append(fp)
except Exception:
    sys.exit(0)
print("\n".join(seen))
PY
)

# Nenhum .ts tocado nesta sessao -> nada a checar.
[ -z "$files" ] && exit 0

# Caminhos relativos ao repo, para casar com pathspec do git.
mapfile -t paths < <(printf '%s\n' "$files" | sed -E "s#^$PWD/##")

# Interseccao com o que MUDOU NO DISCO: modificado, staged, ou untracked.
mapfile -t changed < <(
  {
    git diff --name-only -- "${paths[@]}"
    git diff --cached --name-only -- "${paths[@]}"
    git ls-files --others --exclude-standard -- "${paths[@]}"
  } 2>/dev/null | awk 'NF' | sort -u
)

# Nada mudou de fato no disco -> nada a bloquear.
[ ${#changed[@]} -eq 0 ] && exit 0

# ngc — reporta erro cujo arquivo esta no conjunto `changed`. ngc imprime paths
# relativos ao dir da lib: arquivos DA lib comecam com 'src/'; dependencias
# quebradas pre-existentes comecam com '../' e sao RUIDO (filtro `^src/`). Casa o
# proprio .ts e o .html pareado (erros de template saem atribuidos ao .html).
# ANSI stripado antes (ngc emite escape entre "error" e "TS" mesmo com --pretty false).
libs=$(printf '%s\n' "${changed[@]}" | grep -E '^libs/' | sed -E 's#^(libs/[^/]+/[^/]+/[^/]+)/.*#\1#' | sort -u)
ngcmsg=""
for lib in $libs; do
  ts="$lib/tsconfig.lib.json"; [ -f "$ts" ] || continue
  rel=$(printf '%s\n' "${changed[@]}" | grep -F "$lib/" | sed -E "s#^$lib/##")
  [ -z "$rel" ] && continue
  needles=$(printf '%s\n' "$rel" | while IFS= read -r r; do
    [ -n "$r" ] && printf '%s:\n%s.html:\n' "$r" "${r%.ts}"
  done)
  clean=$(npx ngc --noEmit -p "$ts" 2>&1 | sed -r 's/\x1b\[[0-9;]*m//g')
  m=$(printf '%s\n' "$clean" \
    | grep -E '^src/.*\.(ts|html):[0-9]+.*error (TS|NG)-?[0-9]+' \
    | grep -F -f <(printf '%s\n' "$needles") \
    | sed 's/^/  /' | head -10)
  [ -n "$m" ] && ngcmsg="$ngcmsg"$'\n'"[$lib]"$'\n'"$m"
done

printf '%s' "$ngcmsg"
exit 0
