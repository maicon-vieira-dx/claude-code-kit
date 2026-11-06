"""Livro de calibração da plan-generation: previsto × real por plano, e o custo real do /clear.

O `guard.py` chama `registrar()` no Stop de cada turno de uma sessão com plano vinculado; a linha da
sessão é sobrescrita, então o livro guarda o último estado de cada sessão. Duas perguntas que só
dados respondem saem daqui:

- a D0 acerta? (`--plano`: a linha `D0: previsto N / real M` que a Fase 5 grava no plano);
- quanto da base o cache perde num /clear? (`fracao_base_reescrita()`, que o `checkpoint.py` usa no
  lugar do 1,0 conservador quando há pelo menos 3 retomadas medidas).

Uso: python3 calibracao.py --plano <caminho-do-plano> | --resumo
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics
import sys
from datetime import datetime

COLUNAS = ["atualizado_em", "sessao", "plano", "retomada", "d0_exec", "d0_total", "calls", "base",
           "ctx_inv", "sujo_inicial", "pico", "atual", "releitura", "escrita_primeira",
           "checkpoints_recomendados"]
MINIMO_DE_RETOMADAS = 3


def caminho_do_livro() -> str:
    return os.environ.get("PLANGEN_LEDGER") or os.path.expanduser(
        "~/.claude/evals/evolution/calibracao-plan-generation.tsv")


def ler() -> list[dict]:
    try:
        with open(caminho_do_livro(), encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh, delimiter="\t"))
    except OSError:
        return []


def _gravar(linhas: list[dict]) -> None:
    destino = caminho_do_livro()
    if not os.path.isdir(os.path.dirname(destino)):
        return
    tmp = destino + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUNAS, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)
    os.replace(tmp, destino)


def registrar(sid: str, estado: dict, medida, plano) -> None:
    """Sobrescreve a linha da sessão com o estado atual. Retomada = o plano entrou pela leitura."""
    linha = {
        "atualizado_em": datetime.now().isoformat(timespec="seconds"),
        "sessao": sid,
        "plano": plano.caminho.replace("\\", "/"),
        "retomada": 1 if estado.get("vinculado_por") == "leitura" else 0,
        "d0_exec": plano.d0_exec if plano.d0_exec is not None else "",
        "d0_total": plano.d0_total if plano.d0_total is not None else "",
        "calls": estado.get("calls", 0),
        "base": medida.base,
        "ctx_inv": estado.get("ctx_inv", 0),
        "sujo_inicial": max(0, estado.get("ctx_inv", 0) - medida.base),
        "pico": medida.pico,
        "atual": medida.atual,
        "releitura": medida.releitura_total - estado.get("releitura_inv", 0),
        "escrita_primeira": medida.escrita_primeira,
        "checkpoints_recomendados": estado.get("checkpoints_recomendados", 0),
    }
    linhas = [r for r in ler() if r.get("sessao") != sid] + [linha]
    try:
        _gravar(linhas)
    except OSError:
        pass


def _int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def fracao_base_reescrita() -> float | None:
    """Mediana de escrita_primeira ÷ base nas retomadas; None com menos de 3 medidas.

    Superestima de propósito: a primeira chamada da sessão nova também escreve o pedido de retomada
    e o corpo da skill. Superestimar a fração encarece o /clear na conta, nunca o barateia.
    """
    fracoes = [min(1.0, _int(r["escrita_primeira"]) / _int(r["base"]))
               for r in ler() if r.get("retomada") == "1" and (_int(r.get("base")) or 0) > 0
               and _int(r.get("escrita_primeira")) is not None]
    return statistics.median(fracoes) if len(fracoes) >= MINIMO_DE_RETOMADAS else None


def linha_d0_do_plano(caminho: str) -> str | None:
    """A linha que a Fase 5 grava no plano, somando as chamadas de todas as sessões dele."""
    alvo = caminho.replace("\\", "/")
    linhas = [r for r in ler() if r.get("plano") == alvo]
    if not linhas:
        return None
    ultima = linhas[-1]
    real = sum(_int(r["calls"]) or 0 for r in linhas)
    previsto = ultima.get("d0_total") or "?"
    return (f"D0: previsto {previsto} / real {real} (execução prevista {ultima.get('d0_exec') or '?'}; "
            f"{len(linhas)} sessão(ões); contexto na invocação {ultima['ctx_inv']}, base {ultima['base']}, "
            f"pico {ultima['pico']}; checkpoints recomendados "
            f"{sum(_int(r['checkpoints_recomendados']) or 0 for r in linhas)})")


def resumo() -> str:
    linhas = ler()
    planos: dict[str, list[dict]] = {}
    for r in linhas:
        planos.setdefault(r["plano"], []).append(r)
    razoes = []
    for rs in planos.values():
        previsto = _int(rs[-1].get("d0_total"))
        if previsto:
            razoes.append(sum(_int(r["calls"]) or 0 for r in rs) / previsto)
    fracao = fracao_base_reescrita()
    retomadas = sum(1 for r in linhas if r.get("retomada") == "1")
    return "\n".join([
        f"sessões: {len(linhas)} · planos: {len(planos)} · retomadas: {retomadas}",
        f"real ÷ previsto (D0_total), mediana: {statistics.median(razoes):.2f} (n={len(razoes)})" if razoes
        else "real ÷ previsto: sem plano com D0_total",
        f"fração da base reescrita no /clear, mediana: {fracao:.2f}" if fracao is not None
        else f"fração da base reescrita: menos de {MINIMO_DE_RETOMADAS} retomadas — checkpoint usa 1,0",
    ])


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    grupo = ap.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--plano")
    grupo.add_argument("--resumo", action="store_true")
    args = ap.parse_args(argv)
    if args.resumo:
        print(resumo())
        return 0
    linha = linha_d0_do_plano(args.plano)
    if linha is None:
        print(f"sem registro para {args.plano} (o Stop grava ao fim de cada turno com plano vinculado)")
        return 1
    print(linha)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
