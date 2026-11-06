import os
import subprocess
import sys
import tempfile
import unittest

import apoio  # noqa: F401
import calibracao
import contexto
import plano as planos
from apoio import SCRIPTS, chamada, escrever_plano, escrever_transcript, rodar_guard


def medida(base=77000, atual=200000, escrita=77000, releitura=900000):
    return contexto.Medida(base, atual, atual + 10000, 40, releitura, escrita, 0, 1, "m")


class CalibracaoBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.livro = os.path.join(self.tmp.name, "calibracao.tsv")
        os.environ["PLANGEN_LEDGER"] = self.livro
        self.addCleanup(os.environ.pop, "PLANGEN_LEDGER", None)
        self.plano = planos.ler_plano(escrever_plano(self.tmp.name))

    def registrar(self, sid, calls=30, vinculado_por="escrita", **kw):
        estado = {"calls": calls, "ctx_inv": 90000, "releitura_inv": 100000, "vinculado_por": vinculado_por,
                  "checkpoints_recomendados": 1}
        calibracao.registrar(sid, estado, medida(**kw), self.plano)


class TestRegistrar(CalibracaoBase):
    def test_sobrescreve_a_linha_da_mesma_sessao(self):
        self.registrar("s1", calls=10)
        self.registrar("s1", calls=25)
        self.registrar("s2", calls=5)
        linhas = calibracao.ler()
        self.assertEqual([(r["sessao"], r["calls"]) for r in linhas], [("s1", "25"), ("s2", "5")])
        self.assertEqual((linhas[0]["sujo_inicial"], linhas[0]["releitura"]), ("13000", "800000"))

    def test_pasta_do_livro_ausente_nao_grava_nem_quebra(self):
        os.environ["PLANGEN_LEDGER"] = os.path.join(self.tmp.name, "nao", "existe.tsv")
        self.registrar("s1")
        self.assertEqual(calibracao.ler(), [])


class TestFracao(CalibracaoBase):
    def test_menos_de_tres_retomadas_devolve_none(self):
        self.registrar("a", vinculado_por="leitura", escrita=20000)
        self.registrar("b", vinculado_por="leitura", escrita=30000)
        self.registrar("c", vinculado_por="escrita", escrita=77000)
        self.assertIsNone(calibracao.fracao_base_reescrita())

    def test_mediana_das_retomadas_limitada_a_um(self):
        for sid, escrita in (("a", 7700), ("b", 38500), ("c", 154000)):
            self.registrar(sid, vinculado_por="leitura", escrita=escrita)
        self.assertAlmostEqual(calibracao.fracao_base_reescrita(), 0.5)


class TestLinhaD0(CalibracaoBase):
    def test_soma_as_chamadas_de_todas_as_sessoes_do_plano(self):
        self.registrar("s1", calls=30)
        self.registrar("s2", calls=12, vinculado_por="leitura")
        linha = calibracao.linha_d0_do_plano(self.plano.caminho)
        self.assertTrue(linha.startswith("D0: previsto 40 / real 42"))
        self.assertIn("2 sessão(ões)", linha)

    def test_cli_sem_registro_sai_1(self):
        proc = subprocess.run([sys.executable, os.path.join(SCRIPTS, "calibracao.py"), "--plano", "x.md"],
                              capture_output=True, env={**os.environ, "PLANGEN_LEDGER": self.livro})
        self.assertEqual(proc.returncode, 1)

    def test_resumo_sem_retomadas_avisa_o_conservador(self):
        self.registrar("s1", calls=80)
        texto = calibracao.resumo()
        self.assertIn("real ÷ previsto (D0_total), mediana: 2.00", texto)
        self.assertIn("checkpoint usa 1,0", texto)


class TestPeloGuard(CalibracaoBase):
    def test_stop_com_plano_vinculado_grava_o_livro(self):
        transcript = escrever_transcript(os.path.join(self.tmp.name, "s.jsonl"), [
            chamada(77000, w1h=77000), chamada(100000, lido=77000, w1h=23000)])
        base = {"session_id": "cal", "transcript_path": transcript}
        env = {"PLANGEN_LEDGER": self.livro}
        rodar_guard({**base, "hook_event_name": "PostToolUse", "tool_name": "Write",
                     "tool_input": {"file_path": self.plano.caminho}, "tool_response": {}}, self.tmp.name, env)
        self.assertEqual(rodar_guard({**base, "hook_event_name": "Stop"}, self.tmp.name, env), (0, ""))
        self.assertEqual(calibracao.ler()[0]["sessao"], "cal")


if __name__ == "__main__":
    unittest.main()
