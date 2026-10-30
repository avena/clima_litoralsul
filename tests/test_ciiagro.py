"""Testes do extrator e do banco, sobre HTML real salvo em tests/fixtures.

Os fixtures foram baixados em 2026-10-30 e são a única verdade sobre o formato
da página. Se o CIIAGRO mudar o HTML, estes testes quebram — que é o ponto.

Nenhum teste toca a rede: `linhas`, `inicios`, `codigos` e `coordenadas` são
funções puras sobre texto, e o banco roda em arquivo temporário.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import coletor
import municipios
import relatorio
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
    """Garante o casamento entre nome de estação e os 25 municípios."""

    def test_vinte_e_cinco_municipios(self):
        """O CSV tem que ter exatamente os 25 do Litoral Sul e do Vale.

        Se alguém adicionar ou remover linha, o relatório passa a prometer
        cobertura que não existe.
        """
        self.assertEqual(len(municipios.todos()), 25)
        self.assertEqual(municipios.regioes(),
                         ("Litoral Sul", "Vale do Ribeira",
                          "Alto Vale e Cabeceiras"))

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

    def test_estacao_fora_do_escopo(self):
        """Estação de município vizinho fica sem município, e isso não é erro.

        Elas continuam no banco como referência; o que não pode é entrar no
        relatório de um dos 25 municípios.
        """
        for fora in ("Sorocaba", "Santos", "Itapeva", "Pindamonhangaba"):
            self.assertIsNone(municipios.resolver(fora), fora)


class TestBanco(unittest.TestCase):
    """Garante as invariantes de gravação, em banco temporário."""

    def setUp(self):
        """Cria banco temporário com um município e uma estação."""
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = coletor.abrir(Path(self.tmp.name) / "t.sqlite")
        self.conn.execute("INSERT INTO municipio(nome, regiao) VALUES('Registro','Vale do Ribeira')")
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


class TestRelatorio(unittest.TestCase):
    """Garante que o relatório não publique número que o dado não sustenta."""

    def setUp(self):
        """Cria banco temporário com um município e uma estação."""
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = coletor.abrir(Path(self.tmp.name) / "r.sqlite")
        self.conn.execute("INSERT INTO municipio(nome, regiao) VALUES('Registro','Vale do Ribeira')")
        self.conn.execute("INSERT INTO municipio(nome, regiao) VALUES('Itanhaém','Litoral Sul')")
        self.conn.execute(
            "INSERT INTO ponto(id, fonte, nome, municipio_id) VALUES('63','ciiagro','Registro',1)")
    def tearDown(self):
        """Fecha a conexão e apaga o banco temporário."""
        self.conn.close()
        self.tmp.cleanup()

    def _mes(self, data, tmed=20.0, chuva=100.0):
        """Insere um mês de série, com temperatura e chuva."""
        self.conn.execute(
            "INSERT INTO fato(ponto_id, data, tmed, chuva) VALUES('63', ?, ?, ?)",
            (data, tmed, chuva))

    def test_nome_de_arquivo_sem_acento(self):
        """`Pariquera-Açu` vira `pariquera-acu`, sem `%C3%A7` no link.

        O slug é a rota do SPA (`#/pariquera-acu`); com acento o link quebra ao
        ser colado em chat ou planilha.
        """
        self.assertEqual(relatorio.slug("Pariquera-Açu"), "pariquera-acu")
        self.assertEqual(relatorio.slug("Itanhaém"), "itanhaem")

    def test_cada_estacao_tem_rota_propria_no_json(self):
        """Duas estações do mesmo município saem com slugs distintos.

        O painel escolhe a estação pela URL (`#/registro-unesp`); se a rota fosse
        a do município, Registro e Registro Unesp abririam a mesma tela.
        """
        self.conn.execute(
            "INSERT INTO ponto(id, fonte, nome, municipio_id) "
            "VALUES('109','ciiagro','Registro Unesp',1)")
        for ponto in ("63", "109"):
            self.conn.execute(
                "INSERT INTO fato(ponto_id, data, tmed, chuva) VALUES(?, '2005-01', 20, 100)",
                (ponto,))
        caminho = relatorio.escrever(self.conn, Path(self.tmp.name) / "d.json")
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        registro = next(m for m in dados["municipios"] if m["slug"] == "registro")
        self.assertEqual([e["slug"] for e in registro["estacoes"]],
                         ["registro", "registro-unesp"])
        self.assertEqual({e["municipio"] for e in registro["estacoes"]}, {"Registro"})

    def test_menos_de_30_anos_nunca_diz_normal(self):
        """Série de 2 anos não ganha o rótulo "normal climatológica".

        É a garantia central do projeto: 30 anos é o mínimo da OMM, e um rótulo
        cravado faria 2 anos de dado parecerem clima.
        """
        for mes in range(1, 25):
            self._mes(f"{2000 + (mes - 1) // 12}-{mes % 12 or 12:02d}")
        ag = relatorio.agregado(self.conn, "63")
        self.assertAlmostEqual(ag["anos"], 2.0)
        self.assertNotIn("normal climatológica", relatorio.rotulo(ag, validada=True))
        self.assertIn("médias do período", relatorio.rotulo(ag, validada=True))

    def test_serie_pre_2000_nao_vira_normal_mesmo_com_30_anos(self):
        """34 anos que começam antes do início declarado não são normal.

        Pariquera-Açu tem 34 anos de dado, mas 11 deles anteriores a 2004 vieram
        sem explicação da fonte. Chamar isso de normal climatológica afirmaria
        uma validação que ninguém fez.
        """
        for mes in range(1, 409):
            self._mes(f"{1992 + (mes - 1) // 12}-{mes % 12 or 12:02d}")
        ag = relatorio.agregado(self.conn, "63")
        self.assertGreaterEqual(ag["anos"], 30)
        self.assertIn("normal climatológica", relatorio.rotulo(ag, validada=True))
        self.assertNotIn("normal climatológica", relatorio.rotulo(ag, validada=False))
        self.assertIn("não validada", relatorio.rotulo(ag, validada=False))

    def test_valor_impossivel_sai_da_media_e_e_contado(self):
        """`tmed = 873,35` não entra na média, mas aparece no rodapé como descarte.

        Caso real do CIIAGRO em Miracatu 03/1990. Sem o filtro, o relatório
        publicava 55,9 °C como temperatura média de março; com o filtro em
        silêncio, o leitor não saberia que a fonte se corrompe.
        """
        self._mes("2005-03", tmed=20.0)
        self._mes("2006-03", tmed=873.35)
        ag = relatorio.agregado(self.conn, "63")
        self.assertAlmostEqual(ag["por_mes"][2]["tmed"], 20.0)
        self.assertEqual(ag["descartes"]["tmed"], 1)

    def test_sazonal_soma_a_chuva_anual(self):
        """A soma das quatro estações fecha exatamente com a chuva anual do card.

        Se divergisse, o percentual sazonal estaria distribuindo água que não
        existe (ou escondendo parte dela).
        """
        for mes in range(1, 25):
            self._mes(f"{2000 + (mes - 1) // 12}-{mes % 12 or 12:02d}")
        r = relatorio.resumo(relatorio.agregado(self.conn, "63"))
        self.assertAlmostEqual(sum(s["mm"] for s in r["sazonal"]), r["chuva_ano"])

    def test_sazonal_traz_total_media_maximo_e_minimo(self):
        """A estação do ano carrega total, %, média/mês e os meses extremos.

        T07.1 — o site e a ficha LaTeX mostram máx, mín e média por estação; se
        viessem só o total, cada um calcularia de um jeito e um deles diria
        "máx 248" onde o outro diz 206. Aqui a média é o total dividido pelos
        três meses da estação, não a média das médias.
        """
        for mes in range(1, 25):
            # janeiro e fevereiro chuvosos, o resto seco: os extremos do verão
            # ficam sem empate, e um "pega o primeiro" apareceria.
            chuva = 200.0 if (mes - 1) % 12 in (0, 1) else 80.0
            self._mes(f"{2000 + (mes - 1) // 12}-{mes % 12 or 12:02d}", chuva=chuva)
        r = relatorio.resumo(relatorio.agregado(self.conn, "63"))
        verao = next(s for s in r["sazonal"] if s["nome"] == "Verão")
        self.assertAlmostEqual(verao["media"], verao["mm"] / 3)
        self.assertEqual(verao["max_mes"], "jan")
        self.assertEqual(verao["min_mes"], "dez")
        self.assertAlmostEqual(sum(s["pct"] for s in r["sazonal"]), 100.0)

    def test_solsticios_nao_somam_duas_vezes_nem_perdem_dezembro(self):
        """Os dois acumulados mais dezembro fecham com a chuva anual.

        T07.2 — o acumulado "antes do solstício de inverno" vai de janeiro a
        maio e o de verão de junho a novembro; dezembro é o único mês que fica
        de fora. Se um intervalo escapasse, a ficha apresentaria percentuais que
        não somam o ano.
        """
        for mes in range(1, 25):
            self._mes(f"{2000 + (mes - 1) // 12}-{mes % 12 or 12:02d}")
        ag = relatorio.agregado(self.conn, "63")
        r = relatorio.resumo(ag)
        dois = sum(s["mm"] for s in relatorio.solsticios(ag["por_mes"], r["chuva_ano"]))
        dezembro = next(m["chuva"] for m in ag["por_mes"] if m["mes"] == "dez")
        self.assertAlmostEqual(dois + dezembro, r["chuva_ano"])

    def test_uso_local_cita_numero_e_nao_deixa_valor_ausente(self):
        """O texto de planejamento sai com os números certos e sem `None`.

        T07.3 — é o texto que vai para a ATER; um `None` impresso ou um conselho
        sem o número que o sustenta derruba a confiança na ficha inteira. O
        mesmo texto alimenta o card do site e a ficha em LaTeX.
        """
        for mes in range(1, 13):
            self._mes(f"2005-{mes:02d}", chuva=200.0 if mes in (1, 2, 3) else 80.0)
        r = relatorio.resumo(relatorio.agregado(self.conn, "63"))
        est = {"meses": relatorio.agregado(self.conn, "63")["por_mes"], **r}
        itens = relatorio.uso_local(est)
        self.assertGreaterEqual(len(itens), 3)
        for item in itens:
            self.assertTrue(item["titulo"] and item["texto"])
            self.assertNotIn("None", item["texto"])
            self.assertNotIn("nan", item["texto"])
        self.assertIn("Calagem em cobertura", " ".join(i["titulo"] for i in itens))

    def test_inicio_das_chuvas_e_o_mes_depois_do_seco_nao_janeiro(self):
        """A volta das chuvas é o mês seguinte ao mais seco, não janeiro.

        T07.4 — pegar o primeiro mês úmido do ano civil devolvia janeiro, plena
        estação chuvosa, e a ficha mandava aplicar calcário no pior momento.
        """
        meses = [{"mes": m, "chuva": c} for m, c in zip(
            relatorio.MESES,
            [250.0, 200.0, 150.0, 60.0, 50.0, 70.0, 80.0, 40.0, 90.0, 130.0, 140.0, 180.0])]
        self.assertEqual(relatorio.inicio_das_chuvas(meses, "ago"), "out")
        self.assertEqual(relatorio.janela_seca(meses, "ago"),
                         ["abr", "mai", "jun", "jul", "ago", "set"])

    def test_regiao_leva_orientacao_geral_no_json(self):
        """O JSON traz, no topo, a orientação que vale para todo município.

        T07.5 — o card do site separa "vale para a região" de "nesta estação".
        Se o bloco geral sumisse da exportação, a página quebraria ao renderizar
        e a ficha ficaria só com conselho local.
        """
        caminho = relatorio.escrever(self.conn, Path(self.tmp.name) / "d.json")
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(dados["regiao"]["uso"]), 3)
        for item in dados["regiao"]["uso"]:
            self.assertTrue(item["titulo"] and item["texto"])

    def test_json_exportado_e_serializavel(self):
        """O JSON do dashboard sai do disco íntegro, com 12 linhas e chuva anual.

        Se a exportação perdesse a estrutura, o SPA abriria vazio sem erro
        nenhum — e ninguém saberia que o dado sumiu.
        """
        for mes in range(1, 13):
            self._mes(f"2005-{mes:02d}")
        caminho = relatorio.escrever(self.conn, Path(self.tmp.name) / "d.json")
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        registro = next(m for m in dados["municipios"] if m["slug"] == "registro")
        estacao = registro["estacoes"][0]
        self.assertEqual(estacao["id"], "63")
        self.assertEqual(len(estacao["meses"]), 12)
        self.assertAlmostEqual(estacao["chuva_ano"], 1200.0)

    def test_municipio_sem_estacao_entra_com_lista_vazia(self):
        """Itanhaém aparece no JSON com `estacoes: []`, não desaparece da lista.

        Sumir com o município transformaria "não há dado" em "não existe".
        """
        caminho = relatorio.escrever(self.conn, Path(self.tmp.name) / "d.json")
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        itanhaem = next(m for m in dados["municipios"] if m["slug"] == "itanhaem")
        self.assertEqual(itanhaem["estacoes"], [])

    def test_mes_sem_dado_vira_null(self):
        """Mês ausente é `null` no JSON, nunca `0` — buraco de série não é seca."""
        self._mes("2005-03", tmed=None, chuva=None)
        caminho = relatorio.escrever(self.conn, Path(self.tmp.name) / "d.json")
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        registro = next(m for m in dados["municipios"] if m["slug"] == "registro")
        marco = registro["estacoes"][0]["meses"][2]
        self.assertIsNone(marco["chuva"])
        self.assertIsNone(marco["tmed"])


if __name__ == "__main__":
    unittest.main()
