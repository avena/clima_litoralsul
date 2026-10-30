#!/usr/bin/env python3
"""Gera uma ficha A4 em LaTeX por estação, a partir do `dados.json` do painel.

    python3 latex/gerar.py                 # escreve latex/fichas/<slug>.tex
    python3 latex/gerar.py --saida /tmp/x  # outro diretório

Lê `site/public/dados.json`, **não** o banco. Média, faixa de sanidade, sazonal,
solstícios e o texto de planejamento já vêm decididos por `relatorio.py` — a
ficha só tipografa. Assim ela não pode contradizer o painel: o site e o PDF
mostram a mesma frase, porque a frase é uma só.

Compilar exige LaTeX (pdfLaTeX ou tectonic); este script só escreve o `.tex`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "site" / "public" / "dados.json"
SAIDA = Path(__file__).resolve().parent / "fichas"

MESES_LONGOS = {
    "jan": "janeiro", "fev": "fevereiro", "mar": "março", "abr": "abril",
    "mai": "maio", "jun": "junho", "jul": "julho", "ago": "agosto",
    "set": "setembro", "out": "outubro", "nov": "novembro", "dez": "dezembro",
}
MESES_DA_ESTACAO = {
    "Verão": ("dez", "fev"), "Outono": ("mar", "mai"),
    "Inverno": ("jun", "ago"), "Primavera": ("set", "nov"),
}
SERIE_CURTA = 10      # anos fechados abaixo disso ganham ressalva
BARRA_MM = 26.0       # largura da barra cheia, em milímetros de régua


def num(valor: float | None, casas: int = 0) -> str:
    """Formata número no padrão brasileiro, com travessão quando ausente.

    Args:
        valor: número ou `None`.
        casas: casas decimais; 0 usa separador de milhar.

    Returns:
        `1.510`, `22,7` ou `---`. Ausente vira travessão também no LaTeX, para
        buraco de série não ser lido como zero.
    """
    if valor is None:
        return "---"
    if casas == 0:
        return f"{valor:,.0f}".replace(",", ".")
    return f"{valor:.{casas}f}".replace(".", ",")


def tex(texto: str) -> str:
    """Escapa os caracteres que o LaTeX trataria como comando.

    Args:
        texto: trecho vindo do JSON (nome de estação, texto de planejamento).

    Returns:
        O mesmo texto com `& % $ # _ { } ~ ^ \\` escapados.
    """
    mapa = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
            "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
            "^": r"\textasciicircum{}", "\\": r"\textbackslash{}"}
    return "".join(mapa.get(c, c) for c in texto)


def _barra(chuva: float | None, teto: float) -> str:
    """Desenha a barra proporcional da chuva do mês, em milímetros de régua.

    Args:
        chuva: chuva média do mês, ou `None`.
        teto: maior chuva mensal da série, que ocupa a barra cheia.

    Returns:
        Comando LaTeX `\\barra{…}`; vazio quando não há medição.
    """
    if chuva is None or not teto:
        return ""
    return f"\\barra{{{BARRA_MM * chuva / teto:.1f}}}"


def _tabela_mensal(meses: list[dict]) -> str:
    """Monta a tabela mensal com barras de chuva e as três temperaturas.

    Args:
        meses: as 12 entradas de `meses` no JSON.

    Returns:
        Linhas do corpo do `tabular`, sem cabeçalho nem ambiente.
    """
    teto = max((m["chuva"] or 0) for m in meses) or 1
    linhas = []
    for m in meses:
        linhas.append(
            f'{MESES_LONGOS[m["mes"]]:<10} & {num(m["chuva"]):>5} & '
            f'{_barra(m["chuva"], teto):<14} & {num(m["tmin"], 1):>4} & '
            f'{num(m["tmed"], 1):>4} & {num(m["tmax"], 1):>4} \\\\')
    return "\n".join(linhas)


def _tabela_sazonal(est: dict) -> str:
    """Monta a tabela de chuva por estação do ano.

    Args:
        est: estação do JSON, já com `sazonal` contendo total, percentual,
        média, máximo e mínimo por estação.

    Returns:
        Linhas do corpo do `tabular`: estação, meses, total, %, média/mês e os
        meses de máximo e mínimo — o total sozinho esconde que um verão chuvoso
        pode ser um mês extremo e dois medianos.
    """
    linhas = []
    for s in est["sazonal"]:
        ini, fim = MESES_DA_ESTACAO[s["nome"]]
        linhas.append(
            f'{s["nome"]:<10} & {ini}--{fim} & {num(s["mm"]):>5} & '
            f'{num(s["pct"]):>3}\\% & {num(s["media"]):>4} & '
            f'{num(s["max"])} ({MESES_LONGOS.get(s["max_mes"], "---")[:3]}) & '
            f'{num(s["min"])} ({MESES_LONGOS.get(s["min_mes"], "---")[:3]}) \\\\')
    return "\n".join(linhas)


def _solsticios(est: dict) -> str:
    """Escreve o acumulado de chuva que antecede cada solstício.

    Args:
        est: estação do JSON, com `solsticios` calculados.

    Returns:
        Duas linhas de texto em LaTeX, uma por solstício.

    Nota:
        O acumulado vai de janeiro até o mês que antecede o solstício, e usa a
        média do mês inteiro — inclusive dos dias depois da data. É referência de
        estação, não um acumulado dia a dia.
    """
    partes = []
    for s in est["solsticios"]:
        partes.append(
            f'{s["nome"]}: {s["de"]} a {s["ate"]} somam {num(s["mm"])} mm '
            f'({num(s["pct"])}\\% do ano)')
    return " \\quad\\textbullet\\quad\n".join(partes)


def _itens(lista: list[dict], tamanho: str = "") -> str:
    """Converte a lista de planejamento em um `itemize` compacto.

    Args:
        lista: itens `{"titulo", "texto"}` vindos do `dados.json`.
        tamanho: comando de tamanho a aplicar (`\\small` ou vazio).

    Returns:
        Bloco `itemize` em LaTeX, com o título em negrito e o número no texto.
    """
    corpo = "\n".join(
        f"  \\item \\textbf{{{tex(i['titulo'])}}}: {tex(i['texto'])}" for i in lista)
    abertura = f"{tamanho}\\begin{{itemize}}\\setlength{{\\itemsep}}{{1pt}}" if tamanho \
        else "\\begin{itemize}\\setlength{\\itemsep}{1pt}"
    return f"{abertura}\n{corpo}\n\\end{{itemize}}"


def ficha(est: dict, gerado: str, regiao: list[dict]) -> str:
    """Monta o `.tex` de uma página para uma estação.

    Args:
        est: estação do JSON.
        gerado: data de geração do `dados.json`, para o rodapé.
        regiao: itens de orientação válidos para todas as estações.

    Returns:
        Documento LaTeX completo, pronto para pdfLaTeX ou tectonic.
    """
    nome = tex(est["nome"])
    municipio = tex(est["municipio"])
    # "Registro Unesp" já começa com o município: "Registro --- Registro Unesp"
    # ficaria torto.
    titulo = nome if nome.startswith(municipio) else f"{municipio} --- {nome}"
    fechados = est["anos_completos"]
    ressalva = (
        f"série curta: apenas {fechados} anos com os 12 meses fechados --- trate "
        r"como referência do período medido, não como padrão consolidado"
        if fechados < SERIE_CURTA else
        f"{fechados} anos com os 12 meses fechados"
    )
    descarte = (f"\n{tex(est['aviso_descarte'])}" if est.get("aviso_descarte") else "")
    umidade = ("Umidade relativa ficou fora: a fonte usa \\texttt{0} para ``sem "
               "sensor'', o que tornaria a média enganosa.")

    return rf"""\documentclass[10pt,a4paper]{{article}}
