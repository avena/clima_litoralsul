#!/usr/bin/env python3
"""Exporta a série do CIIAGRO como JSON para o dashboard React.

    python3 relatorio.py                  # site/public/dados.json
    python3 relatorio.py --saida /tmp/x.json

O cálculo que exige honestidade — média mensal, chuva anual, estações do ano,
faixa de sanidade, rótulo "normal climatológica" — mora aqui, em Python testado.
O `site/` (Vite + React + Tailwind) só desenha. Reimplementar essas regras em
JavaScript criaria duas versões da mesma mentira possível.

Sem dependência: só stdlib. Nada aqui escreve no banco.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import unicodedata
from datetime import date
from pathlib import Path

from coletor import DB, abrir

SAIDA = Path(__file__).with_name("site") / "public" / "dados.json"
MESES = ("jan", "fev", "mar", "abr", "mai", "jun",
         "jul", "ago", "set", "out", "nov", "dez")

# Faixas de sanidade: fora disso a leitura é defeito da fonte, não clima.
# Chuva mensal acima de 1000 mm já é suspeita no litoral paulista.
LIMITE_CHUVA_MES = 1000
LIMITES = (("tmin", -20, 50), ("tmed", -20, 50), ("tmax", -20, 50),
           ("urmed", 0, 100), ("chuva", 0, LIMITE_CHUVA_MES))

ESTACOES_DO_ANO = (("Verão", ("dez", "jan", "fev")), ("Outono", ("mar", "abr", "mai")),
                   ("Inverno", ("jun", "jul", "ago")), ("Primavera", ("set", "out", "nov")))


def slug(nome: str) -> str:
    """Converte nome de município em identificador de URL sem acento nem espaço.

    Args:
        nome: nome como está no banco, ex.: `Pariquera-Açu`.

    Returns:
        `pariquera-acu`. É o `slug` usado no link `#/pariquera-acu` do dashboard.

    Nota:
        Sem acento para o link poder ser digitado e colado sem `%C3%A7`.
    """
    plano = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return "-".join(plano.lower().replace("-", " ").split())


def _ok(valor: float | None, lo: float, hi: float) -> bool:
    """Diz se a leitura está dentro da faixa de sanidade.

    Args:
        valor: leitura ou `None`.
        lo: mínimo aceitável, inclusivo.
        hi: máximo aceitável, inclusivo.

    Returns:
        `False` para `None` e para valor fora de `[lo, hi]`. Usado para
        descartar da média sem apagar do banco.
    """
    return valor is not None and lo <= valor <= hi


def _media(valores: list[float | None]) -> float | None:
    """Média ignorando ausentes.

    Args:
        valores: leituras, possivelmente com `None`.

    Returns:
        A média, ou `None` se não houver nenhum valor — nunca 0 no lugar de
        "sem dado".
    """
    reais = [v for v in valores if v is not None]
    return sum(reais) / len(reais) if reais else None


def agregado(conn: sqlite3.Connection, ponto_id: str) -> dict:
    """Resume a série de uma estação em médias por mês do ano.

    Args:
        conn: conexão aberta por `coletor.abrir`.
        ponto_id: código CIIAGRO da estação.

    Returns:
        Dict com `inicio`, `fim`, `n_meses`, `anos`, `por_mes` (12 entradas),
        `chuva_ano` (média dos anos com os 12 meses), `anos_completos` e
        `descartes` (quantas leituras ficaram fora por coluna).

    Nota:
        Só linhas mensais (`length(data) = 7`): somar mensal com diário contaria
        o mês duas vezes.

        Leitura fora de `LIMITES` não entra na média e é contada em `descartes`.
        O banco guarda o valor original — a fonte se corrompe (Miracatu tem
        `tmed = 873,35` em 03/1990) e publicar isso como temperatura seria pior
        do que admitir o descarte.
    """
    linhas = conn.execute(
        "SELECT substr(data, 1, 7) AS mes, tmin, tmed, tmax, urmed, chuva FROM fato "
        "WHERE ponto_id = ? AND length(data) = 7 ORDER BY 1", (ponto_id,)).fetchall()
    if not linhas:
        return {"inicio": None, "fim": None, "n_meses": 0, "anos": 0.0,
                "por_mes": [], "chuva_ano": None, "anos_completos": 0,
                "descartes": {}}

    descartes = {nome: 0 for nome, *_ in LIMITES}
    por_mes = []
    for i in range(1, 13):
        do_mes = [l for l in linhas if int(l["mes"][5:7]) == i]
        medias = {}
        for nome, lo, hi in LIMITES:
            valores = [l[nome] for l in do_mes]
            medias[nome] = _media([v for v in valores if _ok(v, lo, hi)])
            descartes[nome] += sum(1 for v in valores if v is not None and not _ok(v, lo, hi))
        por_mes.append({"mes": MESES[i - 1], "n": len(do_mes), **medias})

    por_ano: dict[str, list] = {}
    for l in linhas:
        if _ok(l["chuva"], 0, LIMITE_CHUVA_MES):
            por_ano.setdefault(l["mes"][:4], []).append(l["chuva"])
    totais = [sum(v) for v in por_ano.values() if len(v) == 12]
    return {
        "inicio": linhas[0]["mes"],
        "fim": linhas[-1]["mes"],
        "n_meses": len(linhas),
        "anos": len(linhas) / 12,
        "por_mes": por_mes,
        "chuva_ano": _media(totais),
        "anos_completos": len(totais),
        "descartes": descartes,
    }


def normal(ag: dict, validada: bool) -> bool:
    """Diz se a série pode receber o rótulo de normal climatológica.

    Args:
        ag: resultado de `agregado`.
        validada: se a série começa depois do início declarado pelo CIIAGRO.

    Returns:
        `True` só com 30 anos ou mais **e** série validada. Série que começa
        antes do início declarado é de origem desconhecida: chamá-la de normal
        afirmaria uma validação que ninguém fez.
    """
    return ag["anos"] >= 30 and validada


def rotulo(ag: dict, validada: bool) -> str:
    """Diz o que a tabela é, sem prometer mais do que o dado sustenta.

    Args:
        ag: resultado de `agregado`.
        validada: se a série começa depois do início declarado pelo CIIAGRO.

    Returns:
        `"normal climatológica"` só quando `normal` é verdadeiro; senão o
        período com a ressalva de série não validada.
    """
    if normal(ag, validada):
        return "normal climatológica"
    sufixo = "" if validada else "; parte da série não validada"
    return (f"médias do período {ag['inicio'][:4]}–{ag['fim'][:4]}"
            f" ({ag['anos']:.1f} anos de dado{sufixo})")


def resumo(ag: dict) -> dict:
    """Extrai os indicadores que vão nos cards de KPI.

    Args:
        ag: resultado de `agregado`.

    Returns:
        Dict com chuva anual, mês mais e menos chuvoso, média térmica, mês mais
        quente e mais frio por `tmed`, amplitude sazonal, UR média, faixa térmica
        e o acumulado por estação do ano (DJF, MAM, JJA, SON).

    Nota:
        Estações do ano pelo mês civil do hemisfério sul. Como cada mês entra
        com a média dos anos, a soma das quatro estações é exatamente a chuva
        anual — é o que permite apresentar percentual sem inventar peso.
    """
    pm = ag["por_mes"]
    chuvas = [m["chuva"] for m in pm if m["chuva"] is not None]
    quentes = [m for m in pm if m["tmed"] is not None]
    ur = _media([m["urmed"] for m in pm])

    sazonal = []
    for nome, meses in ESTACOES_DO_ANO:
        valores = [m["chuva"] for m in pm if m["mes"] in meses and m["chuva"] is not None]
        sazonal.append({"nome": nome, "mm": sum(valores) if valores else None})

    return {
        "chuva_ano": ag["chuva_ano"],
        "chuva_max": max(chuvas) if chuvas else None,
        "mes_chuvoso": (max(pm, key=lambda m: m["chuva"] or -1)["mes"] if chuvas else None),
        "mes_seco": (min(pm, key=lambda m: m["chuva"] if m["chuva"] is not None else 1e9)["mes"]
                     if chuvas else None),
        "chuva_min": min(chuvas) if chuvas else None,
        "tmed_media": _media([m["tmed"] for m in pm]),
        "tmin_global": min((m["tmin"] for m in pm if m["tmin"] is not None), default=None),
        "tmax_global": max((m["tmax"] for m in pm if m["tmax"] is not None), default=None),
        "quente": (max(quentes, key=lambda m: m["tmed"])["mes"] if quentes else None),
        "quente_t": (max(quentes, key=lambda m: m["tmed"])["tmed"] if quentes else None),
        "frio": (min(quentes, key=lambda m: m["tmed"])["mes"] if quentes else None),
        "frio_t": (min(quentes, key=lambda m: m["tmed"])["tmed"] if quentes else None),
        "amplitude": (max(quentes, key=lambda m: m["tmed"])["tmed"]
                      - min(quentes, key=lambda m: m["tmed"])["tmed"] if quentes else None),
        "ur": ur,
        "sazonal": sazonal,
    }


def _estacao(conn: sqlite3.Connection, p: sqlite3.Row) -> dict | None:
    """Monta o JSON de uma estação, ou `None` quando não há dado coletado.

    Args:
        conn: conexão aberta por `coletor.abrir`.
        p: linha de `ponto` com `id`, `nome`, `inicio_auto` e `primeiro_fato`.

    Returns:
        Dict pronto para o dashboard. `aviso` e `descartes` só aparecem quando
        há o que avisar, para o front não precisar decidir se o texto importa.
    """
    ag = agregado(conn, p["id"])
    if not ag["n_meses"]:
        return None
    validada = not (p["primeiro_fato"] and p["inicio_auto"]
                    and p["primeiro_fato"][:7] < p["inicio_auto"][:7])
    total = sum(ag["descartes"].values())
    return {
        "id": p["id"],
        "nome": p["nome"],
        "inicio": ag["inicio"],
        "fim": ag["fim"],
        "total_meses": ag["n_meses"],
        "anos": round(ag["anos"], 1),
        "normal": normal(ag, validada),
        "rotulo": rotulo(ag, validada),
        "aviso": (None if validada else
                  f"Série começa antes do início declarado pelo CIIAGRO "
                  f"({p['inicio_auto']}). Pode ser registro histórico convencional "
                  f"ou reconstrução — não validado, e por isso não recebe o rótulo "
                  f"de normal climatológica."),
        "aviso_descarte": (None if not total else
                           f"{total} leitura(s) fora da faixa de sanidade excluída(s) "
                           f"da média ("
                           + ", ".join(f"{n} {v}" for n, v in ag["descartes"].items() if v)
                           + "); o banco as preserva."),
        "anos_completos": ag["anos_completos"],
        "meses": ag["por_mes"],
        **resumo(ag),
    }


def exportar(conn: sqlite3.Connection) -> dict:
    """Monta o pacote JSON completo que o dashboard consome.

    Args:
        conn: conexão aberta por `coletor.abrir`.

    Returns:
        Dict com `gerado` (data), `fonte` e `municipios`; cada município traz
        `slug`, `nome` e `estacoes`. Cada estação traz `slug` e `municipio`, que
        são a sua rota no painel (`#/registro-unesp`). Município sem estação
        aparece com a lista vazia — quem decide como mostrar isso é o front.

    Nota:
        A lista de municípios vem da tabela `municipio`, inclusive os 4 sem
        estação: sumir com eles transformaria "não há dado" em "não existe".

        O `slug` da estação, e não o do município, é a rota: Registro e
        Pariquera-Açu têm duas estações cada, e a URL precisa dizer qual.
    """
    municipios = []
    for mun_id, mun in conn.execute("SELECT id, nome FROM municipio ORDER BY nome"):
        estacoes = []
        for p in conn.execute(
                "SELECT id, nome, inicio_auto, primeiro_fato FROM ponto "
                "WHERE municipio_id = ? ORDER BY nome", (mun_id,)):
            estacao = _estacao(conn, p)
            if estacao:
                estacao["slug"] = slug(p["nome"])
                estacao["municipio"] = mun
                estacoes.append(estacao)
        municipios.append({"slug": slug(mun), "nome": mun, "estacoes": estacoes})
    return {"gerado": date.today().isoformat(), "fonte": "CIIAGRO",
            "municipios": municipios}


def escrever(conn: sqlite3.Connection, destino: Path = SAIDA) -> Path:
    """Grava o JSON do dashboard.

    Args:
        conn: conexão aberta por `coletor.abrir`.
        destino: caminho do arquivo; por padrão `site/public/dados.json`.

    Returns:
        O caminho escrito.

    Efeitos:
        Cria o diretório se faltar e sobrescreve o arquivo. Não toca no banco.

    Nota:
        O arquivo vai para `site/public/` porque é servido como está pelo Vite
        e copiado para `dist/` no build; assim o deploy não depende do banco.
    """
    dados = exportar(conn)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")),
                       encoding="utf-8")
    return destino


def main(argv: list[str] | None = None) -> int:
    """CLI: exporta o JSON do dashboard a partir do banco."""
    parser = argparse.ArgumentParser(description="Exporta o JSON do dashboard.")
    parser.add_argument("--saida", type=Path, default=SAIDA)
    parser.add_argument("--db", type=Path, default=DB)
    args = parser.parse_args(argv)
    conn = abrir(args.db)
    try:
        caminho = escrever(conn, args.saida)
    finally:
        conn.close()
    quantas = sum(len(m["estacoes"]) for m in json.loads(caminho.read_text("utf-8"))["municipios"])
    print(f"{args.saida} · {quantas} estações · {caminho.stat().st_size // 1024} KiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
