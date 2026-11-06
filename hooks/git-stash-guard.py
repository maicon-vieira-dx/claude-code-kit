#!/usr/bin/env python3
"""Decisao do git-stash-guard: bloqueia stash de arvore inteira (sem pathspec).

Num incidente real, um stash sem pathspec, com agentes concorrentes editando, capturou
o trabalho em voo dos outros — near-miss de perda de dados. A regra: stash que
CRIA estado tem de delimitar paths.

Classe: DENY-GATE DE DADO. Quando nao consegue atestar (JSON ilegivel, stdin
mudo), NEGA — mas so no escopo: o texto tem de casar o subcomando em POSICAO DE
COMANDO. Sem esse recorte a inversao de polaridade derrubaria qualquer Bash sem
relacao nenhuma com stash, e negar sem dar a saida e custo puro.

Escopo do casamento (achado ao vivo em 21/09): o gate casava substring em
qualquer lugar do payload, entao escrever DOCUMENTACAO sobre a propria regra era
negado — heredoc, texto entre aspas e comentario sao dados, nao comando. Eles
saem do texto antes do casamento. O efeito colateral aceito e que um subcomando
escondido dentro de aspas (`bash -c "..."`) passa: o alvo deste gate e o erro
acidental do agente, nao a evasao deliberada.
"""
import json
import os
import re
import sys
import threading

TIMEOUT_STDIN = 5.0

# `git` tem de estar em POSICAO DE COMANDO: inicio, ou depois de separador de
# comando. `mygit stash` ou `--git stash` nao casam.
COMANDO_GIT = re.compile(
    r"(?:^|[;&|(\n`]|\$\()\s*"
    r"git\b((?:\s+(?:-C\s+\S+|-c\s+\S+|--\S+(?:=\S+)?))*)\s+stash\b([^\n;&|]*)"
)

# Subcomandos que NAO criam um novo stash da arvore -> liberados.
NAO_CRIA = ("list", "show", "pop", "apply", "drop", "clear", "branch", "create", "store")

REMEDIO = (
    "stash de arvore inteira (sem pathspec) bloqueado por hook "
    "(~/.claude/hooks/git-stash-guard.py). Com trabalho em voo isso captura tudo "
    "e e near-miss de perda de dados. Delimite os paths com a forma "
    "`push` seguida de `--` e os caminhos, ou use o patch interativo `-p`. "
    "Subcomandos read-only (list/show/pop/apply/drop) sao liberados."
)


def ler_stdin(timeout: float = TIMEOUT_STDIN) -> str:
    """Le stdin com teto de tempo. Sem o teto, stdin mudo pendura o PreToolUse.

    Decodifica com utf-8-sig: no Windows o stdin de texto usa cp1252 e os bytes
    do BOM viram tres caracteres visiveis em vez de \\ufeff, quebrando o parse.
    Thread daemon porque `select` nao funciona sobre pipe no Windows.
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


def sem_literais(cmd: str) -> str:
    """Remove corpo de heredoc, string entre aspas e comentario.

    O que sobra e o que o shell de fato executaria como comando. E o recorte que
    faz `cat > doc.md <<EOF ... EOF` com a regra escrita dentro deixar de ser
    negado.
    """
    s = cmd
    # Corpo de heredoc: <<TAG ... \nTAG  (aceita <<-, aspas na tag)
    abre = re.compile(r"<<-?\s*([\"']?)([A-Za-z_][A-Za-z0-9_]*)\1")
    partes = []
    i = 0
    while True:
        m = abre.search(s, i)
        if not m:
            partes.append(s[i:])
            break
        partes.append(s[i:m.start()])
        tag = m.group(2)
        fecha = re.search(r"^\s*" + re.escape(tag) + r"\s*$", s[m.end():], re.M)
        if not fecha:
            break  # heredoc sem terminador: o resto e corpo, descarta
        i = m.end() + fecha.end()
    s = " ".join(partes)
    # Strings entre aspas (dado, nao comando)
    s = re.sub(r"'[^']*'", " ", s)
    s = re.sub(r"\"[^\"]*\"", " ", s)
    # Comentarios
    s = re.sub(r"#[^\n]*", " ", s)
    return s


def cria_stash_de_arvore(cmd: str) -> bool:
    """True se o comando cria stash da arvore inteira, sem delimitar paths."""
    for m in COMANDO_GIT.finditer(sem_literais(cmd)):
        tokens = m.group(2).strip().split()
        sub = tokens[0] if tokens else ""
        if sub in NAO_CRIA:
            continue
        # Liberado se delimita paths (--) ou e patch interativo (-p/--patch).
        if "--" in tokens or "-p" in tokens or "--patch" in tokens:
            continue
        return True
    return False


def negar(motivo: str, aviso: str = "") -> None:
    saida = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": motivo,
        }
    }
    if aviso:
        saida["systemMessage"] = aviso
    print(json.dumps(saida))


def avisar_uma_vez(sid: str, msg: str) -> None:
    """Aviso de falha uma vez por sessao — por invocacao dispararia o circuit-breaker."""
    tmp = os.environ.get("TMPDIR") or os.environ.get("TEMP") or "/tmp"
    marca = os.path.join(tmp, f"claude-stashguard-warned-{sid}")
    try:
        if os.path.exists(marca):
            return
        with open(marca, "w", encoding="utf-8") as f:
            f.write("1")
    except OSError:
        pass
    print(json.dumps({"systemMessage": msg}))


def main() -> None:
    bruto = ler_stdin()

    if not bruto.strip():
        # Nada para casar -> nada a negar. Avisa: um deny-gate mudo e um portao
        # aberto que ninguem percebe.
        avisar_uma_vez("nostdin", "⚠ git-stash-guard: sem entrada do host — nao atestei este comando")
        return

    try:
        d = json.loads(bruto)
    except (json.JSONDecodeError, TypeError):
        # Nao consigo atestar. Classe deny-gate de dado -> NEGA, no escopo:
        # so se o texto bruto casar o subcomando em posicao de comando.
        if cria_stash_de_arvore(bruto):
            negar(
                "Entrada do hook ilegivel E o comando casa o padrao de risco. " + REMEDIO,
                "⛔ git-stash-guard: payload ilegivel, negado por precaucao",
            )
        else:
            avisar_uma_vez(
                "badjson",
                "⚠ git-stash-guard: payload ilegivel — liberado porque nao casa o padrao de risco",
            )
        return

    # `tool_name` AUSENTE nao e o mesmo que "nao e Bash": um payload sem o campo
    # e um payload que nao consigo atestar, e a classe deste gate manda checar o
    # comando mesmo assim. So um tool_name presente E diferente de Bash libera.
    tool = d.get("tool_name")
    if tool is not None and tool != "Bash":
        return

    cmd = str((d.get("tool_input", {}) or {}).get("command", ""))
    if cria_stash_de_arvore(cmd):
        negar(REMEDIO)


if __name__ == "__main__":
    main()
