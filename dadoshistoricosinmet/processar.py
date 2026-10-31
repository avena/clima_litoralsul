"""Processador de dados históricos do INMET (portal.inmet.gov.br/dadoshistoricos).

Baixa e extrai arquivos anuais (.zip), lê os CSVs das estações automáticas
diretamente da memória, e consolida séries diárias e mensais em SQLite e JSON.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Iterator

URL_BASE = "https://portal.inmet.gov.br/uploads/dadoshistoricos/{ano}.zip"
DIR_BASE = Path(__file__).resolve().parent
DIR_ZIPS = DIR_BASE / "zips"
DB_PADRAO = DIR_BASE / "inmet_historico.sqlite"
JSON_PADRAO = DIR_BASE / "inmet_regional.json"

# Estações no território do Litoral Sul e Vale do Ribeira
ESTACOES_REGIAO = {
    "A712": {"nome": "Iguape", "municipio": "Iguape"},
    "A746": {"nome": "Barra do Turvo", "municipio": "Barra do Turvo"},
    "A766": {"nome": "Registro", "municipio": "Registro"},
}


def baixar_ano(ano: int, destino_dir: Path = DIR_ZIPS) -> Path:
    """Baixa o arquivo .zip de um ano do portal do INMET se não estiver em cache.

    Args:
        ano: Ano com 4 dígitos (ex.: 2023).
        destino_dir: Pasta onde os .zip são armazenados.

    Returns:
        Caminho local para o arquivo .zip.

    Raises:
        urllib.error.URLError: Se a conexão ou download falhar.
    """
    destino_dir.mkdir(parents=True, exist_ok=True)
    caminho = destino_dir / f"{ano}.zip"
    if caminho.exists() and caminho.stat().st_size > 100_000:
        return caminho

    url = URL_BASE.format(ano=ano)
    print(f"Baixando dados históricos de {ano} ({url})...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (clima-litoralsul)"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(caminho, "wb") as f:
        total = int(resp.headers.get("Content-Length", 0))
        baixado = 0
        while True:
            bloco = resp.read(1024 * 512)
            if not bloco:
                break
            f.write(bloco)
            baixado += len(bloco)
            if total > 0 and baixado % (1024 * 1024 * 10) < 1024 * 512:
                sys.stdout.write(f"\r  -> {baixado / (1024 * 1024):.1f} / {total / (1024 * 1024):.1f} MB")
                sys.stdout.flush()
    print(f"\n  -> {caminho.name} concluído ({caminho.stat().st_size / (1024 * 1024):.1f} MB).")
    return caminho


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
    inicio = meta.get("DATA DE FUNDACAO (YYYY-MM-DD)") or meta.get("DATA DE FUNDAÇÃO (YYYY-MM-DD)") or meta.get("DATA DE FUNDACAO") or ""

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
            "chuva": round(sum(chuvas), 1) if chuvas else (0.0 if (tmeds or urs) else None),
            "tmed": round(sum(tmeds) / len(tmeds), 2) if tmeds else None,
            "tmax": max(tmaxs) if tmaxs else (max(tmeds) if tmeds else None),
            "tmin": min(tmins) if tmins else (min(tmeds) if tmeds else None),
            "urmed": round(sum(urs) / len(urs), 1) if urs else None,
        })

    return estacao_info, fatos_diarios


def inicializar_banco(conn: sqlite3.Connection) -> None:
    """Cria tabelas no banco de dados SQLite para as séries do INMET."""
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS inmet_estacao (
                codigo TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                uf TEXT NOT NULL,
                lat REAL,
                lon REAL,
                altitude REAL,
                inicio TEXT
            );

            CREATE TABLE IF NOT EXISTS inmet_diario (
                codigo TEXT NOT NULL,
                data TEXT NOT NULL,
                chuva REAL,
                tmed REAL,
                tmax REAL,
                tmin REAL,
                urmed REAL,
                PRIMARY KEY (codigo, data),
                FOREIGN KEY (codigo) REFERENCES inmet_estacao(codigo)
            );

            CREATE TABLE IF NOT EXISTS inmet_mensal (
                codigo TEXT NOT NULL,
                mes TEXT NOT NULL,
                chuva REAL,
                tmed REAL,
                tmax REAL,
                tmin REAL,
                urmed REAL,
                dias_com_dado INTEGER,
                PRIMARY KEY (codigo, mes),
                FOREIGN KEY (codigo) REFERENCES inmet_estacao(codigo)
            );

            CREATE INDEX IF NOT EXISTS idx_inmet_diario_dt ON inmet_diario(data);
            CREATE INDEX IF NOT EXISTS idx_inmet_mensal_mes ON inmet_mensal(mes);
        """)


def salvar_estacao_e_diarios(conn: sqlite3.Connection, est: dict, diarios: list[dict]) -> None:
    """Insere ou atualiza estação e registros diários no SQLite."""
    with conn:
        conn.execute("""
            INSERT INTO inmet_estacao (codigo, nome, uf, lat, lon, altitude, inicio)
            VALUES (:codigo, :nome, :uf, :lat, :lon, :altitude, :inicio)
            ON CONFLICT(codigo) DO UPDATE SET
                nome = excluded.nome,
                uf = excluded.uf,
                lat = COALESCE(excluded.lat, inmet_estacao.lat),
                lon = COALESCE(excluded.lon, inmet_estacao.lon),
                altitude = COALESCE(excluded.altitude, inmet_estacao.altitude)
        """, est)

        conn.executemany("""
            INSERT INTO inmet_diario (codigo, data, chuva, tmed, tmax, tmin, urmed)
            VALUES (:codigo, :data, :chuva, :tmed, :tmax, :tmin, :urmed)
            ON CONFLICT(codigo, data) DO UPDATE SET
                chuva = excluded.chuva,
                tmed = excluded.tmed,
                tmax = excluded.tmax,
                tmin = excluded.tmin,
                urmed = excluded.urmed
        """, diarios)


