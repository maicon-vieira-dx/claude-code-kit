"""Apoio dos testes: transcripts e planos sintéticos, e o guard rodando como subprocesso."""
from __future__ import annotations

import json
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(RAIZ, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


def chamada(ctx: int, lido: int = 0, w1h: int = 0, w5: int = 0, out: int = 10, modelo: str = "claude-sonnet-5-5", **extra) -> dict:
    return {"ctx": ctx, "lido": lido, "w1h": w1h, "w5": w5, "out": out, "modelo": modelo, **extra}


def escrever_transcript(caminho: str, chamadas: list[dict]) -> str:
    with open(caminho, "w", encoding="utf-8") as fh:
        for i, c in enumerate(chamadas):
            usage = {
                "input_tokens": c["ctx"] - c["lido"] - c["w1h"] - c["w5"],
                "cache_read_input_tokens": c["lido"],
                "cache_creation": {"ephemeral_5m_input_tokens": c["w5"], "ephemeral_1h_input_tokens": c["w1h"]},
                "output_tokens": c["out"],
            }
            linha = {
                "type": "assistant",
                "isSidechain": c.get("sidechain", False),
                "message": {"id": c.get("id", f"msg_{i}"), "model": c["modelo"], "usage": usage},
            }
            fh.write(json.dumps(linha) + "\n")
            if c.get("duplicada"):
                fh.write(json.dumps(linha) + "\n")
    return caminho


def texto_de_plano(d3: str = "eu, mesma janela", d0: str = "~40 tool calls no total (execução: ~25 · já gastas: ~15)",
                   regime: str = "fora — 2 libs, TDD sim, D0_exec 25. Solo por preferência.",
                   alvos: tuple[str, ...] = ("alvo.ts",), passos: str | None = None) -> str:
    linhas = [
        "# Plano: teste",
        "",
        "## Decisões de execução",
        f"- **D0 — Orçamento:** {d0}",
        f"- **D3 executor:** {d3}",
        f"  - **Regime:** {regime}",
        "",
        "## Arquivos-alvo",
        *[f"- `{a}` — muda" for a in alvos],
    ]
    if passos:
        linhas += ["", "## Estado (atualizar a cada passo fechado)", f"- **Passos fechados:** {passos}"]
    return "\n".join(linhas) + "\n"


def escrever_plano(raiz: str, nome: str = "teste.md", **kw) -> str:
    pasta = os.path.join(raiz, ".claude", "plans")
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, nome)
    with open(caminho, "w", encoding="utf-8") as fh:
        fh.write(texto_de_plano(**kw))
    return caminho


def rodar_guard(payload: dict | str, tmp: str, extra_env: dict | None = None) -> tuple[int, str]:
    """Roda `scripts/guard.py` como o Claude Code roda: JSON no stdin, stdout capturado em bytes.

    O ambiente sai sem PYTHONUTF8/PYTHONIOENCODING de propósito: é nesse ambiente que o stdout do
    Windows vira cp1252, e é ali que o deny do budget-guard morria.
    """
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    env.update(TMPDIR=tmp, TEMP=tmp, PLANGEN_LEDGER=os.path.join(tmp, "livro.tsv"))
    env.update(extra_env or {})
    dado = payload if isinstance(payload, str) else json.dumps(payload)
    proc = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "guard.py")],
        input=dado.encode("utf-8"),
        capture_output=True,
        env=env,
        timeout=30,
    )
    return proc.returncode, proc.stdout.decode("ascii", "strict").strip()
