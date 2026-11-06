"""Processador nacional dos Dados Históricos do INMET.

Lê os ZIPs anuais de `portal.inmet.gov.br/dadoshistoricos`, agrega as leituras
horárias em totais/médias **mensais** e **anuais** por estação, e consolida a
normal climatológica do período completo.

Não guarda o diário: a escolha é mensal + anual, o que deixa o banco em poucos
MB e permite recalcular qualquer média sem reprocessar 1,8 GiB de ZIP.

Uso:
    python3 dadoshistoricosinmet/processar.py                    # todos os anos em cache
    python3 dadoshistoricosinmet/processar.py --desde 2000 --ate 2026 --paralelo 4
    python3 dadoshistoricosinmet/processar.py --anos 2023,2024
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

DIR_BASE = Path(__file__).resolve().parent
DIR_ZIPS = DIR_BASE / "zips"
DB_PADRAO = DIR_BASE / "inmet_nacional.sqlite"

# Estações no território do Litoral Sul e Vale do Ribeira (atalho do painel).
ESTACOES_REGIAO = {
    "A712": {"nome": "Iguape", "municipio": "Iguape"},
    "A746": {"nome": "Barra do Turvo", "municipio": "Barra do Turvo"},
    "A766": {"nome": "Registro", "municipio": "Registro"},
}

# --- Critérios de validade estatística -------------------------------------
# Um ano só entra nas médias se tiver quase todos os dias observados.
MIN_DIAS_ANO = 300
# Um mês só vira normal se tiver maioria dos dias observados naquele ano.
MIN_DIAS_MES = 20
# Normal climatológica exige série longa: 5 anos no mínimo.
MIN_ANOS_NORMAL = 5
# E cobertura de pelo menos 80% dos meses esperados no período da estação.
MIN_COBERTURA_NORMAL = 0.80


def _to_num(val: str) -> float | None:
    """Converte valor formatado do INMET (com vírgula) para float.

    Args:
        val: String vinda da célula do CSV (ex.: "23,4", ",4", "-9999").

    Returns:
        Float ou None se for nulo/ausente.
    """
    s = val.strip().replace(",", ".")
    if not s or s == "-9999" or s == "-999":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_csv_estacao(conteudo_bytes: bytes) -> tuple[dict, list[dict]]:
    """Extrai metadados e observações diárias agregadas de um CSV do INMET.

    Args:
        conteudo_bytes: Conteúdo bruto do arquivo CSV lido do zip.

    Returns:
        Tupla (metadados_estacao, lista_de_dias_agregados).
    """
    # Decoding com fallback para latin-1
    try:
        texto = conteudo_bytes.decode("utf-8")
    except UnicodeDecodeError:
        texto = conteudo_bytes.decode("latin-1", "replace")

    linhas = texto.splitlines()
    if len(linhas) < 10:
        return {}, []

    # Extração de Metadados nas primeiras 8 linhas
    meta = {}
    for l in linhas[:8]:
        partes = l.split(";")
        if len(partes) >= 2:
            k = partes[0].replace(":", "").strip().upper()
            v = partes[1].strip()
            meta[k] = v

    codigo = meta.get("CODIGO (WMO)") or meta.get("CODIGO") or ""
    nome = meta.get("ESTACAO") or meta.get("ESTAÇÃO") or ""
    uf = meta.get("UF") or ""
    lat = _to_num(meta.get("LATITUDE") or "")
    lon = _to_num(meta.get("LONGITUDE") or "")
    alt = _to_num(meta.get("ALTITUDE") or "")
    inicio = (
        meta.get("DATA DE FUNDACAO (YYYY-MM-DD)")
        or meta.get("DATA DE FUNDAÇÃO (YYYY-MM-DD)")
        or meta.get("DATA DE FUNDACAO")
        or ""
    )

    estacao_info = {
        "codigo": codigo,
        "nome": nome,
        "uf": uf,
        "lat": lat,
        "lon": lon,
        "altitude": alt,
        "inicio": inicio,
    }

    # Cabeçalho na linha 9 (índice 8)
    cabecalho = [c.strip().upper() for c in linhas[8].split(";")]

    def acha_idx(termo: str) -> int | None:
        for idx, col in enumerate(cabecalho):
            if termo in col:
                return idx
        return None

    i_data = acha_idx("DATA")
    i_chuva = acha_idx("PRECIPITA")
    i_tmed = acha_idx("BULBO SECO")
    i_tmax = acha_idx("MÁXIMA NA HORA") or acha_idx("MAXIMA NA HORA")
    i_tmin = acha_idx("MÍNIMA NA HORA") or acha_idx("MINIMA NA HORA")
    i_ur = acha_idx("UMIDADE RELATIVA DO AR, HORARIA")

    if i_data is None:
        return estacao_info, []

    # Agrupa horas por data
    por_dia: dict[str, dict[str, list[float]]] = {}
    col_max = max(filter(None, [i_data, i_chuva, i_tmed, i_tmax, i_tmin, i_ur]), default=0)

    for l in linhas[9:]:
        if not l.strip():
            continue
        p = l.split(";")
        if len(p) <= col_max:
            continue

        raw_dt = p[i_data].strip().replace("/", "-")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", raw_dt):
            continue

        chuva = _to_num(p[i_chuva]) if i_chuva is not None else None
        tmed = _to_num(p[i_tmed]) if i_tmed is not None else None
        tmax = _to_num(p[i_tmax]) if i_tmax is not None else None
        tmin = _to_num(p[i_tmin]) if i_tmin is not None else None
        ur = _to_num(p[i_ur]) if i_ur is not None else None

        d = por_dia.setdefault(raw_dt, {"chuva": [], "tmed": [], "tmax": [], "tmin": [], "ur": []})
        if chuva is not None:
            d["chuva"].append(chuva)
        if tmed is not None:
            d["tmed"].append(tmed)
        if tmax is not None:
            d["tmax"].append(tmax)
        if tmin is not None:
            d["tmin"].append(tmin)
        if ur is not None:
            d["ur"].append(ur)

    # Consolida dias
    fatos_diarios = []
    for dt, v in sorted(por_dia.items()):
        chuvas = v["chuva"]
        tmeds = v["tmed"]
        tmaxs = v["tmax"]
        tmins = v["tmin"]
        urs = v["ur"]

        fatos_diarios.append({
            "codigo": codigo,
            "data": dt,
            # Sem nenhuma leitura válida de precipitação o dia fica None.
            # Antes assumia 0.0 quando havia temperatura, o que inventava
            # "não choveu" para estações com a coluna toda em -9999.
            "chuva": round(sum(chuvas), 1) if chuvas else None,
            "tmed": round(sum(tmeds) / len(tmeds), 2) if tmeds else None,
            "tmax": max(tmaxs) if tmaxs else (max(tmeds) if tmeds else None),
            "tmin": min(tmins) if tmins else (min(tmeds) if tmeds else None),
            "urmed": round(sum(urs) / len(urs), 1) if urs else None,
        })

    return estacao_info, fatos_diarios


def agregar_mensal(estacao_info: dict, dias: list[dict]) -> dict[str, dict[str, Any]]:
    """Reduz os dias de uma estação em totais/médias mensais.

    Args:
        estacao_info: Metadados da estação.
        dias: Lista de dias agregados produzida por `parse_csv_estacao`.

    Returns:
        Mapa "YYYY-MM" -> agregados do mês, com contagem de dias válidos
        separada por variável (chuva e temperatura têm lacunas diferentes).
    """
    meses: dict[str, dict[str, Any]] = {}

    for d in dias:
        chave = d["data"][:7]
        m = meses.setdefault(chave, {
            "chuva": 0.0,
            "dias_chuva": 0,
            "tmed_soma": 0.0,
            "dias_tmed": 0,
            "tmax": None,
            "tmin": None,
            "ur_soma": 0.0,
            "dias_ur": 0,
        })

        if d["chuva"] is not None:
            m["chuva"] += d["chuva"]
            m["dias_chuva"] += 1
        if d["tmed"] is not None:
            m["tmed_soma"] += d["tmed"]
            m["dias_tmed"] += 1
        if d["tmax"] is not None:
            m["tmax"] = d["tmax"] if m["tmax"] is None else max(m["tmax"], d["tmax"])
        if d["tmin"] is not None:
            m["tmin"] = d["tmin"] if m["tmin"] is None else min(m["tmin"], d["tmin"])
        if d["urmed"] is not None:
            m["ur_soma"] += d["urmed"]
            m["dias_ur"] += 1

    return meses


def processar_ano(caminho_zip: str | Path) -> tuple[dict[str, dict], dict[str, dict[str, dict]]]:
    """Processa um ZIP anual inteiro, retornando agregados mensais por estação.

    Função de topo de módulo para poder rodar em `ProcessPoolExecutor`.

    Args:
        caminho_zip: Caminho do `.zip` anual.

    Returns:
        Tupla (estacoes, mensais):
          - estacoes: mapa código -> metadados
          - mensais: mapa código -> mapa "YYYY-MM" -> agregados
    """
    caminho_zip = Path(caminho_zip)
    estacoes: dict[str, dict] = {}
    mensais: dict[str, dict[str, dict]] = {}

    with zipfile.ZipFile(caminho_zip, "r") as z:
        for nome_arq in z.namelist():
            if not nome_arq.upper().endswith(".CSV"):
                continue
            try:
                conteudo = z.read(nome_arq)
            except (zipfile.BadZipFile, OSError):
                continue

            est, dias = parse_csv_estacao(conteudo)
            codigo = est.get("codigo")
            if not codigo or not dias:
                continue

            # Metadados: guarda a primeira aparição não vazia. Arquivos antigos
            # têm altitude com vírgula e nome sem acento; o mais recente manda.
            estacoes[codigo] = est
            mensais[codigo] = agregar_mensal(est, dias)

    return estacoes, mensais


def inicializar_banco(conn: sqlite3.Connection) -> None:
    """Cria o esquema do banco nacional (mensal + anual + normal)."""
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS inmet_estacao (
                codigo TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                uf TEXT NOT NULL,
                lat REAL,
                lon REAL,
                altitude REAL,
                inicio TEXT,
                primeiro_ano INTEGER,
                ultimo_ano INTEGER
            );

            CREATE TABLE IF NOT EXISTS inmet_mensal (
                codigo TEXT NOT NULL,
                mes TEXT NOT NULL,
                chuva REAL,
                dias_chuva INTEGER,
                tmed REAL,
                dias_tmed INTEGER,
                tmax REAL,
                tmin REAL,
                urmed REAL,
                dias_ur INTEGER,
                PRIMARY KEY (codigo, mes)
            );

            CREATE TABLE IF NOT EXISTS inmet_anual (
                codigo TEXT NOT NULL,
                ano INTEGER NOT NULL,
                chuva_total REAL,
                dias_chuva INTEGER,
                tmed REAL,
                dias_tmed INTEGER,
                tmax_abs REAL,
                tmin_abs REAL,
                urmed REAL,
                meses_com_dado INTEGER,
                valido INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (codigo, ano)
            );

            CREATE TABLE IF NOT EXISTS inmet_normal (
                codigo TEXT NOT NULL,
                mes INTEGER NOT NULL,
                chuva REAL,
                tmed REAL,
                tmax REAL,
                tmin REAL,
                urmed REAL,
                anos_base INTEGER,
                PRIMARY KEY (codigo, mes)
            );

            CREATE TABLE IF NOT EXISTS inmet_resumo (
                codigo TEXT PRIMARY KEY,
                periodo_inicio INTEGER,
                periodo_fim INTEGER,
                anos_validos INTEGER,
                anos_com_dado INTEGER,
                chuva_anual_media REAL,
                chuva_periodo_total REAL,
                tmed_periodo REAL,
                tmax_abs REAL,
                tmin_abs REAL,
                urmed_periodo REAL,
                cobertura REAL,
                status TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_mensal_mes ON inmet_mensal(mes);
            CREATE INDEX IF NOT EXISTS idx_anual_ano ON inmet_anual(ano);
        """)


