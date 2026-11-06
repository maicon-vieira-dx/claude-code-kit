"""Mede o contexto da sessão a partir do transcript JSONL do Claude Code.

Biblioteca sem estado: `guard.py` e os módulos opcionais (`checkpoint.py`, `acumulo.py`,
`calibracao.py`) importam daqui. "Contexto" é sempre o tamanho do prompt de UMA chamada à API —
input novo + cache lido + cache escrito —, que é o que a chamada seguinte relê.

Uso direto: python3 contexto.py <transcript.jsonl> | --ultimo [<pasta-do-projeto>]
(`--ultimo` mede o transcript mais recente do projeto, que é o da sessão que está rodando.)
"""
from __future__ import annotations

import glob
import importlib.util
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from types import ModuleType

# Medido em 2026-10-14: 16 invocações reais da plan-generation, corpo injetado (bytes) ÷ salto de
# contexto (tokens) = 2,08–2,95, mediana 2,35. Texto em português com markdown; não vale para código.
BYTES_POR_TOKEN = 2.35

# Escrever no cache ÷ ler do cache, para quando a tarifa do modelo é desconhecida. 20 é a razão do
# TTL de 1 h na regra geral (2× o input ÷ 0,1× o input).
RAZAO_PADRAO = 20.0

TURN_COST = os.path.expanduser("~/.claude/hooks/turn-cost.py")


@dataclass(frozen=True)
class Medida:
    """Contexto da sessão no instante da leitura, em tokens."""

    base: int
    atual: int
    pico: int
    chamadas: int
    releitura_total: int
    escrita_primeira: int
    escrita_5m: int
    escrita_1h: int
    modelo: str

    @property
    def excedente(self) -> int:
        """O que um `/clear` tiraria da janela: tudo acima da base do harness."""
        return max(0, self.atual - self.base)


def _escrita(usage: dict) -> tuple[int, int]:
    cc = usage.get("cache_creation") or {}
    if cc:
        return cc.get("ephemeral_5m_input_tokens", 0), cc.get("ephemeral_1h_input_tokens", 0)
    return usage.get("cache_creation_input_tokens", 0), 0


def medir(caminho: str) -> Medida | None:
    """Lê o transcript e devolve a medida da thread principal, ou None se não há chamada legível.

    Subagente (`isSidechain`) fica fora: a janela dele não é relida pelo pai. Uma resposta da API
    vira várias linhas com o mesmo `message.id`; cada id conta uma vez. Linha ilegível é pulada,
    porque o transcript pode estar no meio de uma gravação.
    """
    vistos: set[str] = set()
    base = atual = pico = n = releitura = primeira = w5 = w1h = 0
    modelo = ""
    try:
        fh = open(caminho, encoding="utf-8")
    except OSError:
        return None
    with fh:
        for linha in fh:
            if '"usage"' not in linha:
                continue
            try:
                e = json.loads(linha)
            except json.JSONDecodeError:
                continue
            if e.get("type") != "assistant" or e.get("isSidechain"):
                continue
            msg = e.get("message") or {}
            usage = msg.get("usage")
            mid = msg.get("id")
            if not usage or (mid and mid in vistos):
                continue
            if mid:
                vistos.add(mid)
            e5, e1 = _escrita(usage)
            lido = usage.get("cache_read_input_tokens", 0)
            ctx = usage.get("input_tokens", 0) + lido + e5 + e1
            if n == 0:
                base, primeira = ctx, e5 + e1
            n += 1
            atual = ctx
            pico = max(pico, ctx)
            releitura += lido
            w5 += e5
            w1h += e1
            modelo = msg.get("model") or modelo
    if n == 0:
        return None
    return Medida(base, atual, pico, n, releitura, primeira, w5, w1h, modelo)


def kilo(n: int) -> str:
    """Tokens para leitura humana nas mensagens: 105000 → '105k'."""
    return f"{n / 1000:.0f}k" if n >= 1000 else str(n)


def tokens_de_bytes(n_bytes: int) -> int:
    return round(n_bytes / BYTES_POR_TOKEN)


def tokens_de_arquivo(caminho: str) -> int:
    """Estimativa de tokens de um arquivo pelo tamanho em disco; 0 se ele não existe."""
    try:
        return tokens_de_bytes(os.path.getsize(caminho))
    except OSError:
        return 0


_tarifas: ModuleType | None | bool = False


def _carregar_tarifas() -> ModuleType | None:
    """O `turn-cost.py` é a fonte única de tarifa desta máquina; uma cópia aqui divergiria dela."""
    global _tarifas
    if _tarifas is False:
        _tarifas = None
        try:
            spec = importlib.util.spec_from_file_location("turn_cost_tarifas", TURN_COST)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                _tarifas = mod
        except Exception:  # noqa: BLE001 — tarifa ausente cai na razão padrão, nunca derruba o hook
            _tarifas = None
    return _tarifas if isinstance(_tarifas, ModuleType) else None


def razao_escrita_leitura(medida: Medida) -> float:
    """Quantas releituras de cache custa escrever o mesmo token no cache, para o modelo da sessão.

    O TTL sai do que a própria sessão escreveu (1 h se escreveu mais em 1 h que em 5 min). Modelo
    sem tarifa no `turn-cost.py` devolve `RAZAO_PADRAO`.
    """
    mult = 2.0 if medida.escrita_1h >= medida.escrita_5m else 1.25
    tarifas = _carregar_tarifas()
    if tarifas is None:
        return RAZAO_PADRAO if mult == 2.0 else RAZAO_PADRAO * 1.25 / 2.0
    preco = getattr(tarifas, "MODELOS", {}).get(medida.modelo)
    if not preco:
        return RAZAO_PADRAO if mult == 2.0 else RAZAO_PADRAO * 1.25 / 2.0
    entrada = preco[0]
    leitura = getattr(tarifas, "CACHE_READ", {}).get(medida.modelo, entrada * 0.1)
    return (entrada * mult) / leitura if leitura else RAZAO_PADRAO


def slug_do_projeto(pasta_do_projeto: str) -> str:
    """Nome da pasta do projeto em `~/.claude/projects`: todo caractere que não é letra ou dígito
    vira `-` (`C:/Users/a.b` → `C--Users-a-b`)."""
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(pasta_do_projeto))


def transcript_mais_recente(pasta_do_projeto: str) -> str | None:
    """O `.jsonl` mais recente do projeto — numa sessão viva, é o dela, que está sendo gravado agora."""
    slug = slug_do_projeto(pasta_do_projeto)
    achados = glob.glob(os.path.join(os.path.expanduser("~/.claude/projects"), slug, "*.jsonl"))
    return max(achados, key=os.path.getmtime) if achados else None


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    caminho = transcript_mais_recente(argv[1] if len(argv) > 1 else os.getcwd()) if argv[0] == "--ultimo" else argv[0]
    medida = medir(caminho or "")
    if medida is None:
        print(f"sem chamada legível em {caminho}")
        return 1
    print(json.dumps({**asdict(medida), "excedente": medida.excedente, "transcript": caminho,
                      "razao_escrita_leitura": round(razao_escrita_leitura(medida), 1)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
