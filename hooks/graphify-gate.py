import sys, os, json, re, shlex, shutil, subprocess

# Gate de busca em libs/ por LIMITE de ocorrencias (nao por proibicao total).
#   <= GRAPHIFY_GREP_MAX  -> permite (busca pontual, barata para o contexto)
#   >  GRAPHIFY_GREP_MAX  -> nega e forca graphify (exploratoria, cara)
# grep que so filtra stdin de um pipe (ex.: `ngc -p libs/... | grep X`) e liberado:
# o segmento do grep nao tem operando de path em libs/.
# NUNCA executa o comando do usuario — reconstroi um grep/find seguro so para contar.

LIMIT = int(os.environ.get("GRAPHIFY_GREP_MAX", "20"))
SEARCH_TOOLS = {"grep", "egrep", "fgrep", "rg", "ag", "ack", "ack-grep", "find"}

MSG = (
    "Busca em libs/ retornaria mais de %d ocorrencias (exploratoria). "
    "Use a skill graphify-search: graphify explain \"Simbolo\" / graphify query \"termos\" --dfs. "
    "grep/find pontual em libs/ (ate %d ocorrencias) e liberado. Ver .claude/rules/libs-graphify.md."
) % (LIMIT, LIMIT)

MSG_UNPARSEABLE = (
    "Nao foi possivel medir o escopo desta busca em libs/. "
    "Use a skill graphify-search (graphify explain/query) em vez de grep/find cru. "
    "Ver .claude/rules/libs-graphify.md."
)

NUM_VALUE_FLAGS = {
    "-A", "-B", "-C", "-m", "-d",
    "--after-context", "--before-context", "--context", "--max-count",
}


def emit_allow():
    sys.exit(0)


def emit_deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def bounded_count(cmd):
    # Le no maximo LIMIT+1 linhas do stdout e encerra. Retorna int, ou None em falha.
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    except Exception:
        return None
    n = 0
    try:
        for _ in p.stdout:
            n += 1
            if n > LIMIT:
                break
    except Exception:
        return None
    finally:
        try:
            p.stdout.close()
        except Exception:
            pass
        try:
            p.terminate()
            p.wait(timeout=1)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
    return n


def timeout_prefix(segundos=5):
    """Prefixo `timeout` do coreutils, resolvido por caminho ABSOLUTO.

    No Windows, `timeout` resolvido pelo PATH cai no TIMEOUT.EXE do System32 (o
    comando de pausa do cmd), que rejeita os argumentos e nunca executa o grep:
    a contagem voltava 0 e o gate liberava TODA busca em libs/. Sem coreutils
    disponivel, roda sem prefixo — bounded_count ja encerra o processo por conta
    propria ao passar do limite.
    """
    exe = shutil.which("timeout")
    if exe and "system32" not in exe.lower():
        return [exe, str(segundos)]
    return []


def grep_count(pattern, paths, flags, fixed):
    base = "-rIsF" if fixed else "-rIsE"
    cmd = timeout_prefix() + ["grep", base] + flags + ["-e", pattern, "--"] + paths
    return bounded_count(cmd)


def find_count(paths):
    return bounded_count(timeout_prefix() + ["find"] + paths)


def parse_grep_segment(toks, tool_idx):
    # Retorna (pattern, paths, flags, fixed). pattern=None se nao der para extrair.
    tool = os.path.basename(toks[tool_idx])
    fixed = tool == "fgrep"
    ignore = False
    word = False
    include_flags = []
    patterns = []
    paths = []
    saw_e = False
    operands_only = False
    i = tool_idx + 1
    while i < len(toks):
        t = toks[i]
        if not operands_only and t == "--":
            operands_only = True
            i += 1
            continue
        if not operands_only and t.startswith("-") and t != "-":
            if t in ("-e", "--regexp"):
                i += 1
                if i < len(toks):
                    patterns.append(toks[i])
                    saw_e = True
            elif t.startswith("--regexp="):
                patterns.append(t.split("=", 1)[1])
                saw_e = True
            elif t in NUM_VALUE_FLAGS:
                i += 1  # pula o valor do flag
            elif t.startswith("--include=") or t.startswith("--exclude=") or t.startswith("--include-dir=") or t.startswith("--exclude-dir="):
                include_flags.append(t)
            elif t in ("--include", "--exclude", "--include-dir", "--exclude-dir"):
                i += 1
                if i < len(toks):
                    include_flags.append("%s=%s" % (t, toks[i]))
            elif t in ("-i", "--ignore-case", "-y"):
                ignore = True
            elif t in ("-w", "--word-regexp"):
                word = True
            elif t in ("-F", "--fixed-strings"):
                fixed = True
            elif re.fullmatch(r"-[A-Za-z]+", t):
                letters = t[1:]
                if "i" in letters:
                    ignore = True
                if "w" in letters:
                    word = True
                if "F" in letters:
                    fixed = True
            i += 1
            continue
        # operando
        if not saw_e and not patterns:
            patterns.append(t)
        else:
            paths.append(t)
        i += 1
    flags = []
    if ignore:
        flags.append("-i")
    if word:
        flags.append("-w")
    flags += include_flags
    pattern = patterns[0] if patterns else None
    return pattern, paths, flags, fixed


