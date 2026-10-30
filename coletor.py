#!/usr/bin/env python3
"""Coletor CIIAGRO — catálogo, série e auditoria.

    python3 coletor.py catalogo
    python3 coletor.py coletar --desde 2000-01 --ate 2026-10
    python3 coletor.py coletar --desde 2026-10-01 --ate 2026-10-30 --diario
    python3 coletor.py auditar

Banco único em `dados/clima.sqlite`. Nenhuma dependência externa.

Por que mensal por padrão: 315 requisições em ~2 min, contra 9.560 em ~40 min
para a mesma janela em diário. O mensal não permite veranico nem dias secos;
quando isso for necessário, `--diario` grava no mesmo `fato` e a view
`consolidado` prefere o dia sobre o mês.

Aviso que o banco não resolve sozinho: o CIIAGRO devolve dados ANTES da
estação existir (Registro tem 380 mm em 01/1995, mas começou em 11/10/2005) e
usa 0 para "sem medição". `auditar` expõe os dois casos; nada é apagado aqui.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from fontes import ciiagro
from municipios import todos

DB = Path(__file__).with_name("dados") / "clima.sqlite"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS municipio(
    id INTEGER PRIMARY KEY,
    nome TEXT UNIQUE NOT NULL,
    regiao TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ponto(
    id TEXT PRIMARY KEY,
    fonte TEXT NOT NULL,
    nome TEXT NOT NULL,
    municipio_id INTEGER REFERENCES municipio(id),
    lat REAL, lon REAL,
    inicio_auto TEXT,
    primeiro_fato TEXT
);
CREATE TABLE IF NOT EXISTS fato(
    ponto_id TEXT NOT NULL REFERENCES ponto(id),
    data TEXT NOT NULL,              -- AAAA-MM-DD (dia) ou AAAA-MM (mês)
    tmin REAL, tmed REAL, tmax REAL,
    urmin REAL, urmed REAL, urmax REAL,
    chuva REAL,
    PRIMARY KEY (ponto_id, data)
);
CREATE INDEX IF NOT EXISTS fato_data ON fato(data);
"""

CAMPOS = ("tmin", "tmed", "tmax", "urmin", "urmed", "urmax", "chuva")


def abrir(caminho: Path = DB) -> sqlite3.Connection:
    """Abre (ou cria) o banco e aplica o esquema.

    Args:
        caminho: arquivo SQLite. O diretório é criado se não existir.

    Returns:
        Conexão com `row_factory = sqlite3.Row`, então as consultas aceitam
        `r["coluna"]`. O esquema usa `IF NOT EXISTS`, logo é seguro abrir
        repetidas vezes e em testes.
    """
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    conn.executescript(ESQUEMA)
    # Banco antigo tinha `municipio.microrregiao`; `CREATE TABLE IF NOT EXISTS`
    # não toca em tabela existente, então renomeia à mão. O `ALTER` preserva os
    # ids, e com eles o `ponto.municipio_id` já vinculado.
    colunas = {r["name"] for r in conn.execute("PRAGMA table_info(municipio)")}
    if "microrregiao" in colunas and "regiao" not in colunas:
        conn.execute("ALTER TABLE municipio RENAME COLUMN microrregiao TO regiao")
        conn.commit()
    return conn


def catalogo(conn: sqlite3.Connection) -> None:
    """Sincroniza `municipio` e `ponto` com o CSV local e com o CIIAGRO.

    Faz três requisições ao CIIAGRO (calendário, códigos, mapa). Os municípios
    vêm de `municipios.csv`, que é a lista canônica: estação cujo nome não casa
    com nenhum deles entra com `municipio_id = NULL` e continua utilizável como
    referência.

    Args:
        conn: conexão aberta por `abrir`.

    Efeitos:
        UPSERT em `municipio` (por nome) e em `ponto` (por código da estação).
        Não toca em `fato`; recolher o catálogo não apaga série.
    """
    conn.executemany(
        "INSERT INTO municipio(nome, regiao) VALUES(?, ?) "
        "ON CONFLICT(nome) DO UPDATE SET regiao = excluded.regiao",
        [(m["nome"], m["regiao"]) for m in todos()],
    )
    ids = {r["nome"]: r["id"] for r in conn.execute("SELECT id, nome FROM municipio")}
    pontos = ciiagro.pontos()
    for p in pontos:
        conn.execute(
            "INSERT INTO ponto(id, fonte, nome, municipio_id, lat, lon, inicio_auto) "
            "VALUES(?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET nome = excluded.nome, "
            "municipio_id = excluded.municipio_id, lat = excluded.lat, "
            "lon = excluded.lon, inicio_auto = excluded.inicio_auto",
            (p["id"], ciiagro.FONTE, p["nome"],
             ids.get(p["municipio"]), p["lat"], p["lon"], p["inicio_auto"]),
        )
    conn.commit()
    dentro = sum(p["municipio"] is not None for p in pontos)
    print(f"{len(ids)} municípios, {len(pontos)} estações "
          f"({dentro} dentro, {len(pontos) - dentro} fora do escopo)")


