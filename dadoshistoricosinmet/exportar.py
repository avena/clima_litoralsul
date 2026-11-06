"""Exporta o banco nacional do INMET para os JSONs consumidos pelo site.

Gera dois arquivos:

- `inmet_catalogo.json`: leve, carregado no boot do painel. Uma entrada por
  estação com metadados, cobertura ano a ano e status (`medido`/`parcial`/
  `insuficiente`).
- `inmet_series.json`: pesado, carregado sob demanda ao trocar de estação.
  Contém a normal mensal (12 meses) e a série anual completa.

Uso:
    python3 dadoshistoricosinmet/exportar.py
    python3 dadoshistoricosinmet/exportar.py --destino site/public
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

DIR_BASE = Path(__file__).resolve().parent
DB_PADRAO = DIR_BASE / "inmet_nacional.sqlite"
DIR_SITE = DIR_BASE.parent / "site" / "public"

URL_SERIE = "https://portal.inmet.gov.br/dadoshistoricos"
URL_CATALOGO = "https://apitempo.inmet.gov.br/estacoes/T"

# Códigos do Litoral Sul / Vale do Ribeira, destacados no painel.
ESTACOES_REGIAO = ("A712", "A746", "A766")


def carregar_catalogo_api(caminho: Path) -> dict[str, dict]:
    """Lê o catálogo da API do INMET já versionado no site.

    Args:
        caminho: Caminho de `inmet_estacoes_brasil.json`.

    Returns:
        Mapa código -> metadados do catálogo (pode vir vazio se ausente).
    """
    if not caminho.exists():
        return {}
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {e["cod"]: e for e in dados if e.get("cod")}


def montar_catalogo(conn: sqlite3.Connection, catalogo_api: dict[str, dict]) -> dict:
    """Monta o catálogo leve: metadados + cobertura anual + status.

    Args:
        conn: Conexão com o banco nacional.
        catalogo_api: Catálogo da API para preencher estações sem série.

    Returns:
        Payload JSON pronto para escrita.
    """
    cur = conn.cursor()

    resumos = {
        r[0]: r
        for r in cur.execute("""
            SELECT codigo, periodo_inicio, periodo_fim, anos_validos, anos_com_dado,
                   chuva_anual_media, chuva_periodo_total, tmed_periodo,
                   tmax_abs, tmin_abs, urmed_periodo, cobertura, status
            FROM inmet_resumo
        """)
    }

    # Cobertura por ano: 2 = ano válido, 1 = ano com dado parcial, 0 = sem dado.
    por_ano: dict[str, dict[int, int]] = {}
    for codigo, ano, valido in cur.execute("SELECT codigo, ano, valido FROM inmet_anual"):
        por_ano.setdefault(codigo, {})[ano] = 2 if valido else 1

    estacoes = []
    vistos = set()

    for codigo, r in sorted(resumos.items()):
        (_, p_ini, p_fim, anos_val, anos_dado, chuva_med, chuva_tot,
         tmed, tmax, tmin, urmed, cobertura, status) = r

        meta = catalogo_api.get(codigo, {})
        est = cur.execute(
            "SELECT nome, uf, lat, lon, altitude, inicio FROM inmet_estacao WHERE codigo = ?",
            (codigo,),
        ).fetchone()
        nome, uf, lat, lon, alt, inicio = est

        anos = por_ano.get(codigo, {})
        primeiro = min(anos) if anos else p_ini
        ultimo = max(anos) if anos else p_fim
        # Vetor compacto de 2000..2026: 2=valido, 1=parcial, 0=vazio.
        cobertura_anos = [
            anos.get(a, 0) for a in range(2000, 2027)
        ]

        estacoes.append({
            "cod": codigo,
            "nome": (nome or meta.get("nome") or codigo).title(),
            "uf": uf or meta.get("uf") or "",
            "lat": lat if lat is not None else meta.get("lat"),
            "lon": lon if lon is not None else meta.get("lon"),
            "alt": alt if alt is not None else meta.get("alt"),
            "fund": inicio or meta.get("fund"),
            "sit": meta.get("sit", "—"),
            "status": status,
            "periodo": [primeiro, ultimo],
            "anosValidos": anos_val or 0,
            "anosComDado": anos_dado or 0,
            "cobertura": cobertura,
            "coberturaAnos": cobertura_anos,
            "chuvaAnualMedia": chuva_med,
            "chuvaPeriodoTotal": chuva_tot,
            "tmedPeriodo": tmed,
            "tmaxAbs": tmax,
            "tminAbs": tmin,
            "urmedPeriodo": urmed,
            "regional": codigo in ESTACOES_REGIAO,
        })
        vistos.add(codigo)

    # Estações do catálogo da API sem nenhuma série nos arquivos.
    for codigo, meta in catalogo_api.items():
        if codigo in vistos:
            continue
        estacoes.append({
            "cod": codigo,
            "nome": (meta.get("nome") or codigo).title(),
            "uf": meta.get("uf", ""),
            "lat": meta.get("lat"),
            "lon": meta.get("lon"),
            "alt": meta.get("alt"),
            "fund": meta.get("fund"),
            "sit": meta.get("sit", "—"),
            "status": "sem_dado",
            "periodo": [None, None],
            "anosValidos": 0,
            "anosComDado": 0,
            "cobertura": 0.0,
            "coberturaAnos": [0] * 27,
            "chuvaAnualMedia": None,
            "chuvaPeriodoTotal": None,
            "tmedPeriodo": None,
            "tmaxAbs": None,
            "tminAbs": None,
            "urmedPeriodo": None,
            "regional": codigo in ESTACOES_REGIAO,
        })

    estacoes.sort(key=lambda e: (e["uf"] or "ZZ", e["nome"] or ""))

    medidos = sum(1 for e in estacoes if e["status"] == "medido")
    parciais = sum(1 for e in estacoes if e["status"] == "parcial")
    insuficientes = sum(1 for e in estacoes if e["status"] == "insuficiente")
    sem_dado = sum(1 for e in estacoes if e["status"] == "sem_dado")

    return {
        "fonte": "INMET — Dados Históricos (portal.inmet.gov.br/dadoshistoricos)",
        "urlSerie": URL_SERIE,
        "urlCatalogo": URL_CATALOGO,
        "anos": [2000, 2026],
        "resumo": {
            "total": len(estacoes),
            "medido": medidos,
            "parcial": parciais,
            "insuficiente": insuficientes,
            "semDado": sem_dado,
            "noCatalogoApi": len(catalogo_api),
        },
        "estacoes": estacoes,
    }


def montar_series(conn: sqlite3.Connection) -> dict:
    """Monta o payload pesado: normal mensal + série anual por estação.

    Args:
        conn: Conexão com o banco nacional.

    Returns:
        Payload JSON com as séries.
    """
    cur = conn.cursor()
    series: dict[str, dict] = {}

    for codigo, mes, chuva, tmed, tmax, tmin, urmed, anos_base in cur.execute("""
        SELECT codigo, mes, chuva, tmed, tmax, tmin, urmed, anos_base
        FROM inmet_normal ORDER BY codigo, mes
    """):
        s = series.setdefault(codigo, {"normal": [], "anual": []})
        s["normal"].append({
            "m": mes, "chuva": chuva, "tmed": tmed,
            "tmax": tmax, "tmin": tmin, "ur": urmed, "n": anos_base,
        })

    for codigo, ano, chuva, tmed, tmax, tmin, ur, meses, valido in cur.execute("""
        SELECT codigo, ano, chuva_total, tmed, tmax_abs, tmin_abs, urmed, meses_com_dado, valido
        FROM inmet_anual ORDER BY codigo, ano
    """):
        s = series.setdefault(codigo, {"normal": [], "anual": []})
        s["anual"].append({
            "a": ano, "chuva": chuva, "tmed": tmed,
            "tmax": tmax, "tmin": tmin, "ur": ur,
            "meses": meses, "ok": bool(valido),
        })

    return {
        "fonte": URL_SERIE,
        "urlCatalogo": URL_CATALOGO,
        "series": series,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporta o banco do INMET para JSON do site.")
    parser.add_argument("--db", type=Path, default=DB_PADRAO)
    parser.add_argument("--destino", type=Path, default=DIR_SITE)
    args = parser.parse_args()

    if not args.db.exists():
        raise SystemExit(f"Banco não encontrado: {args.db}. Rode processar.py antes.")

    args.destino.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(args.db)

    catalogo_api = carregar_catalogo_api(args.destino / "inmet_estacoes_brasil.json")

    catalogo = montar_catalogo(conn, catalogo_api)
    saida_cat = args.destino / "inmet_catalogo.json"
    saida_cat.write_text(
        json.dumps(catalogo, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    series = montar_series(conn)
    saida_ser = args.destino / "inmet_series.json"
    saida_ser.write_text(
        json.dumps(series, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    r = catalogo["resumo"]
    print(f"Catálogo: {saida_cat.name} — {r['total']} estações "
          f"({saida_cat.stat().st_size / 1024:.0f} KB)")
    print(f"  medido={r['medido']} parcial={r['parcial']} "
          f"insuficiente={r['insuficiente']} sem_dado={r['semDado']}")
    print(f"Séries:   {saida_ser.name} — {len(series['series'])} estações "
          f"({saida_ser.stat().st_size / 1024 / 1024:.1f} MB)")
    conn.close()


if __name__ == "__main__":
    main()
