#!/usr/bin/env python3
"""Relatórios climáticos estáticos, gerados do banco do coletor.

    python3 relatorio.py              # todos os municípios com estação
    python3 relatorio.py Registro     # um município
    ./start.sh                        # gera e abre em http://localhost:8000

Saída em `relatorios/`: um HTML por município e um índice. Só stdlib, sem
template engine — `str.join` basta para uma tabela.

Limite conhecido: o banco é mensal, então não existe "dias com chuva ≥ 1 mm"
nem veranico aqui. Isso exige `coletar --diario` primeiro.
"""
from __future__ import annotations

import argparse
import sqlite3
import unicodedata
from pathlib import Path

from coletor import DB, abrir

SAIDA = Path(__file__).with_name("relatorios")
MESES = ("jan", "fev", "mar", "abr", "mai", "jun",
         "jul", "ago", "set", "out", "nov", "dez")
TRAVESSAO = "—"

# Faixas de sanidade: fora disso a leitura é defeito da fonte, não clima.
# Chuva mensal acima de 1000 mm já é suspeita no litoral paulista.
LIMITE_CHUVA_MES = 1000
LIMITES = (("tmin", -20, 50), ("tmed", -20, 50), ("tmax", -20, 50),
           ("urmed", 0, 100), ("chuva", 0, LIMITE_CHUVA_MES))

CSS = """
body{font:15px/1.5 system-ui,sans-serif;max-width:52rem;margin:2rem auto;padding:0 1rem;color:#1a1a1a}
h1{font-size:1.6rem;margin-bottom:.2rem}h2{font-size:1.15rem;margin:2rem 0 .3rem}
small{font-weight:400;color:#666}
.meta{color:#555;margin:.2rem 0 .8rem}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{padding:.3rem .4rem;text-align:right;border-bottom:1px solid #eee}
th:first-child,td:first-child{text-align:left}
thead th{border-bottom:2px solid #ccc;font-size:.85rem;color:#444}
tfoot td{font-weight:600;border-top:2px solid #ccc}
.bar{height:.55rem;background:#3b82f6;border-radius:2px;display:block;min-width:1px}
.barcell{width:8rem}.barcell div{background:#f1f5f9;border-radius:2px}
.fonte{color:#666;font-size:.85rem;margin:.6rem 0 0}
.alerta{background:#fff7ed;border-left:3px solid #f59e0b;padding:.5rem .7rem;font-size:.9rem}
ul.municipios{list-style:none;padding:0}ul.municipios li{padding:.35rem 0;border-bottom:1px solid #eee}
ul.municipios a{text-decoration:none;color:#1d4ed8}
"""


