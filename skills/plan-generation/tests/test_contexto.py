import os
import tempfile
import types
import unittest

import apoio  # noqa: F401 — põe scripts/ no sys.path
import contexto
from apoio import chamada, escrever_transcript


class TestMedir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.arq = os.path.join(self.tmp.name, "s.jsonl")

    def test_base_atual_pico_e_releitura_da_thread_principal(self):
        escrever_transcript(self.arq, [
            chamada(80000, w1h=80000),
            chamada(120000, lido=80000, w1h=40000, duplicada=True),
            chamada(999999, lido=1, sidechain=True),
            chamada(110000, lido=100000, w1h=10000),
        ])
        m = contexto.medir(self.arq)
        self.assertEqual((m.base, m.atual, m.pico, m.chamadas), (80000, 110000, 120000, 3))
        self.assertEqual(m.releitura_total, 180000)
        self.assertEqual(m.escrita_primeira, 80000)
        self.assertEqual(m.excedente, 30000)

    def test_linha_ilegivel_e_pulada(self):
        escrever_transcript(self.arq, [chamada(50000)])
        with open(self.arq, "a", encoding="utf-8") as fh:
            fh.write('{"type":"assistant","message":{"usage": {corrompido\n')
        self.assertEqual(contexto.medir(self.arq).chamadas, 1)

    def test_sem_arquivo_ou_sem_chamada_devolve_none(self):
        self.assertIsNone(contexto.medir(os.path.join(self.tmp.name, "nao-existe.jsonl")))
        open(self.arq, "w").close()
        self.assertIsNone(contexto.medir(self.arq))

    def test_excedente_nunca_negativo(self):
        escrever_transcript(self.arq, [chamada(90000), chamada(70000)])
        self.assertEqual(contexto.medir(self.arq).excedente, 0)


class TestTokens(unittest.TestCase):
    def test_bytes_para_tokens_pela_razao_medida(self):
        self.assertEqual(contexto.tokens_de_bytes(2350), 1000)

    def test_arquivo_ausente_vale_zero(self):
        self.assertEqual(contexto.tokens_de_arquivo("Z:/nao/existe.ts"), 0)


class TestRazao(unittest.TestCase):
    def tearDown(self):
        contexto._tarifas = False

    def medida(self, modelo, w5=0, w1h=1):
        return contexto.Medida(0, 0, 0, 1, 0, 0, w5, w1h, modelo)

    def com_tarifas(self, modelos, cache_read=None):
        contexto._tarifas = types.ModuleType("falso")
        contexto._tarifas.MODELOS = modelos
        contexto._tarifas.CACHE_READ = cache_read or {}

    def test_ttl_1h_na_regra_geral_vale_20(self):
        self.com_tarifas({"m": (2.0, 10.0, "M")})
        self.assertAlmostEqual(contexto.razao_escrita_leitura(self.medida("m")), 20.0)

    def test_ttl_5m_vale_12_e_meio(self):
        self.com_tarifas({"m": (2.0, 10.0, "M")})
        self.assertAlmostEqual(contexto.razao_escrita_leitura(self.medida("m", w5=10, w1h=1)), 12.5)

    def test_leitura_mais_barata_que_a_regra_geral_aumenta_a_razao(self):
        self.com_tarifas({"o": (4.0, 20.0, "O")}, {"o": 0.20})
        self.assertAlmostEqual(contexto.razao_escrita_leitura(self.medida("o")), 40.0)

    def test_modelo_sem_tarifa_cai_na_razao_padrao(self):
        self.com_tarifas({})
        self.assertEqual(contexto.razao_escrita_leitura(self.medida("x")), contexto.RAZAO_PADRAO)

    @unittest.skipUnless(os.path.isfile(contexto.TURN_COST), "turn-cost.py ausente nesta máquina")
    def test_tarifa_real_do_turn_cost(self):
        self.assertAlmostEqual(contexto.razao_escrita_leitura(self.medida("claude-sonnet-5-5")), 20.0)


class TestCli(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "o slug de exemplo é um caminho Windows")
    def test_slug_troca_todo_caractere_nao_alfanumerico(self):
        self.assertEqual(
            contexto.slug_do_projeto("C:\\Users\\fulano.silva_x\\Documents\\Projetos\\meu-app"),
            "C--Users-fulano-silva-x-Documents-Projetos-meu-app",
        )

    def test_cli_mede_um_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            arq = escrever_transcript(os.path.join(tmp, "s.jsonl"), [chamada(70000), chamada(90000)])
            self.assertEqual(contexto.main([arq]), 0)
            self.assertEqual(contexto.main([os.path.join(tmp, "nada.jsonl")]), 1)
            self.assertEqual(contexto.main([]), 2)


if __name__ == "__main__":
    unittest.main()
