import json
import re
import shlex
import sys

# Gate do pool do Vitest (maquina Windows local).
#
# Vitest 1.6.1 nao tem variavel de ambiente para `pool`: resolveConfig faz
#   resolved.pool ?? (resolved.pool = "threads")
# (node_modules/vitest/dist/vendor/cli-api.*.js:9497). O pool `threads` segfaulta
# (exit 139) neste Windows assim que a spec carrega Angular/zone.js/Firebase.
#
# Logo `pool` so vem de arquivo de config ou de flag de CLI. Config e versionada e
# isto e problema DESTA maquina, entao a flag e o caminho.
#
# Por que `--minWorkers=1` e nao `--poolOptions.forks.minForks=1`:
# o yargs do Nx aninha flag pontilhada em objeto ANTES de chegar ao executor, e o
# getOptionsAsArgv (@nx/vite) re-serializa objeto como --poolOptions='{"..."}',
# que chega ao Vitest como string e nao aplica. `minWorkers` e flat e sobrevive.
# Em cli-api.js:8036 o forks pool le
#   minThreads = poolOptions.minForks ?? ctx.config.minWorkers ?? threadsCount
# entao minWorkers=1 cobre o mesmo papel.
#
# Sem esse minimo explicito, o fallback vira CPUs-1 (=11) contra o
# VITEST_MAX_FORKS=2 do ambiente e o Tinypool lanca
#   RangeError: options.minThreads and options.maxThreads must not conflict
# maxForks NAO entra na flag de proposito: vem do ambiente, aplicado por ultimo.

REQUIRED = "--pool=forks --minWorkers=1"

SEGMENT_SPLIT = re.compile(r"(?:\|\||&&|[;|\n])")
ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
WRAPPERS = {"npx", "pnpm", "yarn", "bunx", "bun", "npm", "cmd", "sudo", "time", "command", "env", "exec"}
RUNNERS = {"nx", "vitest"}

# Ja definiu pool/concorrencia explicitamente -> respeita a escolha.
HAS_POOL = re.compile(r"--pool[=\s]|poolOptions|--minWorkers[=\s]")

MSG = (
    "Rodada de Vitest sem o pool explicito. O pool padrao (`threads`) segfaulta "
    "(exit 139) nesta maquina Windows, e `pool` nao tem variavel de ambiente — so "
    "flag de CLI ou arquivo de config, e a config NAO deve ser versionada.\n\n"
    "Reenvie o mesmo comando acrescentando:\n\n"
    "    " + REQUIRED + "\n\n"
    "Ex.: npx nx test <projeto> --testFile=<arquivo.spec.ts> " + REQUIRED + "\n\n"
    "NAO use --poolOptions.forks.minForks: o yargs do Nx aninha flag pontilhada e o "
    "executor a re-serializa como JSON string, que o Vitest ignora (da RangeError). "
    "O teto de concorrencia ja vem de VITEST_MAX_FORKS=2 do ambiente — nao passe "
    "maxForks nem defina VITEST_MIN_FORKS. Detalhe: memoria `vitest-ram-swap-fix`."
)


def head_tokens(segment):
    """Tokens do segmento a partir do executavel real, pulando env e wrappers."""
    try:
        tokens = shlex.split(segment, posix=True)
    except ValueError:
        tokens = segment.split()

    i = 0
    while i < len(tokens):
        token = tokens[i]
        if ENV_ASSIGN.match(token):
            i += 1
            continue
        # basename, para pegar node_modules/.bin/vitest e afins
        name = re.split(r"[\\/]", token)[-1]
        name = re.sub(r"\.(cmd|exe|ps1|js|mjs)$", "", name)
        if name in WRAPPERS or token.startswith("-"):
            i += 1
            continue
        return name, tokens[i + 1:]
    return None, []


