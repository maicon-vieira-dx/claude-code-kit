import json
import os
import tempfile
import time
import unittest

import apoio  # noqa: F401
from apoio import chamada, escrever_plano, escrever_transcript, rodar_guard


class GuardBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = os.path.join(self.tmp.name, "repo")
        os.makedirs(self.raiz)
        self.transcript = escrever_transcript(os.path.join(self.tmp.name, "s.jsonl"), [
            chamada(77000, w1h=77000), chamada(105000, lido=77000, w1h=28000),
        ])
        self.sid = "teste-" + str(id(self))

    def pos(self, ferramenta="Bash", caminho=None, **extra):
        ti = {"file_path": caminho} if caminho else {"command": "ls"}
        return rodar_guard({
            "hook_event_name": "PostToolUse", "tool_name": ferramenta, "tool_input": ti,
            "tool_response": {}, "session_id": self.sid, "transcript_path": self.transcript, **extra,
        }, self.tmp.name)

    def pre(self, caminho, ferramenta="Edit"):
        return rodar_guard({
            "hook_event_name": "PreToolUse", "tool_name": ferramenta, "tool_input": {"file_path": caminho},
            "session_id": self.sid, "transcript_path": self.transcript,
        }, self.tmp.name)

    def estado(self):
        with open(os.path.join(self.tmp.name, f"claude-plangen-{self.sid}.json"), encoding="utf-8") as fh:
            return json.load(fh)


class TestMedicaoNaInvocacao(GuardBase):
    def test_primeira_chamada_informa_base_e_sujo_uma_vez(self):
        cod, out = self.pos()
        self.assertEqual(cod, 0)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("105000 tokens = base 77000", ctx)
        self.assertIn("sujo 28000", ctx)
        self.assertEqual((self.estado()["base"], self.estado()["ctx_inv"]), (77000, 105000))
        self.assertEqual(self.pos()[1], "")

    def test_transcript_ausente_nao_derruba(self):
        self.transcript = os.path.join(self.tmp.name, "nao-existe.jsonl")
        self.assertEqual(self.pos(), (0, ""))
        self.assertEqual(self.estado()["calls"], 1)


class TestPlanoDaSessao(GuardBase):
    def test_escrita_do_plano_vincula(self):
        plano = escrever_plano(self.raiz)
        self.pos("Write", plano)
        self.assertEqual((self.estado()["plano"], self.estado()["vinculado_por"]), (plano, "escrita"))

    def test_leitura_vincula_so_sem_plano_ligado(self):
        a = escrever_plano(self.raiz, "a.md")
        b = escrever_plano(self.raiz, "b.md")
        self.pos("Read", a)
        self.pos("Read", b)
        self.assertEqual((self.estado()["plano"], self.estado()["vinculado_por"]), (a, "leitura"))

    def test_readme_de_plans_nao_vincula(self):
        readme = os.path.join(self.raiz, ".claude", "plans", "README.md")
        os.makedirs(os.path.dirname(readme), exist_ok=True)
        open(readme, "w").close()
        self.pos("Write", readme)
        self.assertIsNone(self.estado()["plano"])


class TestGateD3(GuardBase):
    def alvo(self):
        return os.path.join(self.raiz, "alvo.ts")

    def test_solo_sem_conta_nega_em_json_ascii(self):
        self.pos("Write", escrever_plano(self.raiz))
        cod, out = self.pre(self.alvo())
        self.assertEqual(cod, 0)
        saida = json.loads(out)
        self.assertEqual(saida["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("D0_exec = 25", saida["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertIn("\\u26d4", out)

    def test_solo_com_conta_libera(self):
        self.pos("Write", escrever_plano(self.raiz, regime="fora — break-even: S010 T1, solo."))
        self.assertEqual(self.pre(self.alvo()), (0, ""))

    def test_arquivo_nao_citado_libera(self):
        self.pos("Write", escrever_plano(self.raiz))
        self.assertEqual(self.pre(os.path.join(self.raiz, "outro.ts")), (0, ""))

    def test_plano_de_outra_sessao_nao_governa(self):
        escrever_plano(self.raiz, "antigo.md")
        os.utime(os.path.join(self.raiz, ".claude", "plans", "antigo.md"), (time.time(), time.time()))
        self.pos()
        self.assertEqual(self.pre(self.alvo()), (0, ""))

    def test_edicao_do_proprio_plano_libera(self):
        plano = escrever_plano(self.raiz)
        self.pos("Write", plano)
        self.assertEqual(self.pre(plano), (0, ""))

    def test_payload_ilegivel_libera(self):
        self.assertEqual(rodar_guard("{nao e json", self.tmp.name), (0, ""))


class TestAvisos(GuardBase):
    def test_d3_do_template_avisa_uma_vez(self):
        plano = escrever_plano(self.raiz, d3="eu, mesma janela | subagente por camada, em série | usuário")
        self.pos()
        _, out = self.pos("Write", plano)
        self.assertIn("não está resolvida", json.loads(out)["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(self.pos("Edit", plano)[1], "")

    def test_orcamento_avisa_em_1x_e_em_1_5x_uma_vez_cada(self):
        plano = escrever_plano(self.raiz, d0="~3 tool calls no total (execução: ~2 · já gastas: ~1)",
                               regime="dentro — break-even não se aplica")
        self.pos()
        self.pos("Write", plano)
        ctx = json.loads(self.pos()[1])["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Orçamento do plano atingido: 3 tool calls", ctx)
        self.assertIn("Janela agora: 105k (base 77k)", ctx)
        self.assertIn("estourado em 1,5×: 4 tool calls", json.loads(self.pos()[1])["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(self.pos()[1], "")


class TestParada(GuardBase):
    def test_stop_sem_modulo_de_calibracao_fica_mudo(self):
        self.pos("Write", escrever_plano(self.raiz))
        cod, out = rodar_guard({"hook_event_name": "Stop", "session_id": self.sid,
                                "transcript_path": self.transcript}, self.tmp.name)
        self.assertEqual((cod, out), (0, ""))


if __name__ == "__main__":
    unittest.main()
