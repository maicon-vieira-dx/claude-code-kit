import json
import os
import sys
import tempfile
import unittest

import apoio  # noqa: F401, I001 — vem antes: é ele que põe scripts/ no sys.path
import acumulo
import plano as planos
from apoio import chamada, escrever_plano, escrever_transcript, rodar_guard


def payload(ferramenta, resposta=None, **ti):
    return {"tool_name": ferramenta, "tool_input": ti, "tool_response": resposta}


class TestAvaliar(unittest.TestCase):
    def test_read_grande_avisa_com_o_remedio(self):
        avisos = acumulo.avaliar(payload("Read", {"file": {"content": "x" * 30000}}), {}, None, None)
        chave, ctx, _ = avisos[0]
        self.assertEqual(chave, "acumulo-Read")
        self.assertIn("offset", ctx)

    def test_saida_pequena_nao_avisa(self):
        self.assertEqual(acumulo.avaliar(payload("Bash", {"stdout": "ok"}), {}, None, None), [])

    def test_ferramenta_fora_da_lista_nao_avisa(self):
        self.assertEqual(acumulo.avaliar(payload("Edit", "x" * 90000), {}, None, None), [])

    def test_exit_plan_mode_longo_avisa(self):
        avisos = acumulo.avaliar(payload("ExitPlanMode", plan="p" * 4000), {}, None, None)
        self.assertEqual(avisos[0][0], "acumulo-exitplan")

    def test_exit_plan_mode_curto_nao_avisa(self):
        self.assertEqual(acumulo.avaliar(payload("ExitPlanMode", plan="resumo"), {}, None, None), [])

    def test_projecao_usa_as_chamadas_restantes_do_plano(self):
        with tempfile.TemporaryDirectory() as tmp:
            plano = planos.ler_plano(escrever_plano(tmp))
            if "checkpoint" not in sys.modules:
                try:
                    import checkpoint  # noqa: F401
                except ImportError:
                    self.skipTest("checkpoint.py (plano 013) ausente")
            avisos = acumulo.avaliar(payload("Bash", {"stdout": "y" * 30000}), {"calls": 5}, None, plano)
            self.assertIn("~20 chamadas restantes", avisos[0][1])


class TestPeloGuard(unittest.TestCase):
    def test_avisa_uma_vez_por_ferramenta_na_sessao(self):
        with tempfile.TemporaryDirectory() as tmp:
            transcript = escrever_transcript(os.path.join(tmp, "s.jsonl"), [chamada(80000)])
            base = {"hook_event_name": "PostToolUse", "session_id": "ac", "transcript_path": transcript,
                    "tool_name": "Read", "tool_input": {"file_path": "x.ts"}}
            rodar_guard({**base, "tool_response": {}}, tmp)
            _, out = rodar_guard({**base, "tool_response": {"content": "z" * 30000}}, tmp)
            self.assertIn("Esta saída de Read", json.loads(out)["hookSpecificOutput"]["additionalContext"])
            self.assertEqual(rodar_guard({**base, "tool_response": {"content": "z" * 30000}}, tmp)[1], "")


if __name__ == "__main__":
    unittest.main()
