"""Testes do extrator e do banco, sobre HTML real salvo em tests/fixtures.

Os fixtures foram baixados em 2026-10-30 e são a única verdade sobre o formato
da página. Se o CIIAGRO mudar o HTML, estes testes quebram — que é o ponto.

Nenhum teste toca a rede: `linhas`, `inicios`, `codigos` e `coordenadas` são
funções puras sobre texto, e o banco roda em arquivo temporário.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import coletor
import municipios
from fontes import ciiagro

FIXTURES = Path(__file__).parent / "fixtures"


def ler(nome: str) -> str:
    """Lê um fixture como texto, removendo o BOM que o CIIAGRO envia.

    Args:
        nome: arquivo dentro de `tests/fixtures/`.

    Returns:
        Conteúdo decodificado em UTF-8.

    Nota:
        O site responde com BOM (`\\ufeff`), e sem `utf-8-sig` o primeiro `<`
        do arquivo vira lixo e o primeiro regex falha.
    """
    return (FIXTURES / nome).read_text(encoding="utf-8-sig")


class TestExtracao(unittest.TestCase):
    """Garante que o regex extrai os números certos do HTML real."""

    def test_diario_tem_todas_as_estacoes_do_dia(self):
        """`cdiaria` traz 18 estações no dia 29/10/2026.

        Protege contra regressão no casamento união das três tabelas: a lista
        final é a união de temperatura, umidade e chuva, então estação que só
        reporta um dos três continua entrando.
        """
        linhas = ciiagro.linhas(ler("cdiaria.html"))
        self.assertEqual(len(linhas), 18)

    def test_diario_valores_conferem_com_a_pagina(self):
        """Os valores de Apiaí batem com a tabela publicada, coluna por coluna.

        Verifica posição e escala: se o extrator trocar tmin com tmax, ou ler
        a coluna de umidade como temperatura, isto quebra.
        """
        apiai = {l["nome"]: l for l in ciiagro.linhas(ler("cdiaria.html"))}["Apiaí"]
        self.assertAlmostEqual(apiai["tmin"], 12.95)
        self.assertAlmostEqual(apiai["tmed"], 16.795)
        self.assertAlmostEqual(apiai["tmax"], 20.64)
        self.assertAlmostEqual(apiai["chuva"], 1.016)
        self.assertAlmostEqual(apiai["urmin"], 72.4)

    def test_mensal_uma_linha_por_estacao(self):
        """`cmensal` devolve uma linha por estação (7 em 01/2001), não por dia.

        O mensal e o diário usam o mesmo extrator; este teste garante que o
        formato de data diferente não muda a quantidade de linhas.
        """
        linhas = ciiagro.linhas(ler("cmensal.html"))
        self.assertEqual(len(linhas), 7)
        cananeia = {l["nome"]: l for l in linhas}["Cananéia"]
        self.assertAlmostEqual(cananeia["tmed"], 26.09)
        self.assertAlmostEqual(cananeia["chuva"], 329.6, places=3)

    def test_umidade_zero_em_2001_nao_vira_medicao(self):
        """Documenta a armadilha: o site usa `0.00` para "sem sensor".

        O extrator não inventa: preserva o `0.0`. Quem denuncia é `auditar`.
        Se algum dia o extrator passar a converter `0` em `NULL`, este teste
        precisa mudar junto com a decisão — ele existe para a mudança ser
        consciente, não acidental.
        """
        cananeia = {l["nome"]: l for l in ciiagro.linhas(ler("cmensal.html"))}["Cananéia"]
        self.assertEqual(cananeia["urmed"], 0.0)

    def test_calendario_traz_inicio_de_cada_estacao(self):
        """`/calendario` entrega as 23 estações com a data de início em ISO.

        A data vem `dd/mm/aaaa` na página e sai `AAAA-MM-DD` para comparar com
        `fato.data`; a inversão dos campos é o erro fácil aqui.
        """
        inicios = ciiagro.inicios(ler("calendario.html"))
        self.assertEqual(len(inicios), 23)
        self.assertEqual(inicios["Registro"], "2005-10-11")
        self.assertEqual(inicios["Cananéia"], "2000-08-31")

    def test_periodo_traz_o_codigo_numerico(self):
        """`/diario/periodo` é a única página que dá o código numérico da estação.

        O código é a chave primária de `ponto`; sem ele, nenhuma coleta pode ser
        amarrada a uma estação.
        """
        codigos = ciiagro.codigos(ler("periodo.html"))
        self.assertEqual(len(codigos), 23)
        self.assertEqual(codigos["Registro"], "63")

    def test_marcadores_do_mapa_dao_coordenadas(self):
        """As coordenadas saem do `L.marker([lat,lon], {title:"Nome"})` do mapa.

        Evita geocodificação externa: a lat/lon vem do próprio HTML, na ordem
        latitude, longitude.
        """
        geo = ciiagro.coordenadas(ler("estacoes.html"))
        self.assertEqual(len(geo), 23)
        self.assertEqual(geo["Cananéia"], (-25.0202, -47.925))


class TestPeriodos(unittest.TestCase):
    """Garante a geração da lista de requisições entre dois extremos."""

    def test_meses_inclusivos(self):
        """A virada de ano é inclusiva nas duas pontas.

        `2000-11` a `2001-02` tem de dar exatamente 4 meses; um off-by-one aqui
        silenciosamente perde dezembro ou duplica janeiro na série.
        """
        self.assertEqual(ciiagro._chaves("2000-11", "2001-02", False),
                         ["2000-11", "2000-12", "2001-01", "2001-02"])

    def test_dias_inclusivos(self):
        """A contagem de dias atravessa a virada de mês, inclusiva."""
        self.assertEqual(ciiagro._chaves("2026-10-30", "2026-11-01", True),
                         ["2026-10-30", "2026-10-31", "2026-11-01"])


class TestMunicipios(unittest.TestCase):
    """Garante o casamento entre nome de estação e os 17 municípios."""

    def test_dezessete_municipios(self):
        """O CSV tem que ter exatamente os 17 da mesorregião.

        Se alguém adicionar ou remover linha, o relatório passa a prometer
        cobertura que não existe.
        """
        self.assertEqual(len(municipios.todos()), 17)

    def test_nome_exato(self):
        """Nome igual ao do município resolve direto, inclusive com acento."""
        self.assertEqual(municipios.resolver("Cananéia"), "Cananéia")
        self.assertEqual(municipios.resolver("Itanhaém"), "Itanhaém")

    def test_sufixo_de_estacao(self):
        """Sufixo institucional ou numérico é descartado, não vira município novo.

        "Registro Unesp" e "Pariquera-Açu 2" são a mesma cidade que "Registro"
        e "Pariquera-Açu"; tratá-las como município separado duplicaria a série.
        """
        self.assertEqual(municipios.resolver("Registro Unesp"), "Registro")
        self.assertEqual(municipios.resolver("Pariquera-Açu 2"), "Pariquera-Açu")

    def test_estacao_fora_dos_17(self):
        """Estação de município vizinho fica sem município, e isso não é erro.

        Elas continuam no banco como referência; o que não pode é entrar no
        relatório de um dos 17 municípios.
        """
        for fora in ("Apiaí", "Juquitiba", "Ribeira", "Tapiraí", "Itaóca"):
            self.assertIsNone(municipios.resolver(fora), fora)


class TestBanco(unittest.TestCase):
    """Garante as invariantes de gravação, em banco temporário."""

    def setUp(self):
        """Cria banco temporário com um município e uma estação."""
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = coletor.abrir(Path(self.tmp.name) / "t.sqlite")
        self.conn.execute("INSERT INTO municipio(nome, microrregiao) VALUES('Registro','Registro')")
        self.conn.execute(
            "INSERT INTO ponto(id, fonte, nome, municipio_id) VALUES('63','ciiagro','Registro',1)")

    def tearDown(self):
        """Fecha a conexão e apaga o arquivo temporário."""
        self.conn.close()
        self.tmp.cleanup()

    def _grava(self, data, chuva):
        """Insere uma linha de chuva com o mesmo UPSERT usado pela coleta.

        Args:
            data: `AAAA-MM` ou `AAAA-MM-DD`.
            chuva: milímetros.
        """
        self.conn.execute(
            "INSERT INTO fato(ponto_id, data, chuva) VALUES('63', ?, ?) "
            "ON CONFLICT(ponto_id, data) DO UPDATE SET chuva = COALESCE(excluded.chuva, chuva)",
            (data, chuva))

    def test_upsert_nao_duplica(self):
        """Recoletar o mesmo período mantém uma única linha.

        É o que permite rodar a coleta duas vezes sem inflar a série — e o que
        torna a retomada por `MAX(data)` segura.
        """
        self._grava("2026-10", 10.0)
        self._grava("2026-10", 10.0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM fato").fetchone()[0], 1)

    def test_mes_e_dia_nao_convivem_no_mesmo_mes(self):
        """Coletar diário depois de mensal apaga o total do mês.

        Sem isso, um `SUM(chuva)` por mês somaria o total mensal com os dias do
        mesmo mês, dobrando a chuva. A soma dos dias tem de continuar sendo o
        total que estava no mês.
        """
        self._grava("2026-10", 10.0)
        coletor.substituir_granularidade(self.conn, {("63", "2026-10")}, diario=True)
        self._grava("2026-10-01", 4.0)
        self._grava("2026-10-02", 6.0)
        linhas = self.conn.execute("SELECT data, chuva FROM fato ORDER BY data").fetchall()
        self.assertEqual([r["data"] for r in linhas], ["2026-10-01", "2026-10-02"])
        self.assertEqual(sum(r["chuva"] for r in linhas), 10.0)

    def test_mensal_apaga_os_dias_do_mes(self):
        """A invariante vale nos dois sentidos: mensal remove os dias do mês."""
        self._grava("2026-10-01", 4.0)
        self._grava("2026-10-02", 6.0)
        coletor.substituir_granularidade(self.conn, {("63", "2026-10")}, diario=False)
        self.assertEqual(self.conn.execute("SELECT data FROM fato").fetchall(), [])

    def test_primeiro_fato_recalcula_para_tras(self):
        """`primeiro_fato` é o menor `data` do banco, mesmo coletado fora de ordem.

        Regressão real: com `COALESCE(primeiro_fato, ?)` o primeiro lote
        congelava o valor, e coletar 1995 depois de 2005 deixava a estação
        marcada como começando em 2005. A auditoria depende deste valor para
        acusar série anterior ao início da estação.
        """
        self._grava("2005-10", 1.0)
        coletor.atualizar_primeiro_fato(self.conn)
        self.assertEqual(self.conn.execute("SELECT primeiro_fato FROM ponto").fetchone()[0],
                         "2005-10")
        self._grava("1995-01", 2.0)
        coletor.atualizar_primeiro_fato(self.conn)
        self.assertEqual(self.conn.execute("SELECT primeiro_fato FROM ponto").fetchone()[0],
                         "1995-01")


if __name__ == "__main__":
    unittest.main()
