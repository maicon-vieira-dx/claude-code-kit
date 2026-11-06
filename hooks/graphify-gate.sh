#!/usr/bin/env bash
# PreToolUse (Bash|Grep|Glob): gate de busca em libs/ por LIMITE de ocorrencias.
#   - Busca pontual (<= GRAPHIFY_GREP_MAX, default 20): liberada.
#   - Busca exploratoria (> limite): negada, forca graphify-search.
#   - grep que so filtra stdin de pipe (ex.: `ngc -p libs/... | grep X`): liberado.
# A logica de contagem/decisao vive em graphify-gate.py (evita escape de aspas).
#
# Classe: DENY-GATE DE ESCOPO — polaridade DUAL, e os dois caminhos vao para
# lados opostos de proposito:
#   - interpretador morto / payload ilegivel -> LIBERA (com aviso). Este gate
#     protege orcamento de contexto, nao dado: negar toda busca por causa de um
#     payload quebrado custa mais que a busca ampla que escapa.
#   - contagem de ocorrencias que nao parseia -> NEGA (dentro do .py). Ali o gate
#     SABE que e busca em libs/ e so nao sabe o tamanho; liberar seria assumir
#     "pequena" justamente no caso que ele existe para pegar.
# O que NAO existe mais e o terceiro caminho: falhar em silencio.
# Ver .claude/rules/libs-graphify.md.
input=$(cat)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$SCRIPT_DIR/graphify-gate.py"

if ! command -v python3 >/dev/null 2>&1 || [ ! -f "$PY" ]; then
  printf '%s\n' '{"systemMessage":"⚠ graphify-gate: sem interpretador — busca em libs/ liberada sem atestar. Use graphify-search se for varredura ampla."}'
  exit 0
fi

printf '%s' "$input" | GRAPHIFY_GREP_MAX="${GRAPHIFY_GREP_MAX:-20}" python3 "$PY"
exit 0