def invokes_vitest(segment):
    name, rest = head_tokens(segment)
    if name not in RUNNERS:
        return False
    if any(a in ("--help", "-h", "--version") for a in rest):
        return False
    if name == "vitest":
        return True

    # nx: precisa mirar um alvo de teste.
    for index, arg in enumerate(rest):
        if arg in ("test", "test-integration"):
            return True
        if arg.endswith(":test") or arg.endswith(":test-integration"):
            return True
        if arg in ("-t", "--target", "--targets") and index + 1 < len(rest):
            if rest[index + 1].startswith("test"):
                return True
        if arg.startswith(("-t=", "--target=", "--targets=")):
            if arg.split("=", 1)[1].startswith("test"):
                return True
    return False


def ler_stdin(timeout=5.0):
    """Le stdin com teto de tempo e trata BOM UTF-8.

    Sem o teto, stdin mudo pendura o PreToolUse. Sem o utf-8-sig, os bytes do
    BOM decodificam em cp1252 no Windows e quebram o parse — o gate morre calado,
    que para um deny-gate e o mesmo que abrir o portao.
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


VITEST_SOLTO = re.compile(r"(vitest|nx\b[^\n]{0,80}\brun-many\b[^\n]{0,80}\btest\b|nx\b[^\n]{0,80}:test\b)")


def parece_vitest_bruto(texto):
    """Busca frouxa, so para payload ILEGIVEL: o comando aparece em qualquer posicao.

    Com JSON truncado o comando nao fica em cabeca de segmento, entao o matcher
    preciso (`falta_pool`) nao o enxerga e o gate abriria calado. Aqui a precisao
    importa menos que nao abrir o portao: o escopo ja esta limitado a payload que
    o host entregou quebrado.
    """
    return bool(VITEST_SOLTO.search(texto)) and "--pool=forks" not in texto


def falta_pool(texto):
    """True se algum segmento invoca Vitest sem a flag de pool exigida."""
    for segment in SEGMENT_SPLIT.split(texto):
        if not segment.strip():
            continue
        if not invokes_vitest(segment):
            continue
        if HAS_POOL.search(segment):
            continue
        return True
    return False


def negar(motivo, aviso=""):
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


def avisar_uma_vez(sid, msg):
    """Aviso uma vez por sessao — por invocacao dispararia o circuit-breaker."""
    import os

    tmp = os.environ.get("TMPDIR") or os.environ.get("TEMP") or "/tmp"
    marca = os.path.join(tmp, "claude-vitestgate-warned-" + sid)
    try:
        if os.path.exists(marca):
            return
        with open(marca, "w", encoding="utf-8") as f:
            f.write("1")
    except OSError:
        pass
    print(json.dumps({"systemMessage": msg}))


def main():
    # Classe: DENY-GATE DE SEGURANCA. Quando nao consegue atestar, NEGA — mas so
    # no escopo: o texto tem de parecer uma invocacao de Vitest sem a flag.
    # Qualquer outro Bash continua passando; senao um payload quebrado do host
    # derrubaria comando legitimo sem relacao nenhuma com a suite.
    bruto = ler_stdin()

    if not bruto.strip():
        avisar_uma_vez("nostdin", "⚠ vitest-pool-gate: sem entrada do host - nao atestei este comando")
        sys.exit(0)

    try:
        payload = json.loads(bruto)
    except Exception:
        if parece_vitest_bruto(bruto):
            negar(
                "Entrada do hook ilegivel E o comando parece rodar Vitest sem o pool exigido. " + MSG,
                "⛔ vitest-pool-gate: payload ilegivel, negado por precaucao",
            )
        else:
            avisar_uma_vez(
                "badjson",
                "⚠ vitest-pool-gate: payload ilegivel - liberado porque nao casa o padrao de risco",
            )
        sys.exit(0)

    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command:
        sys.exit(0)

    if falta_pool(command):
        negar(MSG)

    sys.exit(0)


if __name__ == "__main__":
    main()
