import json
import os
import sys
import tempfile
import types
import unittest

import apoio  # noqa: F401
import checkpoint
import contexto
import plano as planos
from apoio import chamada, escrever_plano, escrever_transcript, rodar_guard


def medida(base=77000, atual=260000):
    return contexto.Medida(base, atual, atual, 50, 0, base, 0, 1, "m")


class CheckpointBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        contexto._tarifas = types.ModuleType("falso")
        contexto._tarifas.MODELOS = {"m": (2.0, 10.0, "M")}
        contexto._tarifas.CACHE_READ = {}
        self.addCleanup(setattr, contexto, "_tarifas", False)
        sys.modules.pop("calibracao", None)

    def plano(self, **kw):
        return planos.ler_plano(escrever_plano(self.tmp.name, **kw))


class TestCallsRestantes(CheckpointBase):
    def test_sem_passo_fechado_usa_o_resto_da_d0(self):
        estado = {"calls": 12, "calls_no_vinculo": 2}
        self.assertEqual(checkpoint.calls_restantes(estado, self.plano(passos="0 de 4")), 15)

    def test_com_passo_fechado_extrapola_a_taxa_real(self):
        estado = {"calls": 32, "calls_no_vinculo": 2, "passos_no_vinculo": [0, 5]}
        self.assertEqual(checkpoint.calls_restantes(estado, self.plano(passos="2 de 5")), 45)

    def test_na_retomada_so_conta_os_passos_desta_sessao(self):
        estado = {"calls": 10, "calls_no_vinculo": 0, "passos_no_vinculo": [2, 5]}
        self.assertEqual(checkpoint.calls_restantes(estado, self.plano(passos="3 de 5")), 20)

    def test_plano_fechado_devolve_none(self):
        self.assertIsNone(checkpoint.calls_restantes({"calls": 9}, self.plano(passos="5 de 5")))


class TestAvaliar(CheckpointBase):
    def test_janela_grande_e_muito_trabalho_pela_frente_compensa(self):
        estado = {"calls": 0, "calls_no_vinculo": 0}
        avisos = checkpoint.avaliar(estado, medida(), self.plano(d0="~40 (execução: ~40 · já gastas: ~0)"))
        self.assertEqual(len(avisos), 1)
        chave, ctx, usuario = avisos[0]
        self.assertEqual(chave, "checkpoint-0")
        self.assertIn("CHECKPOINT COMPENSA (antes de executar)", ctx)
        self.assertIn("/plan-generation retomar teste", ctx)
        self.assertEqual(estado["checkpoints_recomendados"], 1)

    def test_janela_quase_limpa_nao_compensa_mas_registra_a_conta(self):
        estado = {"calls": 0}
        self.assertEqual(checkpoint.avaliar(estado, medida(atual=107000), self.plano()), [])
        conta = estado["contas"][0]
        self.assertEqual((conta["excedente"], conta["base_reescrita"], conta["razao"]), (30000, 77000, 20.0))
        self.assertLessEqual(conta["ganho"], conta["custo"])

    def test_arquivos_alvo_entram_no_restabelecer(self):
        alvo = os.path.join(self.tmp.name, "grande.ts")
        with open(alvo, "w") as fh:
            fh.write("x" * 23500)
        estado = {"calls": 0}
        checkpoint.avaliar(estado, medida(), self.plano(alvos=("grande.ts",)))
        self.assertGreaterEqual(estado["contas"][0]["restabelecer"], 10000)

    def test_fracao_medida_pela_calibracao_substitui_a_base_inteira(self):
        sys.modules["calibracao"] = types.SimpleNamespace(fracao_base_reescrita=lambda: 0.25)
        self.addCleanup(sys.modules.pop, "calibracao", None)
        estado = {"calls": 0}
        checkpoint.avaliar(estado, medida(), self.plano())
        self.assertEqual(estado["contas"][0]["base_reescrita"], 19250)

    def test_plano_fechado_nao_avalia(self):
        estado = {"calls": 30}
        self.assertEqual(checkpoint.avaliar(estado, medida(), self.plano(passos="4 de 4")), [])
        self.assertNotIn("contas", estado)


class TestPeloGuard(CheckpointBase):
    def test_gravar_o_plano_com_janela_suja_recomenda_checkpoint_de_entrada(self):
        raiz = os.path.join(self.tmp.name, "repo")
        transcript = escrever_transcript(os.path.join(self.tmp.name, "s.jsonl"), [
            chamada(77000, w1h=77000), chamada(250000, lido=77000, w1h=173000),
        ])
        plano = escrever_plano(raiz, d0="~60 tool calls (execução: ~60 · já gastas: ~0)",
                               regime="fora — break-even: 30k × 60 = 1800000 > 400000, solo medido")
        base = {"session_id": "ck", "transcript_path": transcript, "hook_event_name": "PostToolUse", "tool_response": {}}
        rodar_guard({**base, "tool_name": "Bash", "tool_input": {"command": "ls"}}, self.tmp.name)
        _, out = rodar_guard({**base, "tool_name": "Write", "tool_input": {"file_path": plano}}, self.tmp.name)
        saida = json.loads(out)
        self.assertIn("CHECKPOINT COMPENSA (antes de executar)", saida["hookSpecificOutput"]["additionalContext"])
        self.assertIn("/plan-generation retomar teste", saida["systemMessage"])


if __name__ == "__main__":
    unittest.main()
