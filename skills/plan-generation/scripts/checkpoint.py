"""Decide se compensa limpar a janela num limite de passo (D6 da plan-generation).

Chamado pelo `guard.py` quando a sessão vincula o plano (checkpoint de entrada, antes de executar)
e quando edita o plano (o `## Estado` muda ao fechar um passo). A conta e a origem de cada termo
estão em `references/contexto.md`.
"""
from __future__ import annotations

import importlib
import os

import contexto


def calls_restantes(estado: dict, plano) -> int | None:
    """Chamadas que ainda faltam, pela taxa real da sessão; None se o plano já fechou ou não diz.

    Com pelo menos um passo fechado NESTA sessão, extrapola a taxa observada (calls por passo) para os
    passos que faltam — é melhor que a D0, que no único par medido errou 3×. Sem passo fechado, usa o
    que sobra da `D0_exec`.
    """
    feitas = max(0, estado.get("calls", 0) - estado.get("calls_no_vinculo", 0))
    if plano.passos:
        fechados, total = plano.passos
        if total <= fechados:
            return None
        antes = (estado.get("passos_no_vinculo") or [0])[0]
        aqui = fechados - antes
        if aqui >= 1 and feitas > 0:
            return round(feitas / aqui * (total - fechados))
    if plano.d0_exec is not None:
        return max(plano.d0_exec - feitas, 0)
    return None


def raiz_do_plano(caminho: str) -> str:
    norm = caminho.replace("\\", "/")
    return norm.split("/.claude/plans/")[0] if "/.claude/plans/" in norm else os.path.dirname(norm)


def tokens_para_restabelecer(plano) -> int:
    """O que a sessão nova precisa reler: o plano e os arquivos-alvo que existem em disco."""
    raizes = [raiz_do_plano(plano.caminho), os.environ.get("CLAUDE_PROJECT_DIR", "")]
    total = contexto.tokens_de_arquivo(plano.caminho)
    for alvo in plano.alvos:
        candidatos = [alvo] if os.path.isabs(alvo) else [os.path.join(r, alvo) for r in raizes if r]
        total += next((contexto.tokens_de_arquivo(c) for c in candidatos if os.path.isfile(c)), 0)
    return total


def fracao_da_base_reescrita() -> tuple[float, str]:
    """Quanto da base o cache perde no /clear: medido pela calibração (015) ou 1,0 (conservador)."""
    try:
        calibracao = importlib.import_module("calibracao")
        medida = calibracao.fracao_base_reescrita()
    except (ImportError, AttributeError):
        medida = None
    if medida is None:
        return 1.0, "conservador: base inteira, até a calibração medir"
    return medida, "medido pela calibração"


def avaliar(estado: dict, medida: contexto.Medida, plano) -> list[tuple[str, str, str]]:
    restantes = calls_restantes(estado, plano)
    if not restantes:
        return []
    fechados = plano.passos[0] if plano.passos else 0
    r = tokens_para_restabelecer(plano)
    fracao, origem = fracao_da_base_reescrita()
    b = round(medida.base * fracao)
    k = contexto.razao_escrita_leitura(medida)
    ganho = (medida.excedente - r) * restantes
    custo = round(k * (r + b))
    conta = {"passo": fechados, "excedente": medida.excedente, "restabelecer": r, "base_reescrita": b,
             "razao": round(k, 1), "restantes": restantes, "ganho": ganho, "custo": custo}
    estado.setdefault("contas", []).append(conta)
    if ganho <= custo:
        return []
    estado["checkpoints_recomendados"] = estado.get("checkpoints_recomendados", 0) + 1
    quando = "antes de executar" if fechados == 0 else f"passo {fechados} de {plano.passos[1]} fechado"
    k_ = contexto.kilo
    ctx = (
        f"CHECKPOINT COMPENSA ({quando}). Conta da D6: (excedente {medida.excedente} − restabelecer {r}) "
        f"× ~{restantes} chamadas restantes = {ganho} > {k:.0f} × (restabelecer {r} + base reescrita {b}) "
        f"= {custo}. Base reescrita: {origem}. Antes do próximo passo: (1) atualize o `## Estado` do plano "
        "pelo `templates/checkpoint.md`; (2) pare e devolva ao usuário com a frase "
        f"\"Checkpoint gravado. Rode /clear e depois /plan-generation retomar {plano.slug}\". Seguir nesta "
        f"janela relê {k_(medida.excedente)} tokens a cada chamada, e o plano já guarda o que eles carregam."
    )
    usuario = (f"checkpoint compensa — /clear e /plan-generation retomar {plano.slug} "
               f"(excedente {k_(medida.excedente)}, ~{restantes} calls restantes)")
    return [(f"checkpoint-{fechados}", ctx, usuario)]
