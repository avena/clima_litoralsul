"""Garante o parsing e agregação da fonte NASA POWER sem dependência de rede."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from fontes import nasa_power

FIXTURES = Path(__file__).parent / "fixtures"


def ler_fixture(nome: str) -> dict:
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


class TestNasaPower(unittest.TestCase):
    """Garante contratos de extração e sentinelas da NASA POWER."""

    def test_catalogo_pontos_virtuais(self):
        """Catálogo retorna 4 municípios costeiros desprovidos de estação com tipo 'reanalise'."""
        pontos = nasa_power.pontos()
        self.assertEqual(len(pontos), 4)
        municipios = {p["municipio"] for p in pontos}
        self.assertEqual(municipios, {"Itanhaém", "Mongaguá", "Peruíbe", "Ilha Comprida"})
        for p in pontos:
            self.assertTrue(p["id"].startswith("nasa:"))
            self.assertEqual(p["tipo"], "reanalise")

    def test_sentinela_ausente_vira_none(self):
        """Valores -999.0 ou menores que -900 viram None, nunca 0."""
        self.assertIsNone(nasa_power._limpar(-999.0))
        self.assertIsNone(nasa_power._limpar(-999))
        self.assertIsNone(nasa_power._limpar(None))
        self.assertEqual(nasa_power._limpar(25.4), 25.4)
        self.assertEqual(nasa_power._limpar(0.0), 0.0)

    def test_parse_diario_com_fixture(self):
        """Extrai observações diárias canônicas a partir do fixture offline."""
        dados = ler_fixture("nasa_power_point.json")
        fatos = list(nasa_power._parse_resposta(dados, "Ilha Comprida (NASA POWER)", diario=True))
        self.assertEqual(len(fatos), 5)
        primeiro = fatos[0]
        self.assertEqual(primeiro["nome"], "Ilha Comprida (NASA POWER)")
        self.assertEqual(primeiro["data"], "2024-01-01")
        self.assertEqual(primeiro["chuva"], 1.02)
        self.assertEqual(primeiro["tmed"], 25.28)
        self.assertEqual(primeiro["tmin"], 21.83)
        self.assertEqual(primeiro["tmax"], 30.03)
        self.assertEqual(primeiro["urmed"], 73.18)

    def test_parse_mensal_agrega_corretamente(self):
        """Agregação mensal soma chuva e tira média de temperatura e umidade."""
        dados = ler_fixture("nasa_power_point.json")
        fatos = list(nasa_power._parse_resposta(dados, "Ilha Comprida (NASA POWER)", diario=False))
        self.assertEqual(len(fatos), 1)
        mes = fatos[0]
        self.assertEqual(mes["data"], "2024-01")
        self.assertEqual(mes["chuva"], 17.9)
        self.assertIsNotNone(mes["tmed"])


if __name__ == "__main__":
    unittest.main()
