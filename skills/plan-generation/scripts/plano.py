"""Lê do plano gravado pela plan-generation os campos que os hooks precisam.

Os formatos vêm de `templates/plano.md`. Placeholder `<...>` não preenchido não conta como
conteúdo: sem isso o próprio texto do template satisfaria a checagem da conta de break-even.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

_DECISOES = re.compile(r"##\s*Decis[õo]es de execu[çc][ãa]o(.*?)(\n##\s|\Z)", re.S)
_ALVOS = re.compile(r"##\s*Arquivos-alvo(.*?)(\n##\s|\Z)", re.S)
_PLACEHOLDER = re.compile(r"<[^<>\n]*>")
_D3 = re.compile(r"\*\*D3[^\n]*executor:\*\*([^\n]*)")
_D0_EXEC = (re.compile(r"execu[çc][ãa]o:\s*~?\s*(\d+)"), re.compile(r"D0_exec\s*[=:]\s*~?\s*(\d+)"))
_D0_TOTAL = re.compile(r"Or[çc]amento[^\n]*?~?\s*(\d+)")
_PASSOS = re.compile(r"\*\*Passos fechados:\*\*\s*(\d+)\s*de\s*(\d+)")
_CONTA = re.compile(r"break-?even|400\s?0{3}|400\s?k|\d+\s*k?\s*[x*×]\s*\d+", re.I)
_CAMINHO = re.compile(r"`([^`\s]+\.[A-Za-z0-9]+)`")


@dataclass(frozen=True)
class Plano:
    caminho: str
    texto: str
    d3: str | None = None
    d0_exec: int | None = None
    d0_total: int | None = None
    tem_conta: bool = False
    passos: tuple[int, int] | None = None
    alvos: tuple[str, ...] = field(default_factory=tuple)

    @property
    def slug(self) -> str:
        return os.path.splitext(os.path.basename(self.caminho))[0]

    def cita(self, arquivo: str) -> bool:
        """True se o plano menciona o nome do arquivo — só então ele governa a edição."""
        base = os.path.basename(arquivo.replace("\\", "/"))
        if not base:
            return False
        return re.search(r"(?<![\w.-])" + re.escape(base) + r"(?![\w-])", self.texto) is not None


def eh_caminho_de_plano(caminho: str) -> bool:
    norm = caminho.replace("\\", "/")
    return "/.claude/plans/" in norm and norm.endswith(".md") and os.path.basename(norm) != "README.md"


def _d3(sec: str) -> str | None:
    """`solo`, `subagente`, `usuario`, `ambigua` (mais de uma opção, como no template) ou None."""
    m = _D3.search(sec)
    if not m:
        return None
    v = m.group(1).lower()
    achadas = [
        nome
        for nome, presente in (
            ("solo", "mesma janela" in v or "solo" in v),
            ("subagente", "subagente" in v),
            ("usuario", "usuário" in v or "usuario" in v),
        )
        if presente
    ]
    return achadas[0] if len(achadas) == 1 else "ambigua"


def ler_plano(caminho: str) -> Plano | None:
    try:
        with open(caminho, encoding="utf-8") as fh:
            texto = fh.read()
    except (OSError, UnicodeDecodeError):
        return None
    m = _DECISOES.search(texto)
    sec = _PLACEHOLDER.sub("", m.group(1)) if m else ""
    d0_exec = None
    for rx in _D0_EXEC:
        achado = rx.search(sec)
        if achado:
            d0_exec = int(achado.group(1))
            break
    total = _D0_TOTAL.search(_PLACEHOLDER.sub("", texto))
    passos = _PASSOS.search(texto)
    alvos_sec = _ALVOS.search(texto)
    alvos = tuple(dict.fromkeys(_CAMINHO.findall(alvos_sec.group(1)))) if alvos_sec else ()
    return Plano(
        caminho=caminho,
        texto=texto,
        d3=_d3(sec) if m else None,
        d0_exec=d0_exec,
        d0_total=int(total.group(1)) if total else None,
        tem_conta=bool(_CONTA.search(sec)),
        passos=(int(passos.group(1)), int(passos.group(2))) if passos else None,
        alvos=alvos,
    )
