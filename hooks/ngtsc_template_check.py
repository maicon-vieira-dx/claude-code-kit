#!/usr/bin/env python3
"""Diagnosticos de TEMPLATE Angular (NG*) dos arquivos que a sessao alterou no disco.

Por que existe
--------------
`ngc --noEmit -p <lib>/tsconfig.lib.json` NAO chega na fase de template-check quando o
programa ja tem erro TS pre-existente em dependencia. Em monorepo com legado isso e permanente:
as libs legadas somam ~100 erros TS pre-existentes, entao o ngc
para antes e imprime so esse ruido (todo com prefixo `../..`). Consequencia pratica: NG9,
NG8002 e NG8112 — bind em input inexistente, `InputSignal` cru dentro de pipe, `@let`
orfao — passavam batido pelo Stop hook e so apareciam no `nx serve` como
"Application bundle generation failed".

Aqui a fase de template roda direto no `NgCompiler`, arquivo a arquivo
(`getDiagnosticsForFile`), entao dependencia quebrada e irrelevante: pedimos apenas os
diagnosticos DO arquivo alvo.

Tambem cobre o segundo ponto cego: o gate antigo so coletava `.ts` do transcript, e erro
de template mora no `.html`. Uma sessao que so editou o `.html` saia sem checagem alguma.

Entrada : payload de hook (JSON) no stdin, com `transcript_path`.
Saida   : blocos "[lib]\\n  <erros>"; nada quando limpo.
Codigo  : sempre 0 — quem chama decide bloquear. Toolchain ausente -> silencioso.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Teto de libs por execucao: cada programa Angular custa ~10s; o Stop hook tem 180s.
MAX_LIBS = 4
EDIT_TOOLS = {"Edit", "Write", "MultiEdit"}
WATCHED_SUFFIXES = (".ts", ".html")

# Unico trecho que precisa ser JS: a API do compilador Angular nao tem binding Python.
# Recebe tsconfig e alvos por env para nao depender de quoting de argv.
NODE_SNIPPET = r"""
import { createRequire } from 'node:module';
import path from 'node:path';
const require = createRequire(import.meta.url);

let ts, ng;
try {
  ts = require('typescript');
  ng = require('@angular/compiler-cli');
} catch {
  process.exit(0);
}

const targets = new Set(
  (process.env.NGTC_FILES || '').split('\n').filter(Boolean).map((f) => path.resolve(f)),
);
if (targets.size === 0) process.exit(0);

try {
  const config = ng.readConfiguration(path.resolve(process.env.NGTC_TSCONFIG));
  const host = ts.createCompilerHost(config.options, true);
  const program = new ng.NgtscProgram(config.rootNames, config.options, host);

  // A analise precisa terminar antes de qualquer diagnostico de template.
  await program.compiler.analyzeAsync();

  const found = [];
  for (const sf of program.getTsProgram().getSourceFiles()) {
    if (!targets.has(path.resolve(sf.fileName))) continue;
    // OptimizeFor.SingleFile = 1 -> checa so este arquivo, nao o programa inteiro.
    found.push(...program.compiler.getDiagnosticsForFile(sf, 1));
  }

  const errors = found.filter((d) => d.category === ts.DiagnosticCategory.Error);
  if (errors.length === 0) process.exit(0);

  process.stdout.write(
    ts.formatDiagnostics(errors, {
      getCanonicalFileName: (f) => f,
      getCurrentDirectory: () => process.cwd(),
      getNewLine: () => '\n',
    }),
  );
} catch {
  process.exit(0);
}
"""


def touched_from_transcript(transcript: Path) -> list[str]:
    """Arquivos .ts/.html que esta sessao editou, na ordem em que apareceram."""
    seen: list[str] = []
    try:
        with transcript.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                message = entry.get("message", entry)
                blocks = message.get("content") if isinstance(message, dict) else None
                if not isinstance(blocks, list):
                    continue
                for block in blocks:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    if block.get("name") not in EDIT_TOOLS:
                        continue
                    path_str = (block.get("input") or {}).get("file_path")
                    if not isinstance(path_str, str):
                        continue
                    if not path_str.endswith(WATCHED_SUFFIXES):
                        continue
                    if ".claude/evals" in path_str:
                        continue
                    if path_str not in seen:
                        seen.append(path_str)
    except OSError:
        return []
    return seen


def changed_on_disk(repo: Path, candidates: list[str]) -> list[Path]:
    """Interseccao com o que mudou de fato: working tree, staged ou untracked.

    Edicao que voltou ao HEAD nao conta — o build real nao ve mudanca, o gate tambem nao.
    """
    rel = []
    for raw in candidates:
        try:
            rel.append(str(Path(raw).resolve().relative_to(repo)))
        except ValueError:
            continue  # fora do repo
    if not rel:
        return []

    commands = (
        ["git", "diff", "--name-only", "--"],
        ["git", "diff", "--cached", "--name-only", "--"],
        ["git", "ls-files", "--others", "--exclude-standard", "--"],
    )
    changed: set[str] = set()
    for command in commands:
        try:
            out = subprocess.run(
                command + rel, cwd=repo, capture_output=True, text=True, timeout=30
            )
        except (OSError, subprocess.SubprocessError):
            continue
        changed.update(line for line in out.stdout.splitlines() if line.strip())
    return [repo / c for c in sorted(changed)]


def component_source(file: Path) -> Path | None:
    """Arquivo .ts a checar. Template (.html) mapeia para o componente irmao."""
    if file.suffix == ".ts":
        return file if file.is_file() else None
    sibling = file.with_suffix(".ts")
    return sibling if sibling.is_file() else None


def project_tsconfig(file: Path, repo: Path) -> Path | None:
    """Sobe do arquivo ate achar o tsconfig do projeto que o compila."""
    for parent in file.parents:
        if not str(parent).startswith(str(repo)):
            break
        for name in ("tsconfig.lib.json", "tsconfig.app.json"):
            candidate = parent / name
            if candidate.is_file():
                return candidate
        if parent == repo:
            break
    return None


def check(tsconfig: Path, files: list[Path], repo: Path) -> str:
    env = dict(os.environ)
    env["NGTC_TSCONFIG"] = str(tsconfig)
    env["NGTC_FILES"] = "\n".join(str(f) for f in files)
    try:
        out = subprocess.run(
            ["node", "--input-type=module", "-e", NODE_SNIPPET],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip()


def main() -> int:
    repo = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()
    if not repo.is_dir():
        return 0

    try:
        payload = json.loads(sys.stdin.read() or "{}")
        transcript = payload.get("transcript_path")
    except ValueError:
        return 0
    if not transcript:
        return 0

    touched = touched_from_transcript(Path(transcript))
    if not touched:
        return 0

    sources: list[Path] = []
    for file in changed_on_disk(repo, touched):
        source = component_source(file)
        if source is not None and source not in sources:
            sources.append(source)
    if not sources:
        return 0

    by_project: dict[Path, list[Path]] = {}
    for source in sources:
        tsconfig = project_tsconfig(source, repo)
        if tsconfig is not None:
            by_project.setdefault(tsconfig, []).append(source)

    report: list[str] = []
    for tsconfig, files in list(by_project.items())[:MAX_LIBS]:
        errors = check(tsconfig, files, repo)
        if not errors:
            continue
        label = tsconfig.parent.relative_to(repo)
        body = "\n".join(f"  {line}" for line in errors.splitlines())
        report.append(f"[{label}]\n{body}")

    if report:
        sys.stdout.write("\n".join(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