def consolidar_mensal(conn: sqlite3.Connection) -> None:
    """Agrega a tabela `inmet_diario` na tabela `inmet_mensal`."""
    with conn:
        conn.execute("""
            INSERT OR REPLACE INTO inmet_mensal (codigo, mes, chuva, tmed, tmax, tmin, urmed, dias_com_dado)
            SELECT
                codigo,
                substr(data, 1, 7) AS mes,
                ROUND(SUM(chuva), 1) AS chuva,
                ROUND(AVG(tmed), 2) AS tmed,
                ROUND(MAX(tmax), 2) AS tmax,
                ROUND(MIN(tmin), 2) AS tmin,
                ROUND(AVG(urmed), 1) AS urmed,
                COUNT(tmed) AS dias_com_dado
            FROM inmet_diario
            GROUP BY codigo, substr(data, 1, 7)
        """)


def processar_arquivo_zip(caminho_zip: Path, conn: sqlite3.Connection, apenas_regiao: bool = True) -> int:
    """Processa todas as estações de interesse dentro de um arquivo ZIP.

    Args:
        caminho_zip: Caminho do arquivo .zip anual.
        conn: Conexão SQLite.
        apenas_regiao: Se True, processa apenas A712, A746 e A766.

    Returns:
        Número de estações processadas.
    """
    processadas = 0
    with zipfile.ZipFile(caminho_zip, "r") as z:
        for nome_arq in z.namelist():
            if not nome_arq.upper().endswith(".CSV"):
                continue

            cod = None
            if apenas_regiao:
                for c in ESTACOES_REGIAO:
                    if c in nome_arq.upper():
                        cod = c
                        break
                if not cod:
                    continue

            conteudo = z.read(nome_arq)
            est, diarios = parse_csv_estacao(conteudo)
            if not est.get("codigo"):
                continue

            salvar_estacao_e_diarios(conn, est, diarios)
            processadas += 1

    return processadas


def exportar_json(conn: sqlite3.Connection, destino_json: Path = JSON_PADRAO) -> None:
    """Exporta as séries das estações regionais em JSON estruturado para aplicações web."""
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT * FROM inmet_estacao ORDER BY nome")
    estacoes = []
    for est in c.fetchall():
        cod = est["codigo"]
        c.execute("SELECT * FROM inmet_mensal WHERE codigo = ? ORDER BY mes", (cod,))
        meses = [dict(r) for r in c.fetchall()]

        estacoes.append({
            "codigo": cod,
            "nome": est["nome"],
            "uf": est["uf"],
            "lat": est["lat"],
            "lon": est["lon"],
            "altitude": est["altitude"],
            "inicio": est["inicio"],
            "total_meses": len(meses),
            "meses": meses,
        })

    payload = {
        "fonte": "inmet_dadoshistoricos",
        "url_origem": "https://portal.inmet.gov.br/dadoshistoricos",
        "estacoes": estacoes,
    }

    with open(destino_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"JSON exportado em {destino_json} ({len(estacoes)} estações).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Processador de dados históricos do INMET.")
    parser.add_argument("--anos", type=str, help="Anos separados por vírgula (ex.: 2008,2018,2023)")
    parser.add_argument("--ano", type=int, help="Um ano único para processar (ex.: 2023)")
    parser.add_argument("--todos-em-cache", action="store_true", help="Processa todos os ZIPs já baixados em zips/")
    parser.add_argument("--todas-estacoes", action="store_true", help="Processa todas as estações do ZIP (não apenas a região)")
    parser.add_argument("--db", type=Path, default=DB_PADRAO, help="Caminho do banco SQLite de saída")
    parser.add_argument("--json", type=Path, default=JSON_PADRAO, help="Caminho do JSON de saída")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    inicializar_banco(conn)

    anos = []
    if args.ano:
        anos = [args.ano]
    elif args.anos:
        anos = [int(a.strip()) for a in args.anos.split(",")]
    elif args.todos_em_cache:
        anos = sorted([int(f.stem) for f in DIR_ZIPS.glob("*.zip") if f.stem.isdigit()])
    else:
        # Padrão: processa os anos que já estiverem baixados, ou a amostra estatística [2008, 2018, 2023]
        em_cache = sorted([int(f.stem) for f in DIR_ZIPS.glob("*.zip") if f.stem.isdigit()])
        anos = em_cache if em_cache else [2008, 2018, 2023]

    print(f"Processando anos: {anos} no banco {args.db}...")
    for a in anos:
        zip_path = baixar_ano(a)
        n = processar_arquivo_zip(zip_path, conn, apenas_regiao=not args.todas_estacoes)
        print(f"Ano {a}: {n} estações salvas.")

    print("Consolidando série mensal...")
    consolidar_mensal(conn)
    exportar_json(conn, args.json)

    # Imprime resumo
    cur = conn.cursor()
    cur.execute("SELECT codigo, count(*), min(mes), max(mes) FROM inmet_mensal GROUP BY codigo")
    print("\nResumo consolidado no SQLite:")
    for r in cur.fetchall():
        print(f"  Estação {r[0]}: {r[1]} meses ({r[2]} → {r[3]})")


if __name__ == "__main__":
    main()
