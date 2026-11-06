#!/usr/bin/env python3
"""Hook Stop: exibe o custo do último turno e a ocupação do contexto da sessão.

    ↑<in> ↓<out> · U$<custo> (<Modelo>)
    ctx ▰▰▱▱▱▱▱▱▱▱ <usado>/<janela> tokens (<pct>%)

Lê o transcript da sessão, soma o `usage` das mensagens do assistant desde a
última mensagem real do usuário (um turno = todas as chamadas à API até a
resposta final, incluindo tool use e subagents) e calcula o custo por modelo.

A ocupação é a da última chamada da thread principal (input + cache + output):
é o que a próxima chamada vai reenviar, o mesmo total que o `/context` mostra.
Subagent fica de fora — o contexto dele é outro.

Classe: NUDGE. Quando não consegue atestar, ABRE (sai 0) — mas avisa, uma vez
por sessão. Silêncio aqui só custa uma linha de informação; num deny-gate
custaria o portão, e por isso a polaridade é por classe, não uniforme.
"""
import json
import os
import sys
import threading
from datetime import date

# Preço por 1M de tokens: (input, output, nome amigável). Valores fixos — a
# Models API não retorna pricing, então a tabela vive aqui.
#
# EXCEÇÃO DE TARIFA (struct-rules, Neutralidade): estes números dependem de
# preço e por isso ficam escritos, marcados como recalculáveis. A data abaixo é
# a da última alteração da tabela — bump obrigatório ao reconferir as tarifas.
MODELOS_ATUALIZADO_EM = "2026-09-23"
VALIDADE_DIAS = 92  # ~3 meses

MODELOS = {
    "claude-sonnet-5-5": (2.0, 10.0, "Sonnet 5.5"),
    "claude-sonnet-5":(2.0, 10.0, "Sonnet 5"),
    "claude-sonnet-4-6": (3.0, 15.0, "Sonnet 4.6"),
    "claude-opus-5-5": (4.0, 20.0, "Opus 5.5"),
    "claude-opus-5": (5.0, 25.0, "Opus 5"),
    "claude-opus-4-8": (5.0, 25.0, "Opus 4.8"),
    "claude-opus-4-7": (5.0, 25.0, "Opus 4.7"),
    "claude-opus-4-6": (5.0, 25.0, "Opus 4.6"),
    "claude-haiku-4-5": (1.0, 5.0, "Haiku"),
    "claude-haiku-4-5-20251001": (1.0, 5.0, "Haiku"),
    "claude-fable-5-1": (10.0, 50.0, "Fable 5.1"),
    "claude-fable-5": (10.0, 50.0, "Fable"),
}

# Cache read por 1M onde NÃO é 0.1x do input; o resto segue a regra geral.
CACHE_READ = {
    "claude-opus-5-5": 0.20,
    "claude-fable-5-1": 0.25,
}

# Janela de contexto em tokens (Models API: `max_input_tokens`). Mesma regra da
# tabela de preços: id fora daqui não ganha %, só o total — janela chutada
# imprimiria um percentual com cara de medido.
JANELAS = {
    "claude-sonnet-5-5": 1000000,
    "claude-sonnet-5": 1000000,
    "claude-sonnet-4-6": 1000000,
    "claude-opus-5-5": 1000000,
    "claude-opus-5": 1000000,
    "claude-opus-4-8": 1000000,
    "claude-opus-4-7": 1000000,
    "claude-opus-4-6": 1000000,
    "claude-haiku-5-5": 1000000,
    "claude-haiku-4-5": 200000,
    "claude-haiku-4-5-20251001": 200000,
    "claude-fable-5-1": 1000000,
    "claude-fable-5": 1000000,
}
BARRA_SEGMENTOS = 10


def linha_contexto(usado: int, model: str) -> str:
    """Linha de ocupação no formato do `/context`, com barra quando a janela é conhecida."""
    janela = JANELAS.get(model)
    if not janela:
        return f"ctx {humanize(usado)} tokens (janela de {model or '?'} desconhecida)"
    frac = usado / janela
    cheios = min(BARRA_SEGMENTOS, max(1 if usado else 0, round(frac * BARRA_SEGMENTOS)))
    barra = "▰" * cheios + "▱" * (BARRA_SEGMENTOS - cheios)
    return f"ctx {barra} {humanize(usado)}/{humanize(janela)} tokens ({frac * 100:.0f}%)"