def substituir_granularidade(conn: sqlite3.Connection, pontos_meses: set[tuple[str, str]],
                             diario: bool) -> None:
    """Remove a granularidade oposta para cada (ponto, mês) antes da inserção.

    Garante que um mês tenha OU a linha mensal OU os dias, nunca os dois —
    senão `SUM(chuva)` por mês conta a mesma chuva duas vezes.
    """
    outro = 7 if diario else 10
    conn.executemany(
        "DELETE FROM fato WHERE ponto_id = ? AND length(data) = ? AND substr(data, 1, 7) = ?",
        [(p, outro, mes) for p, mes in pontos_meses],
    )


def atualizar_primeiro_fato(conn: sqlite3.Connection) -> None:
    """Recalcula `ponto.primeiro_fato` como o menor `data` existente em `fato`.

    Args:
        conn: conexão aberta por `abrir`.

    Nota:
        Recalcular do zero, e não só gravar o menor valor do lote: com
        `COALESCE(primeiro_fato, ?)` o primeiro lote coletado congelava o valor
        para sempre, e uma coleta posterior de período mais antigo não corrigia.
        Como são 23 linhas, o `UPDATE` inteiro é mais barato que rastrear o
        mínimo por lote.
    """
    conn.execute(
        "UPDATE ponto SET primeiro_fato = "
        "(SELECT MIN(f.data) FROM fato f WHERE f.ponto_id = ponto.id)")


def coletar(conn: sqlite3.Connection, desde: str, ate: str, diario: bool) -> None:
    """Baixa um intervalo do CIIAGRO e grava em `fato`.

    Uma requisição por período (não por estação): `diario/cdiaria` devolve
    todas as estações de uma data e `mensal/cmensal` todas de um mês.

    Args:
        conn: conexão aberta por `abrir`.
        desde: `AAAA-MM` (mensal) ou `AAAA-MM-DD` (diário), inclusivo.
        ate: mesmo formato de `desde`, inclusivo.
        diario: usa `cdiaria` (1 req/dia) em vez de `cmensal` (1 req/mês).
            O diário custa ~25x mais requisições e só compensa quando a
            análise precisa de veranico ou dias secos.

    Efeitos:
        UPSERT em `fato` com `COALESCE` (valor novo ausente não apaga o antigo),
        remoção da granularidade oposta para cada mês coletado (ver
        `substituir_granularidade`) e atualização de `ponto.primeiro_fato`.

    Nota:
        Estação que não está no catálogo é ignorada com aviso — rode `catalogo`
        antes. Intervalo sem nenhum dado imprime erro em stderr: costuma ser
        data inválida, não seca.
    """
    por_nome = {r["nome"]: r["id"] for r in conn.execute("SELECT id, nome FROM ponto")}
    sql = ("INSERT INTO fato(ponto_id, data, " + ", ".join(CAMPOS) + ") "
           "VALUES(?, ?, " + ", ".join("?" * len(CAMPOS)) + ") "
           "ON CONFLICT(ponto_id, data) DO UPDATE SET "
           + ", ".join(f"{c} = COALESCE(excluded.{c}, {c})" for c in CAMPOS))

    lote: list[tuple] = []
    ignorados: set[str] = set()
    vazio = 0
    for f in ciiagro.fatos(desde, ate, diario=diario):
        ponto = por_nome.get(f["nome"])
        if ponto is None:
            ignorados.add(f["nome"])
            continue
        lote.append((ponto, f["data"], *(f[c] for c in CAMPOS)))
    if not lote:
        # Um período sem nenhuma estação é sinal de data inválida, não de seca.
        vazio = 1

    # Invariante: para cada (ponto, mês) existe OU uma linha mensal OU os dias.
    # Sem isso, um SUM por mês somaria o total do mês com os dias do mesmo mês.
    substituir_granularidade(conn, {(p, d[:7]) for p, d, *_ in lote}, diario)
    conn.executemany(sql, lote)
    atualizar_primeiro_fato(conn)
    conn.commit()
    unidade = "dias" if diario else "meses"
    print(f"{len(lote)} linhas em {len({p for p, *_ in lote})} estações "
          f"({desde} a {ate}, {unidade})")
    if ignorados:
        print("fora do catálogo (rode `catalogo`): " + ", ".join(sorted(ignorados)))
    if vazio:
        print("NENHUM dado nesse período — confira o intervalo", file=sys.stderr)


