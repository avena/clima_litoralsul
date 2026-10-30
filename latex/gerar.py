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
import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "site" / "public" / "dados.json"
SAIDA = Path(__file__).resolve().parent / "fichas"
# O site serve isto: `public/` vai cru para o `dist` do Vite, então o link
# "ficha em PDF" do painel aponta para `fichas/<slug>.pdf` sem rewrite nenhum.
PUBLICO = RAIZ / "site" / "public" / "fichas"

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
        O mesmo texto com `& % $ # _ { } ~ ^ \\` escapados, e os travessões e o
        grau trocados pelos comandos que existem em T1.

    Nota:
        O `—`, o `–` e o `°` viram `\\textemdash{}`, `\\textendash{}` e
        `\\textdegree{}` porque o caractere literal só está no lugar certo em
        pdfLaTeX: o XeTeX (tectonic) manda o Unicode cru para a fonte `ec-lmr`,
        e o resultado é pior que um aviso — o `°` sai impresso como `¤`, sem
        erro nenhum. Descobri isso rasterizando a página.
    """
    mapa = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
            "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
            "^": r"\textasciicircum{}", "\\": r"\textbackslash{}",
            "\u2014": r"\textemdash{}", "\u2013": r"\textendash{}",
            "\u00b0": r"\textdegree{}"}
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
        O acumulado de cada solstício separado por bolinha, em LaTeX.

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
    return " \\,\\textbullet\\, ".join(partes)


def _itens(lista: list[dict], tamanho: str = "") -> str:
    """Converte a lista de planejamento em um `itemize` compacto.

    Args:
        lista: itens `{"titulo", "texto"}` vindos do `dados.json`.
        tamanho: declaração de tamanho a aplicar (`\\footnotesize` ou vazio).

    Returns:
        Bloco `itemize` em LaTeX, com o título em negrito e o número no texto.
        O `\\itemsep` reduzido é o que faz cinco itens caberem na página.
    """
    corpo = "\n".join(
        f"  \\item \\textbf{{{tex(i['titulo'])}}}: {tex(i['texto'])}" for i in lista)
    abertura = (f"{tamanho}\\begin{{itemize}}\\setlength{{\\itemsep}}{{0.5pt}}"
                if tamanho else "\\begin{itemize}\\setlength{\\itemsep}{0.5pt}")
    return f"{abertura}\n{corpo}\n\\end{{itemize}}"


def _kpi(rotulo: str, valor: str, rodape: str) -> str:
    """Monta um cartão de indicador em três níveis: rótulo, número e contexto.

    Args:
        rotulo: o que o número mede, ex.: `Chuva anual média`.
        valor: número já formatado, com unidade, ex.: `1.377 mm/ano`.
        rodape: quando ou onde esse número vale, ex.: `em janeiro`.

    Returns:
        Chamada de `\\kpicard` em LaTeX, sem quebra de linha no fim.
    """
    return f"\\kpicard{{{tex(rotulo)}}}{{{tex(valor)}}}{{{tex(rodape)}}}"


def ficha(est: dict, gerado: str, regiao: list[dict]) -> str:
    """Monta o `.tex` de uma página para uma estação.

    Args:
        est: estação do JSON.
        gerado: data de geração do `dados.json`, para o rodapé.
        regiao: itens de orientação válidos para todas as estações.

    Returns:
        Documento LaTeX completo em preto e branco, para pdfLaTeX ou tectonic.

    Nota:
        Toda a paleta é a escala `gray` do `xcolor`: a ficha é impressa em toner
        na ATER. Matiz não sobrevive a impressão P&B — o azul do painel vira
        cinza médio e some contra a barra. A hierarquia vem de peso de traço e de
        caixa, não de cor.
    """
    nome = tex(est["nome"])
    municipio = tex(est["municipio"])
    # "Registro Unesp" já começa com o município: "Registro --- Registro Unesp"
    # ficaria torto.
    titulo = nome if nome.startswith(municipio) else f"{municipio} --- {nome}"
    fechados = est["anos_completos"]
    ressalva = (
        f"\\textbf{{Atenção à série curta:}} apenas {fechados} anos com os 12 meses "
        f"fechados --- referência do período medido, não padrão consolidado."
        if fechados < SERIE_CURTA else
        f"\\textbf{{{fechados} anos com os 12 meses fechados}} --- médias do período "
        f"medido, não previsão do tempo."
    )
    descarte = (f" {tex(est['aviso_descarte'])}" if est.get("aviso_descarte") else "")

    chuva = [
        _kpi("Chuva anual média", f"{num(est['chuva_ano'])} mm/ano", "em todo o ano"),
        _kpi("Mês mais chuvoso", f"{num(est['chuva_max'])} mm",
             f"em {MESES_LONGOS.get(est['mes_chuvoso'], '---')}"),
        _kpi("Mês mais seco", f"{num(est['chuva_min'])} mm",
             f"em {MESES_LONGOS.get(est['mes_seco'], '---')}"),
    ]
    temperatura = [
        _kpi("Temperatura média", f"{num(est['tmed_media'], 1)} °C",
             "média dos 12 meses"),
        _kpi("Mês mais quente", f"{num(est['quente_t'], 1)} °C",
             f"em {MESES_LONGOS.get(est['quente'], '---')}"),
        _kpi("Mês mais frio", f"{num(est['frio_t'], 1)} °C",
             f"em {MESES_LONGOS.get(est['frio'], '---')}"),
    ]
    linha_chuva = "\\hfill\n".join(chuva)
    linha_temperatura = "\\hfill\n".join(temperatura)

    return rf"""\documentclass[10pt,a4paper]{{article}}
