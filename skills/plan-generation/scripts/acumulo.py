"""Freio de acúmulo: avisa quando uma saída de ferramenta incha a janela (D6, regra de leitura).

Nas 19 sessões reais com a plan-generation (medido em 2026-10-14), ler arquivo — `Read` mais
`cat`/`sed -n` pelo Bash — respondeu por ~58% do crescimento da janela depois da invocação, e o
`ExitPlanMode` devolveu em média ~7 mil caracteres por chamada. Nudge: avisa uma vez por ferramenta
por sessão, nunca bloqueia.
"""
from __future__ import annotations

import importlib
import json

import contexto

LIMITE_TOKENS = 6000
LIMITE_EXIT_PLAN = 1500

REMEDIO = {
    "Read": "ache a linha com `Grep -n` e leia só a faixa com `offset`/`limit`.",
    "Bash": "redirecione a saída para arquivo e leia o recorte (`cmd > \"$TMP/saida.log\" 2>&1; "
            "tail -n 40 \"$TMP/saida.log\"`, ou `grep -n`). Para ler código, `grep -n` e depois "
            "`sed -n 'A,Bp'` numa faixa curta — nunca `cat` do arquivo inteiro.",
    "PowerShell": "redirecione a saída para arquivo e leia o recorte com `Select-String` ou "
                  "`Get-Content -Tail 40`.",
    "Grep": "peça `files_with_matches` ou um `head_limit` antes de pedir o conteúdo.",
}


def tokens_da_resposta(payload: dict) -> int:
    resposta = payload.get("tool_response")
    if resposta is None:
        return 0
    bruto = resposta if isinstance(resposta, str) else json.dumps(resposta, ensure_ascii=False)
    return contexto.tokens_de_bytes(len(bruto.encode("utf-8")))


def _restantes(estado: dict, plano) -> int | None:
    if plano is None:
        return None
    try:
        return importlib.import_module("checkpoint").calls_restantes(estado, plano)
    except (ImportError, AttributeError):
        return None


def avaliar(payload: dict, estado: dict, medida, plano) -> list[tuple[str, str, str]]:
    ferramenta = payload.get("tool_name") or ""
    if ferramenta == "ExitPlanMode":
        texto = str((payload.get("tool_input") or {}).get("plan") or "")
        if len(texto) <= LIMITE_EXIT_PLAN:
            return []
        return [(
            "acumulo-exitplan",
            f"O ExitPlanMode recebeu {len(texto)} caracteres, e o texto volta inteiro no resultado, que "
            "fica na janela até o fim da sessão. O plano já está no arquivo: mande só o resumo — o que "
            f"muda, as decisões em uma linha cada e o caminho do .md —, até {LIMITE_EXIT_PLAN} caracteres.",
            f"ExitPlanMode com {len(texto)} caracteres (limite {LIMITE_EXIT_PLAN})",
        )]
    if ferramenta not in REMEDIO:
        return []
    tokens = tokens_da_resposta(payload)
    if tokens < LIMITE_TOKENS:
        return []
    restantes = _restantes(estado, plano)
    projecao = (f" — com ~{restantes} chamadas restantes no plano, são ~{contexto.kilo(tokens * restantes)} "
                "tokens de releitura") if restantes else ""
    return [(
        f"acumulo-{ferramenta}",
        f"Esta saída de {ferramenta} pôs ~{tokens} tokens na janela, e cada chamada seguinte os relê"
        f"{projecao}. Daqui em diante: {REMEDIO[ferramenta]}",
        f"saída de {ferramenta} com ~{contexto.kilo(tokens)} tokens",
    )]