def gravar_ano(conn: sqlite3.Connection, estacoes: dict, mensais: dict) -> int:
    """Grava os agregados mensais de um ano no SQLite.

    Args:
        conn: Conexão SQLite.
        estacoes: Mapa código -> metadados.
        mensais: Mapa código -> mapa mês -> agregados.

    Returns:
        Quantidade de estações gravadas.
    """
    linhas_est = []
    linhas_mes = []

    for codigo, est in estacoes.items():
        meses = mensais.get(codigo, {})
        if not meses:
            continue
        anos = sorted({m[:4] for m in meses})
        linhas_est.append((
            codigo,
            est.get("nome") or codigo,
            est.get("uf") or "",
            est.get("lat"),
            est.get("lon"),
            est.get("altitude"),
            est.get("inicio") or "",
            int(anos[0]),
            int(anos[-1]),
        ))

        for mes, m in meses.items():
            linhas_mes.append((
                codigo,
                mes,
                round(m["chuva"], 1) if m["dias_chuva"] else None,
                m["dias_chuva"],
                round(m["tmed_soma"] / m["dias_tmed"], 2) if m["dias_tmed"] else None,
                m["dias_tmed"],
                m["tmax"],
                m["tmin"],
                round(m["ur_soma"] / m["dias_ur"], 1) if m["dias_ur"] else None,
                m["dias_ur"],
            ))

    with conn:
        conn.executemany("""
            INSERT INTO inmet_estacao
                (codigo, nome, uf, lat, lon, altitude, inicio, primeiro_ano, ultimo_ano)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(codigo) DO UPDATE SET
                nome = excluded.nome,
                uf = excluded.uf,
                lat = COALESCE(excluded.lat, inmet_estacao.lat),
                lon = COALESCE(excluded.lon, inmet_estacao.lon),
                altitude = COALESCE(excluded.altitude, inmet_estacao.altitude),
                primeiro_ano = MIN(inmet_estacao.primeiro_ano, excluded.primeiro_ano),
                ultimo_ano = MAX(inmet_estacao.ultimo_ano, excluded.ultimo_ano)
        """, linhas_est)

        conn.executemany("""
            INSERT INTO inmet_mensal
                (codigo, mes, chuva, dias_chuva, tmed, dias_tmed, tmax, tmin, urmed, dias_ur)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(codigo, mes) DO UPDATE SET
                chuva = excluded.chuva,
                dias_chuva = excluded.dias_chuva,
                tmed = excluded.tmed,
                dias_tmed = excluded.dias_tmed,
                tmax = excluded.tmax,
                tmin = excluded.tmin,
                urmed = excluded.urmed,
                dias_ur = excluded.dias_ur
        """, linhas_mes)

    return len(linhas_est)


