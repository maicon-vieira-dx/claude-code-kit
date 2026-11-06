#!/usr/bin/env bash
# Stop: (1) bloqueia se 'any' foi introduzido em .ts; (2) recurso de componente ausente;
#       (3) advisory ngc — BLOQUEIA compilacao quebrada.
# Escopo: SO os arquivos .ts que ESTA sessao REALMENTE ALTEROU NO DISCO.
# "Realmente alterou" = aparece em `git diff` (working tree), `git diff --cached` ou como
# untracked. Um arquivo que a sessao abriu com Edit mas cujo resultado voltou ao HEAD
# (edicoes que se cancelaram, ou revertidas pelo usuario) NAO conta — o build real nao ve
# mudanca nele, entao o hook tambem nao deve.
#
# Classe: STOP DE COMPILACAO. Aqui silencio NAO e verde. Quando um checker nao
# esta disponivel, este hook BLOQUEIA dizendo que nao pode atestar — antes, um
# checker ausente produzia string vazia, indistinguivel de "compilou".
# O bloqueio por checker ausente acontece UMA vez por sessao: repetido a cada
# Stop viraria laco (o Stop re-invoca o modelo), entao da segunda em diante ele
# vira aviso. Ver o precedente `project_stop-check-hook-was-dead`.
MARCA_ATESTE="${TMPDIR:-/tmp}/claude-stopcheck-noattest"

nao_posso_atestar() {
  # $1 = lista do que falta
  if [ -f "$MARCA_ATESTE" ]; then
    printf '%s\n' "{\"systemMessage\":\"⚠ stop-check: segue sem poder atestar compilacao — $(printf '%s' "$1" | tr '\n' ' ')\"}"
    exit 0
  fi
  : > "$MARCA_ATESTE" 2>/dev/null
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import json,sys; print(json.dumps({"decision":"block","reason":"stop-check: checker ausente, nao posso atestar que o que esta sessao alterou compila. Silencio aqui nao e verde. Faltando:"+sys.argv[1]+"\nRode `npx ngc --noEmit -p <lib>/tsconfig.lib.json` na lib tocada, ou restaure o checker. Este bloqueio so acontece uma vez por sessao."}))' "$1"
  else
    printf '%s\n' '{"decision":"block","reason":"stop-check: nem o interpretador python3 esta disponivel, entao nenhuma checagem rodou — nao posso atestar que o que esta sessao alterou compila. Rode `npx ngc --noEmit -p <lib>/tsconfig.lib.json` na lib tocada. Este bloqueio so acontece uma vez por sessao."}'
  fi
  exit 0
}

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || nao_posso_atestar $'\n  - nao consegui entrar no diretorio do projeto (CLAUDE_PROJECT_DIR)'

input=$(cat 2>/dev/null)
# BOM UTF-8 antes do JSON quebra o parse e as checagens viram vazio = falso verde.
input="${input#$'\xef\xbb\xbf'}"

# Inventario dos checkers ANTES de qualquer saida antecipada.
faltando=""
command -v python3 >/dev/null 2>&1 || faltando="$faltando"$'\n''  - interpretador python3 nao encontrado no PATH'
[ -f "${HOME}/.claude/hooks/ngtsc_template_check.py" ] || faltando="$faltando"$'\n''  - ngtsc_template_check.py (checagem de template Angular)'
[ -f "${HOME}/.claude/hooks/ngc-touched-libs.sh" ] || faltando="$faltando"$'\n''  - ngc-touched-libs.sh (compilacao das libs tocadas)'
[ -n "$input" ] || faltando="$faltando"$'\n''  - payload do Stop (stdin vazio): sem ele nao da para saber o que a sessao alterou'
[ -n "$faltando" ] && nao_posso_atestar "$faltando"