def preco(model: str):
    """(input, output, nome) para o modelo, ou None se o id não está na tabela.

    Sem ramo por família e sem fallback de tier: adivinhar a tarifa por
    substring do id é o mesmo defeito em escala menor — imprime um dólar que
    ninguém conferiu para aquele modelo, e custo com cara de medido é pior que
    custo ausente.
    """
    return MODELOS.get(model)


def tabela_vencida() -> bool:
    """True quando a tabela de preços passou da validade e precisa ser reconferida."""
    try:
        y, m, d = (int(p) for p in MODELOS_ATUALIZADO_EM.split("-"))
        return (date.today() - date(y, m, d)).days > VALIDADE_DIAS
    except (ValueError, TypeError):
        return True


def tokens_entrada(usage: dict) -> int:
    """Total de tokens de entrada do turno: input novo + cache read + cache write.

    O cache (read/write) é tokens reais processados e cobrados — entra tanto no
    custo quanto na contagem exibida, mesmo que o preço unitário seja menor.
    """
    cc = usage.get("cache_creation") or {}
    write = (
        cc.get("ephemeral_5m_input_tokens", 0) + cc.get("ephemeral_1h_input_tokens", 0)
        if cc
        else usage.get("cache_creation_input_tokens", 0)
    )
    return (
        usage.get("input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
        + write
    )


def custo_msg(usage: dict, in_price: float, out_price: float, read_price: float | None = None) -> float:
    """Custo de uma mensagem: input novo 1x, cache read 0.1x (ou `read_price`), write 5m 1.25x / 1h 2x, output."""
    if read_price is None:
        read_price = in_price * 0.1
    cc = usage.get("cache_creation") or {}
    write_5m = cc.get("ephemeral_5m_input_tokens", 0)
    write_1h = cc.get("ephemeral_1h_input_tokens", 0)
    if not cc:  # sem detalhamento de TTL: usa o agregado como 5m
        write_5m = usage.get("cache_creation_input_tokens", 0)
    return (
        usage.get("input_tokens", 0) * in_price
        + usage.get("cache_read_input_tokens", 0) * read_price
        + write_5m * in_price * 1.25
        + write_1h * in_price * 2.0
        + usage.get("output_tokens", 0) * out_price
    ) / 1_000_000


def humanize(n: int) -> str:
    """1000 -> '1k', 15800 -> '15.8k', 950 -> '950', 1000000 -> '1M'."""
    if n >= 1000000:
        return f"{n / 1000000:.1f}".rstrip("0").rstrip(".") + "M"
    if n >= 1000:
        return f"{n / 1000:.1f}".rstrip("0").rstrip(".") + "k"
    return str(n)


def ler_stdin(timeout: float = 5.0) -> str:
    """Lê stdin com teto de tempo; devolve "" se o host não entregar nada a tempo.

    Sem o teto, stdin vazio pendura o hook até o timeout do harness e o turno
    fica travado num nudge — o pior custo possível para a classe mais barata.
    Thread daemon porque `select` não funciona sobre pipe no Windows.

    Lê o buffer binário e decodifica com `utf-8-sig`: no Windows o stdin de
    texto decodifica em cp1252 e os bytes do BOM viram três caracteres visíveis
    em vez de `﻿`, então `lstrip` não alcança e o JSON quebra.
    """
    buf = []

    def _ler():
        try:
            fonte = getattr(sys.stdin, "buffer", None)
            if fonte is None:
                buf.append(sys.stdin.read().lstrip("﻿"))
            else:
                buf.append(fonte.read().decode("utf-8-sig", errors="replace"))
        except Exception:
            buf.append("")

    t = threading.Thread(target=_ler, daemon=True)
    t.start()
    t.join(timeout)
    return buf[0] if buf else ""


def avisar_uma_vez(sid: str, msg: str) -> None:
    """Emite o aviso de falha uma vez por sessão.

    Por invocação dispararia o `circuit-breaker` com a própria falha recorrente
    — mas falha recorrente é justamente a informação útil, então ela aparece,
    uma vez, em vez de se acumular em silêncio.
    """
    tmp = os.environ.get("TMPDIR") or os.environ.get("TEMP") or "/tmp"
    marca = os.path.join(tmp, f"claude-turncost-warned-{sid}")
    try:
        if os.path.exists(marca):
            return
        with open(marca, "w", encoding="utf-8") as f:
            f.write("1")
    except OSError:
        pass  # sem estado gravável: avisa toda vez, que ainda é melhor que calar
    print(json.dumps({"systemMessage": msg}))


def eh_prompt_usuario(entry: dict) -> bool:
    """True só para mensagem real do usuário (ignora tool_result e metadados)."""
    if entry.get("type") != "user" or entry.get("isMeta"):
        return False
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        return not any(
            isinstance(b, dict) and b.get("type") == "tool_result" for b in content
        )
    return False


def main() -> None:
    bruto = ler_stdin()
    if not bruto.strip():
        avisar_uma_vez("nostdin", "⚠ turn-cost: sem entrada do host — custo do turno não medido")
        return

    sid = "nosession"
    try:
        # BOM UTF-8 antes do JSON quebra o parse e o hook morre calado.
        payload = json.loads(bruto.lstrip("﻿"))
        sid = payload.get("session_id") or "nosession"
        with open(payload["transcript_path"], encoding="utf-8") as f:
            linhas = [json.loads(linha) for linha in f if linha.strip()]
    except (json.JSONDecodeError, OSError, KeyError, TypeError, AttributeError) as e:
        avisar_uma_vez(
            sid,
            f"⚠ turn-cost: não consegui ler o transcript ({type(e).__name__}) — "
            "custo do turno não medido neste turno",
        )
        return

    # Início do último turno: logo após a última mensagem real do usuário.
    inicio = 0
    for i in range(len(linhas) - 1, -1, -1):
        if eh_prompt_usuario(linhas[i]):
            inicio = i + 1
            break

    in_tok = out_tok = 0
    custo = 0.0
    modelo = None
    desconhecidos: list[str] = []
    ctx_usado = 0
    ctx_modelo = ""
    vistos: set[str] = set()  # uma resposta da API vira N linhas (1 por content
    # block) com o MESMO usage; conte cada message.id só uma vez.
    for entry in linhas[inicio:]:
        if entry.get("type") != "assistant":
            continue
        msg = entry.get("message") or {}
        usage = msg.get("usage")
        if not usage:
            continue
        mid = msg.get("id")
        if mid:
            if mid in vistos:
                continue
            vistos.add(mid)
        mid_modelo = msg.get("model", "")
        if not entry.get("isSidechain"):
            ctx_usado = tokens_entrada(usage) + usage.get("output_tokens", 0)
            ctx_modelo = mid_modelo
        in_tok += tokens_entrada(usage)
        out_tok += usage.get("output_tokens", 0)
        tarifa = preco(mid_modelo)
        if tarifa is None:
            if mid_modelo and mid_modelo not in desconhecidos:
                desconhecidos.append(mid_modelo)
            modelo = mid_modelo or modelo
            continue
        in_price, out_price, nome = tarifa
        custo += custo_msg(usage, in_price, out_price, CACHE_READ.get(mid_modelo))
        modelo = nome  # último modelo do turno é o que reporta

    if modelo is None:
        return  # nada para reportar

    tokens = f"↑{humanize(in_tok)} ↓{humanize(out_tok)}"
    ctx = f"\n{linha_contexto(ctx_usado, ctx_modelo)}" if ctx_modelo else ""

    if desconhecidos:
        ids = ", ".join(desconhecidos)
        print(json.dumps({"systemMessage":
            f"{tokens} · preço desconhecido ({ids}) — atualize a tabela em turn-cost.py{ctx}"}))
        return

    # 2 casas no padrão; mais casas quando arredondaria para zero.
    cs = f"{custo:.2f}" if custo >= 0.01 else f"{custo:.4f}"
    linha = f"{tokens} · U${cs} ({modelo})"
    if tabela_vencida():
        linha += f" ⚠ tarifa de {MODELOS_ATUALIZADO_EM}, reconferir"
    print(json.dumps({"systemMessage": linha + ctx}))


if __name__ == "__main__":
    main()