def consolidar_anual(conn: sqlite3.Connection) -> None:
    """Deriva a tabela anual a partir da mensal, marcando anos válidos.

    O acumulado anual de chuva soma apenas meses com leitura de precipitação.
    `valido=1` exige `MIN_DIAS_ANO` dias de temperatura no ano.
    """
    with conn:
        conn.execute("DELETE FROM inmet_anual")
        conn.execute("""
            INSERT INTO inmet_anual
                (codigo, ano, chuva_total, dias_chuva, tmed, dias_tmed,
                 tmax_abs, tmin_abs, urmed, meses_com_dado, valido)
            SELECT
                codigo,
                CAST(substr(mes, 1, 4) AS INTEGER) AS ano,
                ROUND(SUM(chuva), 1) AS chuva_total,
                SUM(dias_chuva) AS dias_chuva,
                -- Média anual ponderada pelos dias de cada mês.
                ROUND(SUM(tmed * dias_tmed) / NULLIF(SUM(dias_tmed), 0), 2) AS tmed,
                SUM(dias_tmed) AS dias_tmed,
                MAX(tmax) AS tmax_abs,
                MIN(tmin) AS tmin_abs,
                ROUND(SUM(urmed * dias_ur) / NULLIF(SUM(dias_ur), 0), 1) AS urmed,
                COUNT(*) AS meses_com_dado,
                CASE WHEN SUM(dias_tmed) >= {min_dias} THEN 1 ELSE 0 END AS valido
            FROM inmet_mensal
            GROUP BY codigo, CAST(substr(mes, 1, 4) AS INTEGER)
        """.format(min_dias=MIN_DIAS_ANO))