# (0) Template Angular (NG*) — BLOQUEANTE, delegado ao checker Python.
# Independente do resto porque cobre dois pontos cegos das checagens abaixo:
#   a) elas so coletam .ts do transcript, e erro de template mora no .html — sessao que
#      so editou template saia pelas saidas antecipadas sem checagem alguma;
#   b) o ngc do passo (3) NUNCA chega na fase de template enquanto as libs legadas
#      do monorepo tiverem erro TS pre-existente.
# O checker fala com o NgCompiler arquivo a arquivo, entao esse ruido nao o afeta.
# Checker que roda e MORRE (exit != 0) vale o mesmo que checker ausente: nao houve
# ateste. Antes o `2>/dev/null` transformava crash em string vazia, ou seja, em
# "compilou". O canal e ARQUIVO, nao variavel: `msg=$(tpl_check)` roda em subshell
# e uma variavel setada la dentro nunca chegaria aqui.
FALHA_FILE="${TMPDIR:-/tmp}/claude-stopcheck-fail.$$"
rm -f "$FALHA_FILE"
trap 'rm -f "$FALHA_FILE"' EXIT

tpl_check() {
  local out rc
  out=$(printf '%s' "$input" | python3 "${HOME}/.claude/hooks/ngtsc_template_check.py" 2>&1)
  rc=$?
  if [ "$rc" -ne 0 ]; then
    printf '  - ngtsc_template_check.py saiu com %s: %s\n' \
      "$rc" "$(printf '%s' "$out" | tail -2 | tr '\n' ' ')" >> "$FALHA_FILE"
    return 0
  fi
  printf '%s' "$out"
}

checkers_falharam() { [ -s "$FALHA_FILE" ] && cat "$FALHA_FILE"; }

# Usado no lugar das saidas antecipadas: elas nao podem pular a checagem de template.
tpl_check_then_exit() {
  local msg falhas
  msg=$(tpl_check)
  falhas=$(checkers_falharam)
  [ -n "$falhas" ] && nao_posso_atestar $'\n'"$falhas"
  if [ -n "$msg" ]; then
    python3 -c 'import json,sys; print(json.dumps({"decision":"block","reason":"Erro de template Angular em arquivo que esta sessao alterou — `nx serve`/`ngc` falharia com \"Application bundle generation failed\". Corrija antes de finalizar:\n"+sys.argv[1]}))' "$msg"
  fi
  exit 0
}