\usepackage[T1]{{fontenc}}
\usepackage[utf8]{{inputenc}}
\usepackage[brazilian]{{babel}}
\usepackage[a4paper,margin=1.6cm]{{geometry}}
\usepackage{{booktabs}}
\usepackage{{xcolor}}
\usepackage{{microtype}}
\usepackage[hidelinks]{{hyperref}}
\pagestyle{{empty}}
\setlength{{\parindent}}{{0pt}}
\setlength{{\parskip}}{{3pt}}
\definecolor{{chuva}}{{HTML}}{{1B7F9E}}
\definecolor{{cinza}}{{HTML}}{{666666}}
\newcommand{{\barra}}[1]{{\textcolor{{chuva}}{{\rule{{#1mm}}{{2.4pt}}}}}}
\begin{{document}}

{{\Large\bfseries {titulo} --- climatologia das médias}}\\[1pt]
{{\small Estação CIIAGRO/IAC {tex(str(est["id"]))} \,\textbullet\, {est["total_meses"]} meses
medidos ({est["inicio"]} a {est["fim"]}) \,\textbullet\, \textbf{{{ressalva}}}}}

\vspace{{3pt}}
\colorbox{{cinza!8}}{{\parbox{{\dimexpr\textwidth-2\fboxsep}}{{\small
\textbf{{Leia antes de usar:}} os números abaixo são \textbf{{médias de vários anos}},
calculadas a partir das medições mensais do CIIAGRO. \textbf{{Não é previsão do tempo}}
para amanhã nem para este ano: é o padrão médio da estação, para apoiar decisões de
calendário agrícola, manejo de solo e planejamento da propriedade.}}}}

\vspace{{5pt}}
\begin{{tabular}}{{@{{}}p{{0.31\textwidth}}p{{0.31\textwidth}}p{{0.31\textwidth}}@{{}}}}
\textbf{{Chuva anual média}} & \textbf{{Mês mais chuvoso}} & \textbf{{Mês mais seco}} \\
{{\LARGE {num(est["chuva_ano"])}}} mm/ano &
{{\LARGE {num(est["chuva_max"])}}} mm & {{\LARGE {num(est["chuva_min"])}}} mm \\
{{\small em todo o ano}} & {{\small em {MESES_LONGOS.get(est["mes_chuvoso"], "---")}}} &
{{\small em {MESES_LONGOS.get(est["mes_seco"], "---")}}} \\
\end{{tabular}}

\vspace{{3pt}}
\begin{{tabular}}{{@{{}}p{{0.31\textwidth}}p{{0.31\textwidth}}p{{0.31\textwidth}}@{{}}}}
\textbf{{Temperatura média}} & \textbf{{Mês mais quente}} & \textbf{{Mês mais frio}} \\
{{\LARGE {num(est["tmed_media"], 1)}}} °C & {num(est["quente_t"], 1)} °C &
{num(est["frio_t"], 1)} °C \\
{{\small em todo o ano}} & {{\small em {MESES_LONGOS.get(est["quente"], "---")}}} &
{{\small em {MESES_LONGOS.get(est["frio"], "---")}}} \\
\end{{tabular}}

\vspace{{6pt}}
{{\bfseries Chuva média por mês do ano}}
\vspace{{1pt}}
{{\small
\begin{{tabular}}{{@{{}}l r l r r r@{{}}}}
\toprule
mês & chuva (mm) & perfil & t mín & t méd & t máx \\
\midrule
{_tabela_mensal(est["meses"])}
\midrule
ano & {num(est["chuva_ano"])} & & & {num(est["tmed_media"], 1)} & \\
\bottomrule
\end{{tabular}}}}

\vspace{{5pt}}
{{\bfseries Chuva por estação do ano}}
\vspace{{1pt}}
{{\small
\begin{{tabular}}{{@{{}}l l r r r l l@{{}}}}
\toprule
estação & meses & total (mm) & \% do ano & média/mês & maior mês & menor mês \\
\midrule
{_tabela_sazonal(est)}
\bottomrule
\end{{tabular}}}}

\vspace{{3pt}}
{{\small\textbf{{Antes dos solstícios}} (acumulado desde janeiro)}}

{{\small
{_solsticios(est)}
\\ Dezembro fica depois do solstício de verão e entra no total anual, não nos
acumulados acima.}}

\vspace{{5pt}}
{{\bfseries Como usar no planejamento nesta estação}}
{_itens(est["uso"], "\\small")}

\vspace{{2pt}}
{{\bfseries Vale para qualquer município da região}}
{_itens(regiao, "\\footnotesize")}

\vspace{{2pt}}
{{\footnotesize\color{{cinza}}
Fonte: CIIAGRO/IAC (ciiagro.org.br), série mensal medida; chuva é o total do mês.
Painel interativo:
\href{{https://climalitoralsul.netlify.app/\#{est["slug"]}}}{{\texttt{{climalitoralsul.netlify.app/\#{est["slug"]}}}}}\\
{umidade} Rótulo do painel: {tex(est["rotulo"])}.{descarte}
Gerado a partir de \texttt{{dados.json}} de {gerado}.}}

\end{{document}}
"""


def gerar(dados: dict, destino: Path) -> list[Path]:
    """Escreve uma ficha por estação e devolve os caminhos gravados.

    Args:
        dados: conteúdo de `dados.json`.
        destino: diretório de saída.

    Returns:
        Lista de arquivos `.tex` escritos, em ordem de município.

    Efeitos:
        Cria `destino` se faltar e sobrescreve os arquivos existentes.
    """
    destino.mkdir(parents=True, exist_ok=True)
    regiao = dados.get("regiao", {}).get("uso", [])
    escritos = []
    for municipio in dados["municipios"]:
        for est in municipio["estacoes"]:
            caminho = destino / f"{est['slug']}.tex"
            caminho.write_text(ficha(est, dados["gerado"], regiao), encoding="utf-8")
            escritos.append(caminho)
    return escritos


def main(argv: list[str] | None = None) -> int:
    """CLI: gera as fichas e falha se algum valor ausente vazar para o texto.

    Args:
        argv: argumentos de linha de comando; `None` usa `sys.argv`.

    Returns:
        0 quando todas as fichas foram escritas sem `None`/`undefined` no texto,
        1 caso contrário.
    """
    parser = argparse.ArgumentParser(description="Gera fichas A4 em LaTeX.")
    parser.add_argument("--dados", type=Path, default=DADOS)
    parser.add_argument("--saida", type=Path, default=SAIDA)
    args = parser.parse_args(argv)

    dados = json.loads(args.dados.read_text(encoding="utf-8"))
    arquivos = gerar(dados, args.saida)
    sujos = [a.name for a in arquivos
             if any(marca in a.read_text(encoding="utf-8")
                    for marca in ("None", "undefined"))]
    print(f"{len(arquivos)} fichas em {args.saida}")
    if sujos:
        print("valor ausente vazou para o .tex:", ", ".join(sujos), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