def consolidar_normal(conn: sqlite3.Connection) -> None:
    """Calcula a normal climatológica mensal por estação.

    Só usa anos marcados como válidos. Cada mês precisa de pelo menos
    `MIN_DIAS_MES` dias naquele ano para entrar na média.
    """
    with conn:
        conn.execute("DELETE FROM inmet_normal")
        conn.execute("""
            INSERT INTO inmet_normal (codigo, mes, chuva, tmed, tmax, tmin, urmed, anos_base)
            SELECT
                m.codigo,
                CAST(substr(m.mes, 6, 2) AS INTEGER) AS mes_num,
                ROUND(AVG(CASE WHEN m.dias_chuva >= ? THEN m.chuva END), 1) AS chuva,
                ROUND(AVG(CASE WHEN m.dias_tmed  >= ? THEN m.tmed  END), 2) AS tmed,
                ROUND(AVG(CASE WHEN m.dias_tmed  >= ? THEN m.tmax  END), 2) AS tmax,
                ROUND(AVG(CASE WHEN m.dias_tmed  >= ? THEN m.tmin  END), 2) AS tmin,
                ROUND(AVG(CASE WHEN m.dias_ur    >= ? THEN m.urmed END), 1) AS urmed,
                COUNT(DISTINCT substr(m.mes, 1, 4)) AS anos_base
            FROM inmet_mensal m
            JOIN inmet_anual a
              ON a.codigo = m.codigo
             AND a.ano = CAST(substr(m.mes, 1, 4) AS INTEGER)
            WHERE a.valido = 1
            GROUP BY m.codigo, mes_num
        """, (MIN_DIAS_MES,) * 5)


