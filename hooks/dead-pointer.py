#!/usr/bin/env python3
"""dead-pointer — PostToolUse (Write|Edit).

Avisa quando um arquivo de instrução (SKILL.md, CLAUDE.md, AGENTS.md, rules/,
docs/, commands/) cita um caminho, arquivo irmao ou slash-command que NAO existe
no disco. Nao bloqueia: emite systemMessage + additionalContext e sai 0.

Caso que motivou o hook: interface-design/SKILL.md anunciou por meses dois
comandos (/interface-design:design-review, :design-deslop) morando em
~/.claude/commands/ — diretorio que nunca existiu.

Uso manual (varredura completa do backlog):
    python3 dead-pointer.py --sweep
    python3 dead-pointer.py --sweep <dir>
"""

import json
import os
import re
import sys
from pathlib import Path

HOME = Path.home()
CLAUDE = HOME / ".claude"

# So audita arquivo de instrucao.
NAMES = {"SKILL.md", "CLAUDE.md", "AGENTS.md", "CLAUDE.local.md"}
DIRS = ("/.claude/rules/", "/.claude/docs/", "/.claude/commands/")

# Slash-commands nativos do Claude Code — nunca sao ponteiro morto.
BUILTINS = {
    "help", "clear", "compact", "config", "context", "cost", "doctor", "exit",
    "hooks", "init", "install-github-app", "login", "logout", "mcp", "memory",
    "model", "permissions", "pr-comments", "release-notes", "resume", "review",
    "rewind", "status", "terminal-setup", "vim", "add-dir", "agents", "bug",
    "effort", "export", "fast", "ide", "rename", "todos", "usage",
}

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
CODEPATH = re.compile(r"`([^`\n]*/[^`\n]*\.(?:md|py|sh|mjs|js|ts|json|ya?ml))`")
# A crase ABRE colada na barra e nao ha segunda barra: `/design-review` e
# comando; `/tmp/x.json` e caminho; o lookbehind descarta crase de FECHAMENTO
# seguida de barra (`rxMethod`/pipe, `story_type`/label), que e prosa.
SLASH = re.compile(
    r"(?<![A-Za-z0-9_)\]])`/([a-z][a-z0-9-]*(?::[a-z0-9-]+)?)(?:\s[^`\n/]*)?`"
)

# Conteudo de terceiro (plugin vendorizado) nao e meu para consertar.
VENDOR = ("/plugins/marketplaces/", "/node_modules/")

SKIPCHARS = ("*", "<", "{", "$", "|", "?", "...", " ")

# Caminho sob condicional/criacao e artefato que a skill GERA, nao irmao dela.
CONDITIONAL = (
    "if present", "if any", "when present", "optional",
    "write to", "save to", "create", "generate", "output to",
    "se existir", "se houver", "gravar em", "salvar em", "criar",
)
# Forma partida: "If `x/y.md` exists:", "unless <path> is there".
CONDITIONAL_RE = re.compile(r"\b(?:if|unless|whether|caso)\b.{0,80}?\bexist", re.I)


def project_root(path):
    """Sobe do arquivo ate a raiz do repo — caminho citado costuma ser dali."""
    for parent in path.resolve().parents:
        if (parent / ".git").exists() or (parent / "nx.json").is_file():
            return parent
    return None


def resolve(raw, base):
    """Candidatos de resolucao de um caminho, em ordem de prioridade."""
    if raw.startswith("~"):
        return [Path(raw).expanduser()]
    out = [base / raw, base.parent / raw, CLAUDE / raw, Path.cwd() / raw]
    root = project_root(base)
    if root:
        out.append(root / raw)
    return out


def command_exists(name, base=None):
    """Um slash-command pode ser command/ ou skill/ — pessoal ou de projeto.

    `plugin:cmd` resolve tambem para commands/<plugin>/<cmd>.md (namespaced).
    """
    parts = name.split(":")
    stem = parts[-1]
    roots = [CLAUDE, Path.cwd() / ".claude"]
    if base:
        root = project_root(base)
        if root:
            roots.append(root / ".claude")
    for root in roots:
        if (root / "commands" / f"{stem}.md").is_file():
            return True
        if (root / "skills" / stem / "SKILL.md").is_file():
            return True
        if len(parts) > 1 and (root / "commands" / parts[0] / f"{stem}.md").is_file():
            return True
    return False


