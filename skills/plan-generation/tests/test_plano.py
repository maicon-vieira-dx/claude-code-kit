import os
import tempfile
import unittest

import apoio  # noqa: F401
import plano as planos
from apoio import escrever_plano


class TestLerPlano(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def ler(self, **kw):
        return planos.ler_plano(escrever_plano(self.tmp.name, **kw))

    def test_solo_sem_conta(self):
        p = self.ler()
        self.assertEqual((p.d3, p.d0_exec, p.d0_total, p.tem_conta), ("solo", 25, 40, False))

    def test_conta_de_break_even_escrita(self):
        p = self.ler(regime="fora — break-even: 30k × 25 = 750000 > 400000 → subagente")
        self.assertTrue(p.tem_conta)

    def test_d3_do_template_e_ambigua(self):
        p = self.ler(d3="eu, mesma janela | subagente por camada, em série | usuário")
        self.assertEqual(p.d3, "ambigua")

    def test_placeholder_nao_conta_como_conta(self):
        p = self.ler(regime="fora — <a conta de break-even é OBRIGATÓRIA aqui>")
        self.assertFalse(p.tem_conta)

    def test_passos_e_alvos(self):
        p = self.ler(alvos=("libs/a/x.ts", "libs/b/y.spec.ts"), passos="2 de 5")
        self.assertEqual(p.passos, (2, 5))
        self.assertEqual(p.alvos, ("libs/a/x.ts", "libs/b/y.spec.ts"))
        self.assertEqual(p.slug, "teste")

    def test_cita_pelo_nome_do_arquivo(self):
        p = self.ler(alvos=("libs/a/alvo.ts",))
        self.assertTrue(p.cita("C:\\repo\\libs\\a\\alvo.ts"))
        self.assertFalse(p.cita("libs/a/alvo.spec.ts"))

    def test_arquivo_ausente_devolve_none(self):
        self.assertIsNone(planos.ler_plano(os.path.join(self.tmp.name, "x.md")))


class TestCaminhoDePlano(unittest.TestCase):
    def test_repo_e_pessoal_sim_readme_e_outros_nao(self):
        self.assertTrue(planos.eh_caminho_de_plano("C:\\repo\\.claude\\plans\\x.md"))
        self.assertTrue(planos.eh_caminho_de_plano("/home/u/.claude/plans/x.md"))
        self.assertFalse(planos.eh_caminho_de_plano("/r/.claude/plans/README.md"))
        self.assertFalse(planos.eh_caminho_de_plano("/r/.claude/plans/x.txt"))
        self.assertFalse(planos.eh_caminho_de_plano("/r/docs/plans/x.md"))


if __name__ == "__main__":
    unittest.main()
