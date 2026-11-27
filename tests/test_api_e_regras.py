"""Suíte de testes automatizados do Aponta e Fala (regras, compositor, guarda e API FastAPI).

Execução:
    python -m unittest discover -s tests -v
"""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import core  # noqa: E402
from compor import compor  # noqa: E402
from guarda import verificar  # noqa: E402


class TestCoreRegras(unittest.TestCase):
    def test_ordenar_coloca_lider_na_frente_e_por_favor_no_fim(self):
        self.assertEqual(core.ordenar(["cabeca", "dor"]), ["dor", "cabeca"])
        self.assertEqual(core.ordenar(["por_favor", "agua", "eu_quero"]), ["eu_quero", "agua", "por_favor"])

    def test_ordenar_prioriza_eu_quero_e_nao_quero_sobre_ajuda(self):
        self.assertEqual(core.ordenar(["ajuda", "eu_quero"]), ["eu_quero", "ajuda"])
        self.assertEqual(core.ordenar(["ajuda", "nao_quero"]), ["nao_quero", "ajuda"])
        self.assertEqual(core.ordenar(["por_favor", "ajuda", "eu_quero"]), ["eu_quero", "ajuda", "por_favor"])

    def test_regras_de_ajuda(self):
        self.assertEqual(core.rule_sentence(["eu_quero", "ajuda"]), "Eu quero ajuda.")
        self.assertEqual(core.rule_sentence(["ajuda", "eu_quero", "por_favor"]), "Eu quero ajuda, por favor.")
        self.assertEqual(core.rule_sentence(["nao_quero", "ajuda"]), "Não quero ajuda.")
        self.assertEqual(core.rule_sentence(["ajuda", "banheiro"]), "Preciso de ajuda para ir ao banheiro.")
        self.assertEqual(core.rule_sentence(["ajuda", "mochila"]), "Preciso de ajuda com a mochila.")
        self.assertEqual(core.rule_sentence(["ajuda", "mamae"]), "Mamãe, preciso de ajuda.")

    def test_regras_de_dor_e_concordancia(self):
        self.assertEqual(core.rule_sentence(["cabeca", "dor"]), "Minha cabeça está doendo.")
        self.assertEqual(core.rule_sentence(["dor", "barriga"]), "Minha barriga está doendo.")
        self.assertEqual(core.rule_sentence(["mamae", "dor", "cabeca"]), "Mamãe, minha cabeça está doendo.")

    def test_regras_de_recipientes_e_acoes(self):
        self.assertEqual(core.rule_sentence(["eu_quero", "copo", "agua"]), "Eu quero um copo de água.")
        self.assertEqual(core.rule_sentence(["agua", "copo", "eu_quero"]), "Eu quero um copo de água.")
        self.assertEqual(core.rule_sentence(["eu_quero", "garrafa", "agua", "por_favor"]), "Eu quero uma garrafa de água, por favor.")
        self.assertEqual(core.rule_sentence(["eu_quero", "banheiro"]), "Eu quero ir ao banheiro.")
        self.assertEqual(core.rule_sentence(["eu_quero", "atividade"]), "Eu quero fazer a atividade.")

    def test_memoria_de_contexto_com_mais(self):
        self.assertEqual(core.sentence_with_context(["mais"], ["eu_quero", "agua"]), "Eu quero mais água.")
        self.assertEqual(core.sentence_with_context(["mais"], ["eu_quero", "lanche"]), "Eu quero mais lanche.")
        self.assertIsNone(core.sentence_with_context(["mais"], []))

    def test_saudacoes_sentimentos_e_lista(self):
        self.assertEqual(core.rule_sentence(["oi", "mamae"]), "Oi, mamãe!")
        self.assertEqual(core.rule_sentence(["feliz", "mamae"]), "Mamãe, estou feliz.")
        self.assertEqual(core.rule_sentence(["terminei", "lanche"]), "Terminei o lanche.")
        self.assertEqual(core.lista_sentence(["eu_quero", "bola", "agua"]), "Eu quero a bola e água.")
        self.assertEqual(core.lista_sentence(["nao_quero", "bola", "agua"]), "Não quero a bola nem água.")

    def test_compositor_e_guarda(self):
        frase = compor(["mamae", "eu_quero", "beber", "agua"])
        self.assertIsNotNone(frase)
        self.assertIn("Mamãe", frase)
        self.assertIn("água", frase.lower())
        self.assertIsNone(verificar(["eu_quero", "agua"], "Eu quero água."))
        self.assertIsNotNone(verificar(["eu_quero", "agua"], "Eu quero a bola."))
        self.assertIsNotNone(verificar(["eu_quero", "agua"], "Eu quero água hoje."))


class TestApiEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi import HTTPException
        import api.main as api_main
        import api.admin as api_admin

        cls.HTTPException = HTTPException
        cls.api_main = api_main
        cls.api_admin = api_admin

    def test_rotas_registradas_e_config(self):
        caminhos = set(self.api_main.app.openapi()["paths"].keys()) | {
            getattr(r, "path", None) for r in self.api_main.app.routes
        }
        for rota in ("/", "/sw.js", "/manifest.webmanifest", "/api/health", "/api/config", "/api/ngram", "/api/next", "/api/speak", "/api/admin/login"):
            self.assertIn(rota, caminhos)

        data = self.api_main.health()
        self.assertTrue(data["ok"])
        self.assertGreaterEqual(data["cards"], 40)

        cfg = self.api_main.config()
        self.assertIn("cards", cfg)
        self.assertIn("rotinas", cfg)
        self.assertIn("sempre_visiveis", cfg)

        ng = self.api_main.ngram()
        self.assertIsInstance(ng, dict)
        self.assertTrue((ROOT / "web" / "sw.js").exists())
        self.assertTrue((ROOT / "web" / "index.html").exists())

    def test_next_retorna_top_4_por_padrao(self):
        entrada = self.api_main.NextIn(rotina="lanche", seq=["eu_quero"])
        self.assertEqual(entrada.k, 4)
        body = self.api_main.nxt(entrada)
        self.assertLessEqual(len(body["sugestoes"]), 4)
        self.assertGreater(len(body["sugestoes"]), 0)

    def test_speak_ordena_aplica_contexto_e_fallback(self):
        b1 = self.api_main.speak(self.api_main.SpeakIn(seq=["cabeca", "dor"], contexto=[]))
        self.assertEqual(b1["ordem"], ["dor", "cabeca"])
        self.assertEqual(b1["frase"], "Minha cabeça está doendo.")

        b2 = self.api_main.speak(self.api_main.SpeakIn(seq=["mais"], contexto=["eu_quero", "agua"]))
        self.assertEqual(b2["frase"], "Eu quero mais água.")

        b3 = self.api_main.speak(self.api_main.SpeakIn(seq=["ajuda", "eu_quero"], contexto=[]))
        self.assertEqual(b3["ordem"], ["eu_quero", "ajuda"])
        self.assertEqual(b3["frase"], "Eu quero ajuda.")

    def test_admin_pin_protecao(self):
        old_pin = os.environ.get("ADMIN_PIN")
        old_prod = os.environ.get("FALAPICTO_PROD")
        try:
            os.environ["FALAPICTO_PROD"] = "1"
            os.environ["ADMIN_PIN"] = "1234"
            with self.assertRaises(self.HTTPException) as ctx_block:
                self.api_admin.login(self.api_admin.Login(pin="1234"))
            self.assertEqual(ctx_block.exception.status_code, 503)

            os.environ["ADMIN_PIN"] = "pin-teste-seguro"
            with self.assertRaises(self.HTTPException) as ctx_err:
                self.api_admin.login(self.api_admin.Login(pin="errado"))
            self.assertEqual(ctx_err.exception.status_code, 401)

            res_ok = self.api_admin.login(self.api_admin.Login(pin="pin-teste-seguro"))
            self.assertTrue(res_ok["ok"])
        finally:
            if old_pin is None:
                os.environ.pop("ADMIN_PIN", None)
            else:
                os.environ["ADMIN_PIN"] = old_pin
            if old_prod is None:
                os.environ.pop("FALAPICTO_PROD", None)
            else:
                os.environ["FALAPICTO_PROD"] = old_prod


if __name__ == "__main__":
    unittest.main()
