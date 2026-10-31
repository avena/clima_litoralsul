"""Garante o parsing e agregação da fonte INMET sem dependência de rede."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from fontes import inmet

FIXTURES = Path(__file__).parent / "fixtures"


def ler_fixture(nome: str) -> list[dict]:
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


class TestInmet(unittest.TestCase):
    """Garante contratos de extração e agregação horária do INMET."""

    def test_conversao_numerica_e_sentinelas(self):
        """Trata vírgulas, vazios e sentinelas do INMET como None."""
        self.assertEqual(inmet._converte_num("24,5"), 24.5)
        self.assertEqual(inmet._converte_num("-24.67166"), -24.67166)
        self.assertIsNone(inmet._converte_num(""))
        self.assertIsNone(inmet._converte_num(None))
        self.assertIsNone(inmet._converte_num("-9999"))
        self.assertIsNone(inmet._converte_num("-999"))

    def test_pontos_locais_retornam_estacoes_do_observatorio(self):
        """Catálogo retorna estações mapeadas com prefixo inmet: e tipo estacao."""
        pontos = inmet.pontos()
        self.assertGreaterEqual(len(pontos), 3)
        codigos = {p["id"] for p in pontos}
        self.assertTrue({"inmet:A712", "inmet:A746", "inmet:A766"}.issubset(codigos))
        for p in pontos:
            self.assertEqual(p["tipo"], "estacao")

    def test_parse_horario_para_diario_e_mensal(self):
        """Agrega medições horárias em diárias e mensais com tratamento de ausentes."""
        linhas = [
            {"DT_MEDICAO": "2024-01-01", "HR_MEDICAO": "0000", "TEM_INS": "22,0", "TEM_MIN": "21,5", "TEM_MAX": "22,5", "UMD_INS": "85", "CHUVA": "2,0"},
            {"DT_MEDICAO": "2024-01-01", "HR_MEDICAO": "1200", "TEM_INS": "28,0", "TEM_MIN": "27,0", "TEM_MAX": "28,5", "UMD_INS": "70", "CHUVA": "3,0"},
            {"DT_MEDICAO": "2024-01-02", "HR_MEDICAO": "1200", "TEM_INS": "25,0", "TEM_MIN": "24,0", "TEM_MAX": "26,0", "UMD_INS": "75", "CHUVA": "0,0"},
        ]
        diarios = list(inmet._parse_horario(linhas, "Iguape (INMET A712)", diario=True))
        self.assertEqual(len(diarios), 2)
        dia1 = diarios[0]
        self.assertEqual(dia1["data"], "2024-01-01")
        self.assertEqual(dia1["tmin"], 21.5)
        self.assertEqual(dia1["tmax"], 28.5)
        self.assertEqual(dia1["chuva"], 5.0)

        mensais = list(inmet._parse_horario(linhas, "Iguape (INMET A712)", diario=False))
        self.assertEqual(len(mensais), 1)
        mes1 = mensais[0]
        self.assertEqual(mes1["data"], "2024-01")
        self.assertEqual(mes1["chuva"], 5.0)


if __name__ == "__main__":
    unittest.main()
