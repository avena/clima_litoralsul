"""Testes do módulo de dados históricos do INMET (dadoshistoricosinmet)."""
import sqlite3
import unittest

from dadoshistoricosinmet.processar import _to_num, parse_csv_estacao, sanitizar_extremos


class TestDadosHistoricosINMET(unittest.TestCase):
    """Garante parsing correto de formatos, números e agregação diária do INMET."""

    def test_to_num(self):
        """Garante conversão de vírgula para ponto e sentinelas em None."""
        self.assertEqual(_to_num("23,4"), 23.4)
        self.assertEqual(_to_num(",4"), 0.4)
        self.assertEqual(_to_num("-12,5"), -12.5)
        self.assertIsNone(_to_num(""))
        self.assertIsNone(_to_num("-9999"))
        self.assertIsNone(_to_num("-999"))
        self.assertIsNone(_to_num("invalid"))

    def test_parse_csv_estacao(self):
        """Garante extração de metadados e agregação de registros horários."""
        csv_ficticio = (
            "REGIAO:;SE\n"
            "UF:;SP\n"
            "ESTACAO:;TESTE ESTACAO\n"
            "CODIGO (WMO):;A999\n"
            "LATITUDE:;-24,50\n"
            "LONGITUDE:;-47,80\n"
            "ALTITUDE:;10,5\n"
            "DATA DE FUNDACAO:;01/01/2000\n"
            "Data;Hora UTC;PRECIPITAÇÃO TOTAL, HORÁRIO (mm);PRESSAO;PMAX;PMIN;RAD;"
            "TEMPERATURA DO AR - BULBO SECO, HORARIA (°C);PONTO ORV;"
            "TEMPERATURA MÁXIMA NA HORA ANT. (AUT) (°C);"
            "TEMPERATURA MÍNIMA NA HORA ANT. (AUT) (°C);ORV_MAX;ORV_MIN;"
            "UR_MAX;UR_MIN;UMIDADE RELATIVA DO AR, HORARIA (%);VENTO_DIR;VENTO_RAJ;VENTO_VEL;\n"
            "2023/01/01;0000 UTC;5,2;;;;;20,0;;21,0;19,0;;;;;80;;;\n"
            "2023/01/01;1200 UTC;0;;;;;25,0;;26,0;24,0;;;;;70;;;\n"
            "2023/01/02;0000 UTC;-9999;;;;;-9999;;-9999;-9999;;;;;-9999;;;\n"
        ).encode("latin-1")

        est, diarios = parse_csv_estacao(csv_ficticio)

        self.assertEqual(est["codigo"], "A999")
        self.assertEqual(est["nome"], "TESTE ESTACAO")
        self.assertEqual(est["lat"], -24.50)
        self.assertEqual(est["lon"], -47.80)
        self.assertEqual(est["altitude"], 10.5)

        self.assertEqual(len(diarios), 2)
        # Dia 1 tem dados
        d1 = diarios[0]
        self.assertEqual(d1["data"], "2023-01-01")
        self.assertEqual(d1["chuva"], 5.2)
        self.assertEqual(d1["tmed"], 22.5)  # (20 + 25) / 2
        self.assertEqual(d1["tmax"], 26.0)
        self.assertEqual(d1["tmin"], 19.0)
        self.assertEqual(d1["urmed"], 75.0)

        # Dia 2 foi todo -9999
        d2 = diarios[1]
        self.assertEqual(d2["data"], "2023-01-02")
        self.assertIsNone(d2["tmed"])
        self.assertIsNone(d2["chuva"])


class TestSanitizarExtremos(unittest.TestCase):
    """O filtro de extremos tira o pico do sensor sem apagar frio real."""

    def _banco(self, linhas):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE inmet_mensal "
            "(codigo TEXT, mes TEXT, chuva REAL, tmed REAL, tmax REAL, tmin REAL)"
        )
        conn.executemany(
            "INSERT INTO inmet_mensal VALUES (?, ?, 100.0, 22.0, ?, ?)", linhas
        )
        return conn

    def test_pico_fora_da_serie_do_mes_vira_null(self):
        """Um 45,0 °C isolado em dezembro não sobrevive como máxima do mês."""
        conn = self._banco(
            [("A201", f"{ano}-12", 34.0, 22.0) for ano in range(2000, 2006)]
            + [("A201", "2005-12", 45.0, 0.0)]
        )
        self.assertEqual(sanitizar_extremos(conn), 2)
        linha = conn.execute(
            "SELECT tmax, tmin, tmed, chuva FROM inmet_mensal "
            "WHERE mes = '2005-12'"
        ).fetchone()
        self.assertEqual(linha, (None, None, 22.0, 100.0))

    def test_frio_real_abaixo_de_menos_cinco_fica(self):
        """Mínima de −5 °C dentro da variabilidade da estação é clima, não lixo."""
        conn = self._banco(
            [("A850", f"{ano}-07", 18.0, valor)
             for ano, valor in zip(range(2000, 2006), (-4.0, -5.0, -6.0, -7.0, -5.5))]
            + [("A850", "2006-07", 17.0, -5.0)]
        )
        self.assertEqual(sanitizar_extremos(conn), 0)
        self.assertEqual(
            conn.execute(
                "SELECT tmin FROM inmet_mensal WHERE mes = '2006-07'"
            ).fetchone()[0],
            -5.0,
        )


if __name__ == "__main__":
    unittest.main()
