"""Gera o relatório de médias e acumulados do período histórico do INMET.

Produz um `.md` legível com três visões:

1. **Resumo nacional** — quantas estações, chuva média anual do país.
2. **Tabela por estação** — média anual de cada variável e o acumulado de
   chuva de todo o período (a pergunta "quanto choveu no total").
3. **Normais mensais** das estações do Litoral Sul / Vale do Ribeira.

Uso:
    python3 dadoshistoricosinmet/relatorio_inmet.py
    python3 dadoshistoricosinmet/relatorio_inmet.py --uf SP --min-anos 10
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DIR_BASE = Path(__file__).resolve().parent
DB_PADRAO = DIR_BASE / "inmet_nacional.sqlite"
SAIDA_PADRAO = DIR_BASE.parent / "INMET_RELATORIO.md"

MESES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN",
         "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]


def fmt(v, casas: int = 1, sufixo: str = "") -> str:
    """Formata número no padrão brasileiro ou travessão se ausente.

    Args:
        v: Valor numérico ou None.
        casas: Casas decimais.
        sufixo: Texto colado ao final (ex.: " mm").

    Returns:
        String formatada.
    """
    if v is None:
        return "—"
    txt = f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{txt}{sufixo}"


def resumo_nacional(conn: sqlite3.Connection) -> dict:
    """Calcula agregados nacionais a partir das estações válidas.

    Args:
        conn: Conexão com o banco.

    Returns:
        Dicionário com contagens e médias nacionais.
    """
    cur = conn.cursor()
    total = cur.execute("SELECT COUNT(*) FROM inmet_resumo").fetchone()[0]
    por_status = dict(cur.execute(
        "SELECT status, COUNT(*) FROM inmet_resumo GROUP BY status"
    ))

    # Média nacional: média das médias por estação (não ponderada por área),
    # restrita a estações com série suficiente.
    linha = cur.execute("""
        SELECT COUNT(*), AVG(chuva_anual_media), AVG(tmed_periodo),
               MIN(periodo_inicio), MAX(periodo_fim),
               SUM(chuva_periodo_total), AVG(urmed_periodo)
        FROM inmet_resumo WHERE status = 'medido'
    """).fetchone()

    return {
        "total": total,
        "medido": por_status.get("medido", 0),
        "parcial": por_status.get("parcial", 0),
        "insuficiente": por_status.get("insuficiente", 0),
        "n_medido": linha[0] or 0,
        "chuva_media": linha[1],
        "tmed_media": linha[2],
        "ano_ini": linha[3],
        "ano_fim": linha[4],
        "chuva_soma": linha[5],
        "ur_media": linha[6],
    }


def tabela_estacoes(conn: sqlite3.Connection, uf: str | None, min_anos: int,
                    limite: int) -> list[tuple]:
    """Monta as linhas da tabela principal por estação.

    Args:
        conn: Conexão com o banco.
        uf: Filtro de UF (None = todas).
        min_anos: Mínimo de anos válidos para entrar.
        limite: Máximo de linhas (0 = sem limite).

    Returns:
        Lista de tuplas prontas para formatar.
    """
    sql = """
        SELECT e.codigo, e.nome, e.uf,
               r.periodo_inicio, r.periodo_fim, r.anos_validos,
               r.chuva_anual_media, r.chuva_periodo_total,
               r.tmed_periodo, r.tmax_abs, r.tmin_abs, r.urmed_periodo
        FROM inmet_resumo r
        JOIN inmet_estacao e ON e.codigo = r.codigo
        WHERE r.anos_validos >= ?
    """
    params: list = [min_anos]
    if uf:
        sql += " AND e.uf = ?"
        params.append(uf.upper())
    sql += " ORDER BY r.chuva_periodo_total DESC"
    if limite:
        sql += f" LIMIT {int(limite)}"
    return conn.execute(sql, params).fetchall()


def normais_mensais(conn: sqlite3.Connection, codigos: tuple[str, ...]) -> dict[str, list[tuple]]:
    """Busca a normal mensal das estações pedidas.

    Args:
        conn: Conexão com o banco.
        codigos: Códigos WMO.

    Returns:
        Mapa código -> lista de (mês, chuva, tmed, tmin, tmax, ur, anos_base).
    """
    saida: dict[str, list[tuple]] = {}
    for cod in codigos:
        saida[cod] = conn.execute("""
            SELECT mes, chuva, tmed, tmin, tmax, urmed, anos_base
            FROM inmet_normal WHERE codigo = ? ORDER BY mes
        """, (cod,)).fetchall()
    return saida


def gerar(conn: sqlite3.Connection, uf: str | None, min_anos: int, limite: int) -> str:
    """Monta o Markdown completo do relatório.

    Args:
        conn: Conexão com o banco.
        uf: Filtro de UF.
        min_anos: Mínimo de anos válidos.
        limite: Máximo de estações na tabela.

    Returns:
        Conteúdo Markdown.
    """
    r = resumo_nacional(conn)
    linhas = tabela_estacoes(conn, uf, min_anos, limite)
    agora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    out: list[str] = []
    out.append("# INMET — Médias e Acumulados do Período Histórico\n")
    out.append(f"Gerado em **{agora}** a partir de `dadoshistoricosinmet/inmet_nacional.sqlite`.\n")
    out.append("## Fonte\n")
    out.append("- **Série histórica:** `https://portal.inmet.gov.br/dadoshistoricos` — "
               "pacotes anuais `2000.zip` … `2026.zip`, CSVs horários de todas as "
               "estações automáticas do Brasil.")
    out.append("- **Catálogo de estações:** `https://apitempo.inmet.gov.br/estacoes/T`\n")
    out.append("## Critério de cálculo\n")
    out.append("- As leituras **horárias** foram agregadas em **mensais** e **anuais**; "
               "o diário não é armazenado.")
    out.append("- Um **ano válido** precisa de pelo menos **300 dias** com temperatura "
               "observada. 2026 entra como parcial (dados até 31/10) e fica fora das médias.")
    out.append("- A **chuva anual** soma apenas meses com leitura válida de precipitação. "
               "Dia com coluna toda em `-9999` conta como ausente, nunca como 0 mm.")
    out.append("- A **média do período** é a média dos anos válidos. O **acumulado do "
               "período** é a soma desses mesmos anos.")
    out.append(f"- Estação só recebe status `medido` com **≥ {min_anos if min_anos else 5} anos "
               "válidos** e **≥ 80% de cobertura**.\n")

    out.append("## Resumo nacional\n")
    out.append("| Indicador | Valor |")
    out.append("|---|---|")
    out.append(f"| Estações no banco | {r['total']} |")
    out.append(f"| Com série suficiente (`medido`) | {r['medido']} |")
    out.append(f"| Série parcial | {r['parcial']} |")
    out.append(f"| Dado insuficiente para média | {r['insuficiente']} |")
    out.append(f"| Período coberto | {r['ano_ini']}–{r['ano_fim']} |")
    out.append(f"| Chuva média anual (média das estações) | {fmt(r['chuva_media'], 0, ' mm')} |")
    out.append(f"| Temperatura média do período | {fmt(r['tmed_media'], 1, ' °C')} |")
    out.append(f"| Umidade relativa média | {fmt(r['ur_media'], 0, ' %')} |")
    out.append(f"| Chuva acumulada somada de todas as estações | {fmt(r['chuva_soma'], 0, ' mm')} |")
    out.append("")
    out.append("> A média nacional é a **média das médias por estação**, não ponderada por "
               "área. Serve para comparar estações, não para estimar o volume total "
               "precipitado sobre o território.\n")

    escopo = f"UF {uf.upper()}" if uf else "Brasil"
    out.append(f"## Estações — {escopo}\n")
    out.append(f"Filtro: ≥ {min_anos} anos válidos"
               + (f", top {limite} por chuva acumulada" if limite else "") + ".\n")
    out.append("| Código | Estação | UF | Período | Anos | Chuva média/ano | "
               "Chuva acumulada | T méd | T máx abs | T mín abs | UR |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for (cod, nome, uf_e, ini, fim, anos, chmed, chtot,
         tmed, tmax, tmin, ur) in linhas:
        out.append(
            f"| `{cod}` | {nome} | {uf_e} | {ini}–{fim} | {anos} | "
            f"{fmt(chmed, 0, ' mm')} | **{fmt(chtot, 0, ' mm')}** | "
            f"{fmt(tmed, 1, ' °C')} | {fmt(tmax, 1, ' °C')} | "
            f"{fmt(tmin, 1, ' °C')} | {fmt(ur, 0, ' %')} |"
        )
    out.append("")

    regionais = normais_mensais(conn, ("A712", "A746", "A766"))
    out.append("## Normais mensais — Litoral Sul e Vale do Ribeira\n")
    for cod, meses in regionais.items():
        if not meses:
            continue
        nome = conn.execute("SELECT nome, uf FROM inmet_estacao WHERE codigo = ?",
                            (cod,)).fetchone()
        titulo = f"{nome[0].title()} ({nome[1]})" if nome else cod
        out.append(f"### {cod} — {titulo}\n")
        out.append("| Mês | Chuva | T méd | T mín | T máx | UR | Anos-base |")
        out.append("|---|---|---|---|---|---|---|")
        tot_chuva = 0.0
        soma_t = 0.0
        n_t = 0
        for mes, chuva, tmed, tmin, tmax, ur, base in meses:
            out.append(
                f"| {MESES[mes - 1]} | {fmt(chuva, 1, ' mm')} | {fmt(tmed, 1, ' °C')} | "
                f"{fmt(tmin, 1, ' °C')} | {fmt(tmax, 1, ' °C')} | {fmt(ur, 0, ' %')} | {base} |"
            )
            if chuva:
                tot_chuva += chuva
            if tmed is not None:
                soma_t += tmed
                n_t += 1
        out.append(f"| **Ano** | **{fmt(tot_chuva, 0, ' mm')}** | "
                   f"**{fmt(soma_t / n_t if n_t else None, 1, ' °C')}** | | | | |")
        out.append("")

    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Relatório de médias e acumulados do INMET.")
    parser.add_argument("--db", type=Path, default=DB_PADRAO)
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    parser.add_argument("--uf", type=str, help="Filtra uma UF (ex.: SP)")
    parser.add_argument("--min-anos", type=int, default=5, help="Mínimo de anos válidos")
    parser.add_argument("--limite", type=int, default=0, help="Máximo de estações (0 = todas)")
    args = parser.parse_args()

    if not args.db.exists():
        raise SystemExit(f"Banco não encontrado: {args.db}. Rode processar.py antes.")

    conn = sqlite3.connect(args.db)
    texto = gerar(conn, args.uf, args.min_anos, args.limite)
    args.saida.write_text(texto, encoding="utf-8")
    conn.close()
    print(f"Relatório escrito em {args.saida} ({len(texto.splitlines())} linhas)")


if __name__ == "__main__":
    main()