def consolidar_resumo(conn: sqlite3.Connection) -> None:
    """Resume cada estação: médias do período, acumulados e status de cobertura.

    `status` responde à pergunta prática do painel:
      - `medido`: série longa e densa, pode ser chamada de normal
      - `parcial`: tem dado real, mas curto ou com lacunas
      - `insuficiente`: dado existe mas não sustenta média
    """
    with conn:
        conn.execute("DELETE FROM inmet_resumo")
        conn.execute("""
            INSERT INTO inmet_resumo
                (codigo, periodo_inicio, periodo_fim, anos_validos, anos_com_dado,
                 chuva_anual_media, chuva_periodo_total, tmed_periodo,
                 tmax_abs, tmin_abs, urmed_periodo, cobertura, status)
            SELECT
                codigo,
                MIN(ano),
                MAX(ano),
                SUM(valido),
                COUNT(*),
                -- Média dos acumulados anuais: só anos válidos, para não
                -- subestimar a chuva com anos incompletos.
                ROUND(AVG(CASE WHEN valido = 1 THEN chuva_total END), 1),
                ROUND(SUM(CASE WHEN valido = 1 THEN chuva_total END), 1),
                ROUND(SUM(CASE WHEN valido = 1 THEN tmed * dias_tmed END)
                      / NULLIF(SUM(CASE WHEN valido = 1 THEN dias_tmed END), 0), 2),
                MAX(CASE WHEN valido = 1 THEN tmax_abs END),
                MIN(CASE WHEN valido = 1 THEN tmin_abs END),
                ROUND(SUM(CASE WHEN valido = 1 THEN urmed * dias_tmed END)
                      / NULLIF(SUM(CASE WHEN valido = 1 THEN dias_tmed END), 0), 1),
                ROUND(CAST(SUM(valido) AS REAL) / COUNT(*), 3),
                CASE
                    WHEN SUM(valido) >= ? AND
                         CAST(SUM(valido) AS REAL) / COUNT(*) >= ?
                        THEN 'medido'
                    WHEN SUM(valido) >= 1 THEN 'parcial'
                    ELSE 'insuficiente'
                END
            FROM inmet_anual
            GROUP BY codigo
        """, (MIN_ANOS_NORMAL, MIN_COBERTURA_NORMAL))


def sanitizar_extremos(conn: sqlite3.Connection) -> int:
    """Anula máximas/mínimas mensais fisicamente impossíveis antes de consolidar.

    O arquivo histórico tem picos isolados de sensor que não afetam a média
    mensal (o resto do mês está bom), mas contaminam `tmax_abs`/`tmin_abs` e a
    normal: Belém marca 45,0 °C em 12/2005 e −5,0 °C em 03/2020; Goiânia marca
    −8,7 °C em 08/2008.

    O critério é a própria série da estação **no mesmo mês do ano**: descarta
    o valor fora de `mediana ± max(3*MAD, 6 °C)`. Mediana e MAD ignoram o
    próprio pico, e o piso de 6 °C impede cortar a variabilidade real entre
    anos normais. Só atua em séries com `MIN_ANOS_NORMAL` anos ou mais.

    Args:
        conn: Conexão com o banco já carregado com `inmet_mensal`.

    Returns:
        Quantidade de células mensais anuladas.

    Nota:
        A média mensal (`tmed`) e a chuva não são tocadas — só os extremos.
    """
    from statistics import median

    linhas = conn.execute(
        "SELECT codigo, mes, tmax, tmin FROM inmet_mensal"
    ).fetchall()
    grupos: dict[tuple[str, int], list[tuple[str, float | None, float | None]]] = {}
    for codigo, mes, tmax, tmin in linhas:
        grupos.setdefault((codigo, int(mes[5:7])), []).append((mes, tmax, tmin))

    mudancas: list[tuple[str, str, str]] = []
    for (codigo, _), vals in grupos.items():
        if len(vals) < MIN_ANOS_NORMAL:
            continue
        for coluna, pos in (("tmax", 1), ("tmin", 2)):
            serie = [v[pos] for v in vals if v[pos] is not None]
            if len(serie) < MIN_ANOS_NORMAL:
                continue
            centro = median(serie)
            desvio = median([abs(x - centro) for x in serie]) or 0.0
            tolerancia = max(3 * desvio, 6.0)
            for v in vals:
                if v[pos] is not None and abs(v[pos] - centro) > tolerancia:
                    mudancas.append((codigo, v[0], coluna))

    with conn:
        for coluna in ("tmax", "tmin"):
            alvos = [(c, m) for c, m, col in mudancas if col == coluna]
            conn.executemany(
                f"UPDATE inmet_mensal SET {coluna} = NULL WHERE codigo = ? AND mes = ?",
                alvos,
            )
    return len(mudancas)


