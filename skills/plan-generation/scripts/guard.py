"""Hook único da plan-generation: PreToolUse, PostToolUse e Stop, registrados no frontmatter da skill.

Só existe depois que a skill é invocada na sessão, e por isso o estado é por sessão
(`claude-plangen-<session_id>.json` no diretório temporário). O plano que governa a sessão é o que
ELA gravou ou leu em `.claude/plans/` — nunca "o .md mais recente", heurística que cobrou o
orçamento de um plano contra uma tarefa que não era dele (2026-09-04).

Polaridade por classe (overlay pessoal):
- gate da D3 (PreToolUse Write|Edit|MultiEdit): deny-gate de escopo. Nega só o caso inequívoco;
  qualquer ambiguidade ou falha interna libera, com aviso uma vez por sessão.
- medição, orçamento e os módulos opcionais: nudge. Abrem sempre.
- Stop: só registra. Nunca imprime decisão.

Toda saída é `json.dumps` com escape ASCII. Com `ensure_ascii=False`, um emoji fora do cp1252
derrubava o processo no Windows antes de o deny sair, e o gate ficou morto sem ninguém ver
(achado de 2026-10-14 no `budget-guard.sh`, que este arquivo substitui).
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import threading
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import contexto  # noqa: E402
import plano as planos  # noqa: E402

LIMIAR_D3 = 20
EDICAO = ("Write", "Edit", "MultiEdit", "NotebookEdit")
MODULOS_OPCIONAIS = ("checkpoint", "acumulo", "calibracao")


def ler_stdin(timeout: float = 5.0) -> str:
    """Lê stdin com teto de tempo; devolve "" se o host não entregar nada a tempo.

    Lê o buffer binário em `utf-8-sig`: no Windows o stdin de texto decodifica em cp1252 e o BOM
    vira três caracteres que quebram o JSON. Thread porque `select` não funciona em pipe no Windows.
    """
    buf: list[str] = []

    def _ler() -> None:
        try:
            fonte = getattr(sys.stdin, "buffer", None)
            buf.append(fonte.read().decode("utf-8-sig", "replace") if fonte else sys.stdin.read())
        except Exception:  # noqa: BLE001
            buf.append("")

    t = threading.Thread(target=_ler, daemon=True)
    t.start()
    t.join(timeout)
    return buf[0] if buf else ""


def dir_temporario() -> str:
    return os.environ.get("TMPDIR") or os.environ.get("TEMP") or tempfile.gettempdir()


def caminho_estado(sid: str) -> str:
    return os.path.join(dir_temporario(), f"claude-plangen-{sid}.json")


def carregar_estado(sid: str) -> dict | None:
    try:
        with open(caminho_estado(sid), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def salvar_estado(sid: str, estado: dict) -> None:
    destino = caminho_estado(sid)
    tmp = destino + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(estado, fh)
        os.replace(tmp, destino)
    except OSError:
        pass


def emitir(obj: dict) -> None:
    print(json.dumps(obj))


def caminho_da_ferramenta(payload: dict) -> str:
    ti = payload.get("tool_input") or {}
    return str(ti.get("file_path") or ti.get("notebook_path") or "")


def estado_inicial(medida: contexto.Medida | None) -> dict:
    return {
        "criado": datetime.now().isoformat(timespec="seconds"),
        "base": medida.base if medida else 0,
        "ctx_inv": medida.atual if medida else 0,
        "releitura_inv": medida.releitura_total if medida else 0,
        "calls": 0,
        "plano": None,
        "vinculado_por": None,
        "calls_no_vinculo": 0,
        "passos_no_vinculo": None,
        "avisos": [],
    }


def aviso_de_invocacao(medida: contexto.Medida) -> tuple[str, str, str]:
    sujo = medida.excedente
    ctx = (
        f"Contexto na invocação da plan-generation: {medida.atual} tokens = base {medida.base} "
        f"(system prompt, CLAUDE.md, memória e skills — o piso que nem um /clear tira) + sujo {sujo} "
        "(conversa anterior a esta tarefa). Grave os três números na seção `## Contexto` do plano. "
        "Toda chamada desta tarefa relê a janela inteira: o que entrar agora é pago de novo em cada "
        "chamada seguinte."
    )
    usuario = f"contexto na invocação {contexto.kilo(medida.atual)} (base {contexto.kilo(medida.base)} · sujo {contexto.kilo(sujo)})"
    return ("invocacao", ctx, usuario)


def vincular(payload: dict, estado: dict) -> bool:
    """Liga o plano à sessão quando ela o grava (ou o lê, na retomada). Devolve True se ligou."""
    caminho = caminho_da_ferramenta(payload)
    if not caminho or not planos.eh_caminho_de_plano(caminho) or not os.path.isfile(caminho):
        return False
    ferramenta = payload.get("tool_name")
    if ferramenta == "Read" and estado.get("plano"):
        return False
    if ferramenta not in EDICAO and ferramenta != "Read":
        return False
    if estado.get("plano") == caminho:
        return False
    lido = planos.ler_plano(caminho)
    estado.update(
        plano=caminho,
        vinculado_por="leitura" if ferramenta == "Read" else "escrita",
        calls_no_vinculo=estado.get("calls", 0),
        passos_no_vinculo=list(lido.passos) if lido and lido.passos else None,
    )
    return True


def avisos_de_orcamento(estado: dict, plano: planos.Plano, medida: contexto.Medida | None) -> list:
    if not plano.d0_total or plano.d0_total <= 0:
        return []
    calls, orcado = estado.get("calls", 0), plano.d0_total
    releitura = (medida.releitura_total - estado.get("releitura_inv", 0)) if medida else 0
    janela = f" Janela agora: {contexto.kilo(medida.atual)} (base {contexto.kilo(medida.base)}); releitura desde a invocação: {contexto.kilo(releitura)} tokens." if medida else ""
    if calls >= orcado + orcado // 2:
        return [(
            "orcamento-1.5",
            f"Orçamento do plano estourado em 1,5×: {calls} tool calls (orçado ~{orcado}).{janela} "
            "É sinal forte de abordagem errada: pare, resuma o estado ao usuário e re-trie, em vez de "
            "continuar gastando. Não normalize o estouro.",
            f"orçamento estourado 1,5× ({calls}/{orcado})",
        )]
    if calls >= orcado:
        return [(
            "orcamento-1.0",
            f"Orçamento do plano atingido: {calls} tool calls (orçado ~{orcado}).{janela} Reavalie antes "
            "de seguir: o escopo cresceu? a topologia está errada? há um loop? Com mais de 30% do plano "
            "por fazer, a plan-generation manda a CONVERSAO TARDIA (D3): feche a camada corrente, grave "
            "o estado no plano e entregue as camadas restantes.",
            f"orçamento do plano ({orcado}) atingido",
        )]
    return []


def avisos_de_plano(plano: planos.Plano) -> list:
    """Plano no formato novo, mas com a D3 ou a D0 sem resolver: o gate da D3 não tem o que testar."""
    if plano.d3 is None:
        return []
    if plano.d3 == "ambigua":
        return [(
            "plano-d3",
            "A D3 do plano da sessão não está resolvida (a linha ainda lista mais de uma opção, como no "
            "template). Escolha UMA — eu / subagente por camada / usuário — e grave a justificativa.",
            "D3 do plano não resolvida",
        )]
    if plano.d3 == "solo" and plano.d0_exec is None:
        return [(
            "plano-d0",
            "O plano da sessão não declara D0_exec (calls de execução). Sem esse número a D3 foi "
            "decidida no vácuo. Grave: D0 — Orçamento: ~T tool calls no total (execução: ~E · já "
            "gastas: ~J).",
            "plano sem D0_exec",
        )]
    return []


def gate_d3(payload: dict, estado: dict | None) -> dict | None:
    """Deny para edição de código sob plano REPROVADO (D3 = solo, D0_exec ≥ 20, sem conta)."""
    if payload.get("tool_name") not in EDICAO or not estado or not estado.get("plano"):
        return None
    alvo = caminho_da_ferramenta(payload).replace("\\", "/")
    if not alvo or "/plans/" in alvo or "/.claude/" in alvo:
        return None
    plano = planos.ler_plano(estado["plano"])
    if not plano or not plano.cita(alvo) or plano.d3 != "solo":
        return None
    if plano.d0_exec is None or plano.d0_exec < LIMIAR_D3 or plano.tem_conta:
        return None
    motivo = "\n".join([
        "PLANO REPROVADO — não inicie a execução (plan-generation, seção NUNCA/PROIBIDO).",
        f"O plano da sessão ({os.path.basename(plano.caminho)}) tem D3 = solo com D0_exec = "
        f"{plano.d0_exec} (limiar da D3 = {LIMIAR_D3}) e nenhuma conta de break-even escrita.",
        "",
        "Corrija o PLANO antes de tocar código (editar o plano está liberado):",
        "  1. Classifique o regime: arquivos, camadas, TDD sim/não, D0_exec.",
        "  2. Rode o break-even: tokens_poupados × calls_restantes > 400000.",
        "  3. Grave o resultado na D3 — solo COM a conta, ou subagente por camada em série.",
        "Se a conta der solo, escreva-a: é ela que autoriza, não o default.",
    ])
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": motivo,
        },
        "systemMessage": f"⛔ plan-generation: plano reprovado (D3=solo, D0_exec={plano.d0_exec})",
    }


def modulos() -> dict:
    """Módulos opcionais presentes em `scripts/`. Cada plano posterior instala o seu."""
    achados = {}
    for nome in MODULOS_OPCIONAIS:
        try:
            achados[nome] = importlib.import_module(nome)
        except ImportError:
            continue
    return achados


def novos(estado: dict, avisos: list) -> list:
    """Filtra avisos já emitidos nesta sessão (a chave é o que deduplica) e registra os novos."""
    emitidos = set(estado.setdefault("avisos", []))
    saida = []
    for chave, ctx, usuario in avisos:
        if chave in emitidos:
            continue
        emitidos.add(chave)
        estado["avisos"].append(chave)
        saida.append((ctx, usuario))
    return saida


def pos_ferramenta(payload: dict, sid: str) -> None:
    medida = contexto.medir(payload.get("transcript_path") or "")
    estado = carregar_estado(sid)
    avisos: list = []
    if estado is None:
        estado = estado_inicial(medida)
        if medida:
            avisos.append(aviso_de_invocacao(medida))
    estado["calls"] = estado.get("calls", 0) + 1
    vinculou = vincular(payload, estado)
    plano = planos.ler_plano(estado["plano"]) if estado.get("plano") else None
    if plano:
        avisos += avisos_de_plano(plano) + avisos_de_orcamento(estado, plano, medida)
    mods = modulos()
    editou_plano = bool(plano) and payload.get("tool_name") in EDICAO and caminho_da_ferramenta(payload) == plano.caminho
    if "checkpoint" in mods and plano and medida and (editou_plano or vinculou):
        avisos += mods["checkpoint"].avaliar(estado, medida, plano)
    if "acumulo" in mods:
        avisos += mods["acumulo"].avaliar(payload, estado, medida, plano)
    saida = novos(estado, avisos)
    salvar_estado(sid, estado)
    if not saida:
        return
    emitir({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "\n\n".join(c for c, _ in saida),
        },
        "systemMessage": "📏 plan-generation: " + " · ".join(u for _, u in saida),
    })


def parada(payload: dict, sid: str) -> None:
    estado = carregar_estado(sid)
    mods = modulos()
    if not estado or not estado.get("plano") or "calibracao" not in mods:
        return
    medida = contexto.medir(payload.get("transcript_path") or "")
    plano = planos.ler_plano(estado["plano"])
    if medida and plano:
        mods["calibracao"].registrar(sid, estado, medida, plano)


def avisar_falha(sid: str, erro: Exception) -> None:
    marca = os.path.join(dir_temporario(), f"claude-plangen-falha-{sid}")
    if os.path.exists(marca):
        return
    try:
        open(marca, "w").close()
    except OSError:
        pass
    emitir({"systemMessage": f"⚠ plan-generation guard falhou ({type(erro).__name__}) — gate e medição desligados neste evento"})


def main() -> None:
    bruto = ler_stdin()
    try:
        payload = json.loads(bruto) if bruto.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    sid = str(payload.get("session_id") or "nosession")
    evento = payload.get("hook_event_name")
    try:
        if evento == "PreToolUse":
            decisao = gate_d3(payload, carregar_estado(sid))
            if decisao:
                emitir(decisao)
        elif evento == "PostToolUse":
            pos_ferramenta(payload, sid)
        elif evento == "Stop":
            parada(payload, sid)
    except Exception as erro:  # noqa: BLE001 — nudge e gate abrem; o aviso sai uma vez por sessão
        avisar_falha(sid, erro)


if __name__ == "__main__":
    main()