def handle_bash(cmd):
    if not re.search(r"(^|[\s|;&(])(grep|egrep|fgrep|rg|ag|ack|ack-grep|find)\b", cmd):
        emit_allow()
    if "libs/" not in cmd:
        emit_allow()
    for seg in re.split(r"[|;&\n]+", cmd):
        seg = seg.strip()
        if not seg or "libs/" not in seg:
            continue
        try:
            toks = shlex.split(seg)
        except Exception:
            emit_deny(MSG_UNPARSEABLE)
        tool_idx = None
        for idx, tk in enumerate(toks):
            if os.path.basename(tk) in SEARCH_TOOLS:
                tool_idx = idx
                break
        if tool_idx is None:
            continue
        tool = os.path.basename(toks[tool_idx])
        if tool == "find":
            paths = []
            for tk in toks[tool_idx + 1:]:
                if tk.startswith("-") or tk in ("(", ")", "!"):
                    break
                paths.append(tk)
            libs_paths = [p for p in paths if "libs/" in p]
            if not libs_paths:
                continue
            n = find_count(libs_paths)
        else:
            pattern, paths, flags, fixed = parse_grep_segment(toks, tool_idx)
            libs_paths = [p for p in paths if "libs/" in p]
            if not libs_paths:
                # libs/ estava no pattern ou num filtro; nao e busca de fonte em libs/
                continue
            if pattern is None:
                emit_deny(MSG_UNPARSEABLE)
            n = grep_count(pattern, libs_paths, flags, fixed)
        if n is None:
            emit_deny(MSG_UNPARSEABLE)
        if n > LIMIT:
            emit_deny(MSG)
    emit_allow()


def handle_grep_tool(ti):
    pattern = ti.get("pattern")
    path = ti.get("path") or "."
    glob = ti.get("glob") or ""
    if "libs/" not in ("%s %s" % (path, glob)):
        emit_allow()
    if not pattern:
        emit_allow()
    flags = []
    if glob:
        flags.append("--include=%s" % glob)
    if ti.get("-i"):
        flags.append("-i")
    if ti.get("-w"):
        flags.append("-w")
    n = grep_count(pattern, [path], flags, False)
    if n is None:
        emit_deny(MSG_UNPARSEABLE)
    if n > LIMIT:
        emit_deny(MSG)
    emit_allow()


def handle_glob_tool(ti):
    pattern = ti.get("pattern") or ""
    path = ti.get("path") or "."
    if "libs/" not in ("%s %s" % (pattern, path)):
        emit_allow()
    root = path if "libs/" in path else (pattern.split("*")[0] or ".")
    n = find_count([root])
    if n is None:
        emit_deny(MSG_UNPARSEABLE)
    if n > LIMIT:
        emit_deny(MSG)
    emit_allow()


def ler_stdin(timeout=5.0):
    """Le stdin com teto de tempo e trata BOM UTF-8.

    Sem o teto, stdin mudo pendura o PreToolUse. Sem o utf-8-sig, os bytes do BOM
    decodificam em cp1252 no Windows e quebram o parse.
    """
    import threading

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


def avisar_uma_vez(sid, msg):
    """Aviso uma vez por sessao — por invocacao dispararia o circuit-breaker."""
    import os

    tmp = os.environ.get("TMPDIR") or os.environ.get("TEMP") or "/tmp"
    marca = os.path.join(tmp, "claude-graphifygate-warned-" + sid)
    try:
        if os.path.exists(marca):
            return
        with open(marca, "w", encoding="utf-8") as f:
            f.write("1")
    except OSError:
        pass
    print(json.dumps({"systemMessage": msg}))


def main():
    # Classe: DENY-GATE DE ESCOPO. A polaridade aqui e DUAL de proposito, e os
    # dois caminhos decidem para lados opostos:
    #   - payload ilegivel / interpretador morto -> LIBERA. Este gate protege
    #     orcamento de contexto, nao dado; negar toda busca por causa de um
    #     payload quebrado custa mais que a busca ampla que escapa.
    #   - contagem de ocorrencias que nao parseia -> NEGA (em bounded_count).
    #     Ali o gate SABE que e busca em libs/ e so nao sabe o tamanho; liberar
    #     seria assumir "pequena" justamente no caso que ele existe para pegar.
    # Em ambos, avisa: gate mudo e portao invisivel.
    bruto = ler_stdin()
    if not bruto.strip():
        avisar_uma_vez("nostdin", "⚠ graphify-gate: sem entrada do host - busca nao atestada")
        sys.exit(0)
    try:
        d = json.loads(bruto)
    except Exception:
        avisar_uma_vez("badjson", "⚠ graphify-gate: payload ilegivel - busca liberada sem atestar")
        sys.exit(0)
    tool = d.get("tool_name", "")
    ti = d.get("tool_input", {}) or {}
    if tool == "Bash":
        handle_bash(str(ti.get("command", "")))
    elif tool == "Grep":
        handle_grep_tool(ti)
    elif tool == "Glob":
        handle_glob_tool(ti)
    emit_allow()


main()