def audit(path):
    """Devolve lista de (tipo, alvo) que nao existem no disco."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    base = path.parent
    dead, seen = [], set()

    def check(kind, raw, exists):
        key = (kind, raw)
        if key in seen:
            return
        seen.add(key)
        if not exists:
            dead.append((kind, raw))

    for raw in LINK.findall(text):
        if raw.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if any(c in raw for c in SKIPCHARS):
            continue
        target = raw.split("#")[0]
        if not target:
            continue
        check("link", raw, any(p.exists() for p in resolve(target, base)))

    fenced = False
    for line in text.splitlines():
        # Bloco cercado e template/exemplo, nao ponteiro vivo.
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue

        lowered = line.lower()
        guarded = any(marker in lowered for marker in CONDITIONAL) or bool(
            CONDITIONAL_RE.search(line)
        )

        if not guarded:
            for raw in CODEPATH.findall(line):
                if any(c in raw for c in SKIPCHARS) or raw.startswith(("http", "@")):
                    continue
                check("caminho", raw, any(p.exists() for p in resolve(raw, base)))

        # Comando anunciado vive em item de lista ou celula de tabela; barra em
        # prosa corrida (rota HTTP, alternativa "a/b") nao e anuncio.
        if line.lstrip().startswith(("-", "*", "|", "1.", "2.", "3.")):
            for name in SLASH.findall(line):
                if name.split(":")[-1] in BUILTINS:
                    continue
                check("comando", f"/{name}", command_exists(name, base))

    return dead


def is_target(path):
    posix = path.as_posix()
    if any(v in posix for v in VENDOR):
        return False
    return path.name in NAMES or any(d in posix for d in DIRS)


def sweep(root):
    root = Path(root)
    hits = 0
    for path in sorted(root.rglob("*.md")):
        if not is_target(path):
            continue
        dead = audit(path)
        if not dead:
            continue
        hits += 1
        try:
            shown = path.relative_to(root)
        except ValueError:
            shown = path
        print(f"\n{shown}")
        for kind, raw in dead:
            print(f"  MORTO  {kind}: {raw}")
    print(f"\n{hits} arquivo(s) com ponteiro morto." if hits else "\nNenhum ponteiro morto.")
    return 0


def ler_stdin(timeout=5.0):
    """Le stdin com teto de tempo e trata BOM UTF-8.

    Sem o teto, stdin mudo pendura o PostToolUse. Sem o utf-8-sig, os bytes do
    BOM decodificam em cp1252 no Windows e quebram o parse.
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
    tmp = os.environ.get("TMPDIR") or os.environ.get("TEMP") or "/tmp"
    marca = os.path.join(tmp, "claude-deadpointer-warned-" + sid)
    try:
        if os.path.exists(marca):
            return
        with open(marca, "w", encoding="utf-8") as f:
            f.write("1")
    except OSError:
        pass
    print(json.dumps({"systemMessage": msg}))


def main():
    if "--sweep" in sys.argv:
        idx = sys.argv.index("--sweep")
        root = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else CLAUDE
        return sweep(root)

    # Classe: NUDGE. Quando nao consegue atestar, ABRE (sai 0) — mas avisa, uma
    # vez por sessao. Silencio aqui perde um aviso; num deny-gate perderia o
    # portao, e por isso a polaridade e por classe, nao uniforme.
    bruto = ler_stdin()
    if not bruto.strip():
        avisar_uma_vez("nostdin", "⚠ dead-pointer: sem entrada do host - ponteiros nao conferidos")
        return 0
    try:
        payload = json.loads(bruto)
    except (json.JSONDecodeError, ValueError, TypeError):
        avisar_uma_vez("badjson", "⚠ dead-pointer: payload ilegivel - ponteiros nao conferidos neste turno")
        return 0

    raw = (payload.get("tool_input") or {}).get("file_path") or (
        payload.get("tool_response") or {}
    ).get("filePath")
    if not raw:
        return 0

    path = Path(raw)
    if not is_target(path) or not path.is_file():
        return 0

    dead = audit(path)
    if not dead:
        return 0

    lines = [f"{kind}: {target}" for kind, target in dead]
    joined = "; ".join(lines)
    detail = "\n".join(f"  - {line}" for line in lines)
    print(json.dumps({
        "systemMessage": f"ponteiro morto em {path.name}: {joined}",
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                f"O arquivo {path} cita alvos que nao existem no disco:\n{detail}\n"
                "Ponteiro morto e proibido (struct-rules, Passo 5): criar o destino "
                "ou remover a referencia antes de encerrar."
            ),
        },
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