def main() -> None:
    parser = argparse.ArgumentParser(description="Processa os ZIPs anuais do INMET em mensal + anual.")
    parser.add_argument("--anos", type=str, help="Anos separados por vírgula (ex.: 2008,2018,2023)")
    parser.add_argument("--desde", type=int, help="Primeiro ano (padrão: menor ZIP em cache)")
    parser.add_argument("--ate", type=int, help="Último ano (padrão: maior ZIP em cache)")
    parser.add_argument("--paralelo", type=int, default=4, help="Processos simultâneos")
    parser.add_argument("--db", type=Path, default=DB_PADRAO, help="Banco SQLite de saída")
    args = parser.parse_args()

    em_cache = sorted(int(f.stem) for f in DIR_ZIPS.glob("*.zip") if f.stem.isdigit())
    if args.anos:
        anos = sorted(int(a.strip()) for a in args.anos.split(",") if a.strip())
    else:
        desde = args.desde or (em_cache[0] if em_cache else 2000)
        ate = args.ate or (em_cache[-1] if em_cache else 2026)
        anos = [a for a in range(desde, ate + 1) if a in em_cache]

    faltando = [a for a in anos if a not in em_cache]
    if faltando:
        print(f"Aviso: sem ZIP em cache para {faltando}; rode coletar.py antes.")
    if not anos:
        sys.exit("Nenhum ZIP disponível em dadoshistoricosinmet/zips/.")

    print(f"Processando {len(anos)} anos ({anos[0]}..{anos[-1]}) com {args.paralelo} processos...")
    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    inicializar_banco(conn)

    total_est = 0
    with ProcessPoolExecutor(max_workers=args.paralelo) as pool:
        futuros = {pool.submit(processar_ano, DIR_ZIPS / f"{a}.zip"): a for a in anos}
        for futuro in as_completed(futuros):
            ano = futuros[futuro]
            try:
                estacoes, mensais = futuro.result()
            except Exception as erro:  # noqa: BLE001 - um ano ruim não derruba o lote
                print(f"  [{ano}] FALHOU: {erro}")
                continue
            n = gravar_ano(conn, estacoes, mensais)
            total_est += n
            print(f"  [{ano}] {n} estações, {sum(len(m) for m in mensais.values())} linhas mensais")

    print("Sanitizando extremos mensais...")
    anulados = sanitizar_extremos(conn)
    print(f"  {anulados} células anuladas")
    print("Consolidando anual...")
    consolidar_anual(conn)
    print("Consolidando normal climatológica...")
    consolidar_normal(conn)
    print("Consolidando resumo por estação...")
    consolidar_resumo(conn)

    cur = conn.cursor()
    est = cur.execute("SELECT COUNT(*) FROM inmet_estacao").fetchone()[0]
    men = cur.execute("SELECT COUNT(*) FROM inmet_mensal").fetchone()[0]
    anu = cur.execute("SELECT COUNT(*) FROM inmet_anual").fetchone()[0]
    nor = cur.execute("SELECT COUNT(*) FROM inmet_normal").fetchone()[0]
    print(f"\nBanco: {est} estações | {men} meses | {anu} anos | {nor} normais mensais")

    for status, qtd in cur.execute(
        "SELECT status, COUNT(*) FROM inmet_resumo GROUP BY status ORDER BY COUNT(*) DESC"
    ):
        print(f"  {status}: {qtd} estações")
    conn.close()


if __name__ == "__main__":
    main()