# Arquivos .ts editados nesta sessao, derivados do transcript_path do payload do Stop hook.
# Usados apenas para RESTRINGIR o pathspec do git (nao varrer a arvore suja inteira).
# Exclui .claude/evals (artefatos de avaliacao onde 'any' e proposital).
# IMPORTANTE: o payload vai por ENV (STOP_PAYLOAD), nao por stdin. `python3 - <<'PY'`
# le o PROGRAMA do heredoc (stdin); um `printf | python3 - <<PY` faria o heredoc
# sobrescrever o pipe, deixando `json.load(sys.stdin)` sempre vazio — bug que mantinha
# este hook inteiro morto (files sempre vazio -> exit na linha "[ -z "$files" ]").
files=$(STOP_PAYLOAD="$input" python3 - <<'PY'
import json,os,sys
try:
    payload=json.loads(os.environ.get("STOP_PAYLOAD",""))
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

# Nenhum .ts tocado nesta sessao -> so resta a checagem de template (pode haver .html).
[ -z "$files" ] && tpl_check_then_exit

# Caminhos relativos ao repo, para casar com pathspec do git.
mapfile -t paths < <(printf '%s\n' "$files" | sed -E "s#^$PWD/##")

# Interseccao com o que MUDOU NO DISCO: modificado (working tree), staged, ou untracked.
# Edicoes que voltaram ao HEAD somem daqui. Isto elimina o falso-positivo classico:
# ngc -p tsconfig.lib.json compila TODOS os arquivos da lib (incl. codigo morto que o
# esbuild do app remove por tree-shaking); reportar erro em arquivo que a sessao nao
# alterou = bloquear por quebra pre-existente que o build real nem enxerga.
mapfile -t changed < <(
  {
    git diff --name-only -- "${paths[@]}"
    git diff --cached --name-only -- "${paths[@]}"
    git ls-files --others --exclude-standard -- "${paths[@]}"
  } 2>/dev/null | awk 'NF' | sort -u
)

# Nenhum .ts mudou no disco -> so resta a checagem de template (pode haver .html).
[ ${#changed[@]} -eq 0 ] && tpl_check_then_exit

# (1) ban any — bloqueante. So nas linhas adicionadas dos arquivos alterados da sessao.
diff=$( { git diff -U0 -- "${changed[@]}"; git diff --cached -U0 -- "${changed[@]}"; } 2>/dev/null )
hits=$(printf '%s\n' "$diff" | grep -E '^\+' | grep -vE '^\+\+\+' | grep -E ':[[:space:]]*any\b|<any>|as[[:space:]]+any\b')
if [ -n "$hits" ]; then
  printf '%s\n' '{"decision":"block","reason":"Introduziu \"any\" em arquivo .ts (proibido — ver .claude/rules/typing.md). Criar *ApiDto e mapear para o domínio antes de finalizar."}'
  exit 0
fi

# (2) Recursos de componente ausentes (templateUrl/styleUrl(s)) — BLOQUEANTE.
# O build esbuild do app falha com "Could not resolve <arquivo>.css", mas
# `ngc --noEmit` NAO resolve recursos — esse erro passava batido. Checagem barata e
# deterministica: para cada *.component.ts ALTERADO, todo caminho em templateUrl e
# styleUrl(s) precisa existir relativo ao dir do componente.
resmsg=$(STOP_FILES="$(printf '%s\n' "${changed[@]}")" python3 - <<'PY'
import os, re
files=[f for f in os.environ.get("STOP_FILES","").splitlines() if f.endswith(".component.ts")]
miss=[]
for f in files:
    try: src=open(f).read()
    except Exception: continue
    d=os.path.dirname(f)
    for m in re.finditer(r"templateUrl\s*:\s*['\"]([^'\"]+)['\"]", src):
        if not os.path.isfile(os.path.normpath(os.path.join(d,m.group(1)))):
            miss.append(f"  {f}: templateUrl -> {m.group(1)} (nao existe)")
    for m in re.finditer(r"styleUrls?\s*:\s*(\[[^\]]*\]|['\"][^'\"]+['\"])", src):
        for u in re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)):
            if not os.path.isfile(os.path.normpath(os.path.join(d,u))):
                miss.append(f"  {f}: styleUrl -> {u} (nao existe)")
print("\n".join(miss))
PY
)

# (3) ngc — BLOQUEIA se um arquivo ALTERADO por esta sessao nao compila (TS/template).
# Delegado ao script compartilhado (fonte de verdade unica, tambem usado pelo
# route-a-guard para nao despachar subagente sobre base quebrada). Ele rederiva
# files/changed do mesmo payload e roda ngc so nas libs tocadas, filtrando ruido de
# codigo-morto/dependencia pre-existente. LIMITE CONHECIDO herdado: template-check
# (NG8001) e recursos nao saem no ngc enquanto libs de dependencia tiverem erros TS
# pre-existentes — a checagem (2) cobre o subcaso de recurso ausente.
ngcmsg=$(printf '%s' "$input" | bash "${HOME}/.claude/hooks/ngc-touched-libs.sh" 2>&1)
ngcrc=$?
if [ "$ngcrc" -ne 0 ]; then
  printf '  - ngc-touched-libs.sh saiu com %s: %s\n' \
    "$ngcrc" "$(printf '%s' "$ngcmsg" | tail -2 | tr '\n' ' ')" >> "$FALHA_FILE"
  ngcmsg=""
fi

# (4) Template Angular — o que o ngc do passo (3) nao alcanca (ver comentario em (0)).
tplmsg=$(tpl_check)

# Checker que morreu em execucao vale o mesmo que checker ausente: nao houve ateste.
falhas=$(checkers_falharam)
[ -n "$falhas" ] && nao_posso_atestar $'\n'"$falhas"

blockmsg=""
[ -n "$resmsg" ] && blockmsg="$blockmsg"$'\n'"Recurso de componente ausente (templateUrl/styleUrl):"$'\n'"$resmsg"
[ -n "$ngcmsg" ] && blockmsg="$blockmsg"$'\n'"Erro de compilacao (ngc) em arquivo da lib editada:"$'\n'"$ngcmsg"
[ -n "$tplmsg" ] && blockmsg="$blockmsg"$'\n'"Erro de template Angular (NG*/TS em .html):"$'\n'"$tplmsg"

if [ -n "$blockmsg" ]; then
  python3 -c 'import json,sys; print(json.dumps({"decision":"block","reason":"Build quebrado em arquivo(s) que esta sessao alterou — corrija antes de finalizar. Rode `npx ngc --noEmit -p <lib>/tsconfig.lib.json` e confira templateUrl/styleUrl:"+sys.argv[1]}))' "$blockmsg"
  exit 0
fi
exit 0