\usepackage[T1]{{fontenc}}
\usepackage[utf8]{{inputenc}}
\usepackage[brazilian]{{babel}}
\usepackage[a4paper,margin=1.5cm]{{geometry}}
\usepackage{{booktabs}}
\usepackage{{xcolor}}
\usepackage{{microtype}}
\usepackage[hidelinks]{{hyperref}}
\pagestyle{{empty}}
\setlength{{\parindent}}{{0pt}}
\setlength{{\parskip}}{{2pt}}
% Paleta monocromática: só a escala gray do xcolor, para impressão em toner.
\definecolor{{cinza}}{{gray}}{{0.35}}
\definecolor{{cinzaclaro}}{{gray}}{{0.94}}
\definecolor{{borda}}{{gray}}{{0.75}}
\definecolor{{fundocard}}{{gray}}{{0.98}}
\definecolor{{barras}}{{gray}}{{0.15}}
\newcommand{{\barra}}[1]{{\textcolor{{barras}}{{\rule{{#1mm}}{{2.4pt}}}}}}
% Cartão de indicador: rótulo, número em destaque e rodapé de contexto.
\newcommand{{\kpicard}}[3]{{%
  \fcolorbox{{borda}}{{fundocard}}{{%
    \begin{{minipage}}[c][1.4cm][c]{{\dimexpr0.32\textwidth-2\fboxsep-2\fboxrule\relax}}
      \centering
      {{\scriptsize\bfseries\color{{cinza}} #1}}\\[2pt]
      {{\Large\bfseries #2}}\\[1.5pt]
      {{\tiny\color{{cinza}} #3}}%
    \end{{minipage}}%
  }}%
}}
\begin{{document}}

{{\Large\bfseries {titulo} --- climatologia das médias}}\\[2pt]
{{\small Estação CIIAGRO/IAC {tex(str(est["id"]))} \,\textbullet\,
{est["total_meses"]} meses medidos ({est["inicio"]} a {est["fim"]})}}\\[1pt]
{{\footnotesize {ressalva}}}

\vspace{{4pt}}
\colorbox{{cinzaclaro}}{{%
\parbox{{\dimexpr\textwidth-2\fboxsep}}{{%
\footnotesize
\textbf{{Leia antes de usar:}} os números abaixo são \textbf{{médias de vários anos}},
obtidas das medições mensais do CIIAGRO. \textbf{{Não é previsão meteorológica}} para
os próximos dias nem para esta safra.\par\vspace{{2pt}}
\textbf{{Aplicação prática:}} este é o comportamento médio esperado da estação ---
base técnica para o calendário agrícola, as janelas de calagem, o preparo do solo e
o manejo conservacionista.%
}}}}

\vspace{{4pt}}
\noindent
{linha_chuva}

\vspace{{2pt}}
\noindent
{linha_temperatura}

\vspace{{4pt}}
\begin{{center}}
{{\bfseries\small Tabela 1: Chuva média por mês do ano}}\\[2pt]
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
\end{{center}}

\begin{{center}}
{{\bfseries\small Tabela 2: Chuva por estação do ano}}\\[2pt]
{{\small
\begin{{tabular}}{{@{{}}l l r r r l l@{{}}}}
\toprule
estação & meses & total (mm) & \% do ano & média/mês & maior mês & menor mês \\
\midrule
{_tabela_sazonal(est)}
\bottomrule
\end{{tabular}}}}
\end{{center}}

\vspace{{1pt}}
{{\footnotesize\textbf{{Antes dos solstícios}} (acumulado desde janeiro):
{_solsticios(est)}. Dezembro fica depois do solstício de verão e entra só no total
anual.}}

\vspace{{2pt}}
{{\bfseries\small Como usar no planejamento nesta estação}}

{_itens(est["uso"], "\\footnotesize")}

\vspace{{1pt}}
{{\bfseries\small Vale para qualquer município da região}}

{_itens(regiao, "\\scriptsize")}

\vspace{{1pt}}
{{\tiny\color{{cinza}}
Fonte: CIIAGRO/IAC (\href{{http://ciiagro.org.br}}{{ciiagro.org.br}}), série mensal
medida; chuva é o total do mês. Painel:
\href{{https://climalitoralsul.netlify.app/\#{est["slug"]}}}%
{{\texttt{{climalitoralsul.netlify.app/\#{est["slug"]}}}}}.
Umidade relativa omitida: a fonte usa \texttt{{0}} para ``sem sensor''.
{tex(est["rotulo"])}.{descarte}
Gerado a partir de \texttt{{dados.json}} de {gerado}.}}

\end{{document}}
"""


def compilar(arquivos: list[Path], destino: Path, gerado: str) -> list[Path]:
    """Compila cada `.tex` em PDF na pasta pública do site.

    Args:
        arquivos: caminhos dos `.tex` escritos por `gerar`.
        destino: diretório onde os PDFs ficam, servido pelo site.
        gerado: data do `dados.json` (AAAA-MM-DD), usada como carimbo de tempo.

    Returns:
        Lista dos PDFs gerados, na mesma ordem dos `.tex`.

    Raises:
        SystemExit: quando o `tectonic` não está instalado.

    Nota:
        `SOURCE_DATE_EPOCH` fixa o carimbo do PDF na data dos dados. Sem isso o
        `tectonic` grava a hora da compilação e o PDF muda em todo build — 15
        arquivos binários sujos no git a cada `deploy.sh`, sem nada ter mudado.
    """
    exe = shutil.which("tectonic")
    if exe is None:
        raise SystemExit(
            "tectonic não encontrado; instale com `brew install tectonic` ou "
            "compile os .tex no Overleaf e deixe os PDFs em " + str(destino))
    destino.mkdir(parents=True, exist_ok=True)
    carimbo = 0
    if gerado:
        carimbo = int(datetime.datetime.fromisoformat(gerado)
                      .replace(tzinfo=datetime.timezone.utc).timestamp())
    ambiente = {**os.environ}
    if carimbo:
        ambiente["SOURCE_DATE_EPOCH"] = str(carimbo)
    pdfs = []
    for tex in arquivos:
        subprocess.run([exe, "-X", "compile", "--outdir", str(destino), str(tex)],
                       check=True, capture_output=True, text=True, env=ambiente)
        pdfs.append(destino / f"{tex.stem}.pdf")
    return pdfs


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
    parser.add_argument("--pdf", action="store_true",
                        help="compila com tectonic para site/public/fichas")
    parser.add_argument("--pdf-em", type=Path, default=PUBLICO,
                        help="diretório dos PDFs (padrão: site/public/fichas)")
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
    if args.pdf:
        pdfs = compilar(arquivos, args.pdf_em, dados["gerado"])
        print(f"{len(pdfs)} PDFs em {args.pdf_em}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