def auditar(conn: sqlite3.Connection) -> None:
    """Imprime a cobertura por estação e os valores que exigem desconfiança.

    Não corrige nada, só relata — a coleta é deliberadamente burra e o
    julgamento fica aqui, visível.

    Args:
        conn: conexão aberta por `abrir`.

    Alertas emitidos:
        - `dado antes do início`: `primeiro_fato` anterior a `inicio_auto`
          (o site serve série antes de a estação existir).
        - `início suspeito (site)`: `inicio_auto` antes de 1970 (epoch do site).
        - `umidade toda 0 (ausente)`: todas as linhas com `urmed = 0`, que no
          CIIAGRO significa sensor ausente, não 0 %.
        - `chuva toda 0`: possível estação seca ou coluna quebrada.
    """
    print(f"{'estação':<22}{'município':<18}{'início':<12}{'1º fato':<10}"
          f"{'linhas':>7}  alertas")
    print("-" * 96)
    for r in conn.execute("""
        SELECT p.nome, COALESCE(m.nome, '-') AS municipio, p.inicio_auto, p.primeiro_fato,
               COUNT(f.data) AS n,
               SUM(CASE WHEN f.urmed = 0 THEN 1 ELSE 0 END) AS ur_zero,
               SUM(CASE WHEN f.chuva = 0 THEN 1 ELSE 0 END) AS chuva_zero,
               substr(p.primeiro_fato, 1, 7) < substr(p.inicio_auto, 1, 7) AS antes
        FROM ponto p
        LEFT JOIN municipio m ON m.id = p.municipio_id
        LEFT JOIN fato f ON f.ponto_id = p.id
        GROUP BY p.id ORDER BY p.nome
    """):
        alertas = []
        if r["antes"]:
            alertas.append("dado antes do início")
        if r["inicio_auto"] and r["inicio_auto"] < "1970":
            alertas.append("início suspeito (site)")
        if r["n"] and r["ur_zero"] == r["n"]:
            alertas.append("umidade toda 0 (ausente)")
        if r["n"] and r["chuva_zero"] == r["n"]:
            alertas.append("chuva toda 0")
        print(f"{r['nome']:<22}{r['municipio']:<18}{r['inicio_auto'] or '-':<12}"
              f"{r['primeiro_fato'] or '-':<10}{r['n']:>7}  {'; '.join(alertas)}")


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada da CLI (`catalogo`, `coletar`, `auditar`).

    Args:
        argv: argumentos sem o nome do programa. `None` lê de `sys.argv`.

    Returns:
        Código de saída do processo: sempre 0 quando o comando termina. Erros de
        rede sobem como exceção para não passarem por sucesso.
    """
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", type=Path, default=DB)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("catalogo", help="baixa municípios e estações (3 requisições)")
    c = sub.add_parser("coletar", help="baixa a série do CIIAGRO")
    c.add_argument("--desde", required=True, help="AAAA-MM ou AAAA-MM-DD")
    c.add_argument("--ate", required=True, help="AAAA-MM ou AAAA-MM-DD")
    c.add_argument("--diario", action="store_true", help="dia em vez de mês")
    sub.add_parser("auditar", help="cobertura e valores suspeitos")

    a = p.parse_args(argv)
    conn = abrir(a.db)
    if a.cmd == "catalogo":
        catalogo(conn)
    elif a.cmd == "coletar":
        coletar(conn, a.desde, a.ate, a.diario)
    else:
        auditar(conn)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