def slug(nome: str) -> str:
    """Converte nome de município em nome de arquivo sem acento nem espaço.

    Args:
        nome: nome como está no CSV, ex.: `Pariquera-Açu`.

    Returns:
        `pariquera-acu`. Serve para o arquivo ser linkável sem `%C3%A7` na URL.
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


def _fmt(valor: float | None, casas: int = 1) -> str:
    """Formata número com vírgula decimal, ou travessão quando não há medição."""
    return TRAVESSAO if valor is None else f"{valor:.{casas}f}".replace(".", ",")


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


def rotulo(ag: dict, validada: bool) -> str:
    """Diz o que a tabela é, sem prometer mais do que o dado sustenta.

    Args:
        ag: resultado de `agregado`.
        validada: se a série começa depois do início declarado pelo CIIAGRO.

    Returns:
        `"normal climatológica"` só com 30 anos ou mais **e** série validada.
        Série que começa antes do início declarado é de origem desconhecida, e
        chamá-la de normal afirmaria o que ninguém verificou.
    """
    if ag["anos"] >= 30 and validada:
        return "normal climatológica"
    sufixo = "" if validada else "; parte da série não validada"
    return (f"médias do período {ag['inicio'][:4]}–{ag['fim'][:4]}"
            f" ({_fmt(ag['anos'])} anos de dado{sufixo})")


def _tabela(ag: dict) -> str:
    """Monta a tabela de 12 meses, com barra de chuva proporcional ao maior mês."""
    pico = max((m["chuva"] or 0 for m in ag["por_mes"]), default=0) or 1
    linhas = []
    for m in ag["por_mes"]:
        largura = 0 if m["chuva"] is None else m["chuva"] / pico * 100
        linhas.append(
            f"<tr><td>{m['mes']}</td><td>{_fmt(m['chuva'])}</td>"
            f"<td class='barcell'><div><span class='bar' style='width:{largura:.0f}%'>"
            f"</span></div></td>"
            f"<td>{_fmt(m['tmin'])}</td><td>{_fmt(m['tmed'])}</td><td>{_fmt(m['tmax'])}</td>"
            f"<td>{_fmt(m['urmed'], 0)}</td><td>{m['n'] or TRAVESSAO}</td></tr>")
    ano = _fmt(ag["chuva_ano"], 0)
    linhas.append(
        f"<tr><td>ano</td><td>{ano}</td><td></td><td colspan='3'></td><td></td>"
        f"<td>{ag['anos_completos'] or TRAVESSAO}</td></tr>")
    return (
        "<table><thead><tr><th>mês</th><th>chuva (mm)</th><th></th><th>t mín</th>"
        "<th>t méd</th><th>t máx</th><th>UR %</th><th>n</th></tr></thead>"
        "<tbody>" + "".join(linhas) + "</tbody></table>")


def _estacao(conn: sqlite3.Connection, p: sqlite3.Row) -> str:
    """Renderiza uma estação: cabeçalho, tabela, descartes e proveniência."""
    ag = agregado(conn, p["id"])
    if not ag["n_meses"]:
        return f"<h2>{p['nome']}</h2><p class='meta'>sem dado coletado.</p>"
    validada = not (p["primeiro_fato"] and p["inicio_auto"]
                    and p["primeiro_fato"][:7] < p["inicio_auto"][:7])
    aviso = ""
    if not validada:
        aviso = (f"<p class='alerta'>Série começa antes do início declarado pelo "
                 f"CIIAGRO ({p['inicio_auto']}). Pode ser registro histórico "
                 f"convencional ou reconstrução — não validado, e por isso não "
                 f"recebe o rótulo de normal climatológica.</p>")
    total_descarte = sum(ag["descartes"].values())
    descarte = ""
    if total_descarte:
        detalhe = ", ".join(f"{n} {v}" for n, v in ag["descartes"].items() if v)
        descarte = (f" {total_descarte} leitura(s) fora da faixa de sanidade "
                    f"excluída(s) da média ({detalhe}); o banco as preserva.")
    return (
        f"<h2>{p['nome']} <small>estação {p['id']}</small></h2>"
        f"<p class='meta'>{ag['inicio']} a {ag['fim']} · {ag['n_meses']} meses · "
        f"<strong>{rotulo(ag, validada)}</strong></p>"
        + _tabela(ag) + aviso +
        f"<p class='fonte'>Fonte: CIIAGRO. Médias da série mensal; chuva é o total "
        f"do mês, {ag['anos_completos']} anos com os 12 meses.{descarte}</p>")


def _pagina(titulo: str, corpo: str) -> str:
    """Envolve o conteúdo no HTML mínimo com o CSS embutido."""
    return ("<!doctype html><html lang='pt-BR'><meta charset='utf-8'>"
            f"<title>{titulo}</title><style>{CSS}</style>"
            f"<body><h1>{titulo}</h1>{corpo}"
            "<p class='fonte'><a href='index.html'>todos os municípios</a></p>"
            "</body></html>")


def gerar(conn: sqlite3.Connection, filtro: list[str]) -> list[Path]:
    """Escreve um HTML por município e o índice.

    Args:
        conn: conexão aberta por `coletor.abrir`.
        filtro: nomes de município a gerar; vazio gera todos.

    Returns:
        Caminhos dos arquivos escritos.

    Efeitos:
        Cria/sobrescreve arquivos em `relatorios/`. Não toca no banco.
    """
    SAIDA.mkdir(exist_ok=True)
    estacoes = conn.execute(
        "SELECT p.id, p.nome, p.inicio_auto, p.primeiro_fato, m.id AS mun_id, m.nome AS mun "
        "FROM ponto p JOIN municipio m ON m.id = p.municipio_id "
        "ORDER BY m.nome, p.nome").fetchall()
    alvo = {slug(n) for n in filtro}
    escritos: list[Path] = []
    itens: list[str] = []

    for mun_id, mun in conn.execute("SELECT id, nome FROM municipio ORDER BY nome"):
        if alvo and slug(mun) not in alvo:
            continue
        minhas = [e for e in estacoes if e["mun_id"] == mun_id]
        if minhas:
            corpo = "".join(_estacao(conn, e) for e in minhas)
            ags = [agregado(conn, e["id"]) for e in minhas]
            inicios = [a["inicio"] for a in ags if a["inicio"]]
            fim = max((a["fim"] for a in ags if a["fim"]), default=None)
            periodo = f"{min(inicios)} a {fim}" if inicios else "sem dado"
            quantas = "estação" if len(minhas) == 1 else "estações"
            itens.append(
                f"<li><a href='{slug(mun)}.html'>{mun}</a> — {len(minhas)} {quantas}, "
                f"{periodo}</li>")
        else:
            corpo = "<p class='meta'>Nenhuma estação do CIIAGRO neste município.</p>"
            itens.append(f"<li><strong>{mun}</strong> — sem estação CIIAGRO</li>")
        caminho = SAIDA / f"{slug(mun)}.html"
        caminho.write_text(_pagina(f"Clima — {mun}", corpo), encoding="utf-8")
        escritos.append(caminho)

    indice = ("<p class='meta'>Série mensal do CIIAGRO para os municípios do Litoral "
              "Sul Paulista. 23 estações, 1990–2026.</p>"
              f"<ul class='municipios'>{''.join(itens)}</ul>")
    (SAIDA / "index.html").write_text(_pagina("Clima — Litoral Sul Paulista", indice),
                                      encoding="utf-8")
    escritos.append(SAIDA / "index.html")
    return escritos


def main(argv: list[str] | None = None) -> int:
    """CLI: gera os relatórios de todos os municípios ou dos nomes passados."""
    parser = argparse.ArgumentParser(description="Relatórios HTML a partir do banco.")
    parser.add_argument("municipio", nargs="*", help="nomes; vazio = todos")
    parser.add_argument("--db", type=Path, default=DB)
    args = parser.parse_args(argv)
    conn = abrir(args.db)
    try:
        escritos = gerar(conn, args.municipio)
    finally:
        conn.close()
    print(f"{len(escritos)} arquivos em {SAIDA}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
