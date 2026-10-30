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
from municipios import regioes as grupos

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

# Solstícios, em data média: 21/06 e 21/12. O acumulado "antes" é do começo do
# ano civil até o mês que antecede o solstício — mede quanta água a estação já
# recebeu quando o dia vira, não a chuva do verão sinótico.
SOLSTICIOS = (("inverno", "junho", MESES[:5]), ("verão", "dezembro", MESES[5:11]))

# Limiares do texto de planejamento. São convenções declaradas, não medidas: o
# leitor precisa saber onde a ficha troca de conselho.
LIMITE_SECO = 100      # mm/mês: abaixo disso a ficha chama de janela seca
LIMITE_UMIDO = 120     # mm/mês: acima disso há água para corretivo em cobertura
SERIE_CURTA = 10       # anos fechados abaixo disso ganham ressalva

NOMES_LONGOS = {"jan": "janeiro", "fev": "fevereiro", "mar": "março", "abr": "abril",
                "mai": "maio", "jun": "junho", "jul": "julho", "ago": "agosto",
                "set": "setembro", "out": "outubro", "nov": "novembro", "dez": "dezembro"}


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


def _br(valor: float | None, casas: int = 0) -> str:
    """Formata número no padrão brasileiro para o texto de planejamento.

    Args:
        valor: número ou `None`.
        casas: casas decimais; 0 usa separador de milhar.

    Returns:
        `1.510`, `22,7` ou `---`. `None` vira travessão também no texto, para
        buraco de série não ser lido como zero.
    """
    if valor is None:
        return "---"
    if casas == 0:
        return f"{valor:,.0f}".replace(",", ".")
    return f"{valor:.{casas}f}".replace(".", ",")


def _soma(pm: list[dict], meses) -> float | None:
    """Soma a chuva de um conjunto de meses do ano.

    Args:
        pm: médias por mês do ano.
        meses: siglas a somar.

    Returns:
        Total em mm, ou `None` se qualquer mês do conjunto não tiver medição —
        somar o que existe daria um total menor e mais "seco" do que a série.
    """
    chuva = {m["mes"]: m["chuva"] for m in pm}
    valores = [chuva.get(sigla) for sigla in meses]
    if any(v is None for v in valores):
        return None
    return sum(valores)


def solsticios(pm: list[dict], chuva_ano: float | None) -> list[dict]:
    """Chuva acumulada no ano até o mês que antecede cada solstício.

    Args:
        pm: médias por mês do ano.
        chuva_ano: chuva média anual, para o percentual.

    Returns:
        Duas entradas `{"nome", "solsticio", "de", "ate", "mm", "pct"}`: janeiro
        a maio (antes do solstício de inverno, 21/06) e junho a novembro (antes
        do de verão, 21/12). Dezembro fica depois do solstício e por isso não
        entra em nenhum dos dois.

    Nota:
        As datas dos solstícios são as médias de calendário (21/06 e 21/12);
        a chuva é a média do mês inteiro, inclusive a dos dias posteriores ao
        solstício. É uma referência de estação, não um acumulado dia a dia.
    """
    itens = []
    for nome, mes_solsticio, meses in SOLSTICIOS:
        total = _soma(pm, meses)
        itens.append({
            "nome": nome,
            "solsticio": mes_solsticio,
            "de": NOMES_LONGOS[meses[0]],
            "ate": NOMES_LONGOS[meses[-1]],
            "mm": total,
            "pct": (100 * total / chuva_ano) if total is not None and chuva_ano else None,
        })
    return itens


def janela_seca(pm: list[dict], seco: str | None, limite: int = LIMITE_SECO) -> list[str]:
    """Lista os meses secos em sequência, ao redor do mês mais seco.

    Args:
        pm: médias por mês do ano.
        seco: sigla do mês mais seco, centro da janela.
        limite: mm abaixo do qual o mês conta como seco.

    Returns:
        Siglas dos meses contíguos abaixo do limiar, em ordem do ano civil.
        Vazio quando o próprio mês mais seco passa do limiar.

    Nota:
        Exijo contiguidade porque listar todo mês abaixo de 100 mm junta, por
        exemplo, abril a agosto com um novembro de 97 mm — ruído do limiar, não
        janela de preparo.
    """
    chuva = {m["mes"]: m["chuva"] for m in pm}
    if not seco or seco not in chuva or chuva[seco] is None or chuva[seco] >= limite:
        return []
    i = MESES.index(seco)
    inicio = fim = i
    while True:
        proximo = (fim + 1) % len(MESES)
        if proximo == inicio or not _abaixo(chuva, MESES[proximo], limite):
            break
        fim = proximo
    while True:
        anterior = (inicio - 1) % len(MESES)
        if anterior == fim or not _abaixo(chuva, MESES[anterior], limite):
            break
        inicio = anterior
    if inicio <= fim:
        return list(MESES[inicio:fim + 1])
    return list(MESES[inicio:] + MESES[:fim + 1])


def _abaixo(chuva: dict, sigla: str, limite: int) -> bool:
    """Diz se a chuva média do mês fica abaixo do limiar.

    Args:
        chuva: mapa sigla → chuva média.
        sigla: mês a testar.
        limite: mm.

    Returns:
        `True` quando há medição e ela é menor que o limiar.
    """
    valor = chuva.get(sigla)
    return valor is not None and valor < limite


def inicio_das_chuvas(pm: list[dict], seco: str | None,
                      limite: int = LIMITE_UMIDO) -> str | None:
    """Acha o mês em que a chuva volta a passar do limiar depois do mês mais seco.

    Args:
        pm: médias por mês do ano.
        seco: sigla do mês mais seco, ponto de partida da varredura.
        limite: mm que marca "há água no perfil".

    Returns:
        Sigla do primeiro mês úmido na ordem cíclica (o mais seco não conta), ou
        `None` se a estação nunca alcança o limiar.

    Nota:
        A varredura é cíclica porque o primeiro mês úmido do ano civil é
        janeiro — plena estação chuvosa — e a ficha mandaria aplicar calcário no
        pior momento possível.
    """
    chuva = {m["mes"]: m["chuva"] for m in pm}
    if not seco or seco not in chuva:
        return None
    i = MESES.index(seco)
    for passo in range(1, len(MESES)):
        sigla = MESES[(i + passo) % len(MESES)]
        if not _abaixo(chuva, sigla, limite):
            return sigla
    return None


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
    total = ag["chuva_ano"]
    for nome, meses in ESTACOES_DO_ANO:
        valores = [m["chuva"] for m in pm if m["mes"] in meses and m["chuva"] is not None]
        soma = sum(valores) if valores else None
        sazonal.append({
            "nome": nome,
            "mm": soma,
            "pct": (100 * soma / total) if soma is not None and total else None,
            "media": (soma / len(meses)) if soma is not None else None,
            "max": max(valores) if valores else None,
            "max_mes": (max((m for m in pm if m["mes"] in meses and m["chuva"] is not None),
                            key=lambda m: m["chuva"])["mes"] if valores else None),
            "min": min(valores) if valores else None,
            "min_mes": (min((m for m in pm if m["mes"] in meses and m["chuva"] is not None),
                            key=lambda m: m["chuva"])["mes"] if valores else None),
        })

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


USO_GERAL = (
    {"titulo": "Média não é previsão",
     "texto": "Descrevem o padrão de vários anos, não o tempo deste ano: use para "
              "escolher a janela de cada operação, e decida no campo."},
    {"titulo": "Corrija antes de precisar",
     "texto": "Calcário reage em meses; aplicado na janela seca, chega ao plantio "
              "já reagido."},
    {"titulo": "Chuva em mm não é água no solo",
     "texto": "Textura, declive e cobertura morta decidem quanto do que cai chega à "
              "raiz."},
    {"titulo": "Série curta é pista, não padrão",
     "texto": "Poucos anos fechados oscilam muito: compare com a estação vizinha "
              "antes de fixar calendário."},
)


def uso_local(est: dict) -> list[dict]:
    """Traduz os números da estação em decisões de calendário agrícola.

    Args:
        est: estação já com `meses`, `sazonal`, `mes_seco`, `chuva_max`,
            `quente`, `quente_t`, `frio` e `frio_t`.

    Returns:
        Lista de `{"titulo", "texto"}`. Cada item cita o número que o sustenta;
        quando o limiar não se aplica, o item diz por quê em vez de inventar
        conselho — Iguape não tem janela seca, e escrever "aproveite o mês seco"
        seria tão errado quanto dizer que chove igual o ano todo.

    Nota:
        O texto sai daqui, e não do JavaScript nem do LaTeX, porque site e ficha
        precisam dizer a mesma coisa. Foi escrito à mão por cidade uma vez, e duas
        frases saíram contra os dados: mínima de junho em Barra do Turvo (14,6 °C,
        não "abaixo de 10") e "mais de 40% da chuva" em Jacupiranga (39,8%).
    """
    pm = est["meses"]
    itens = []

    secos = janela_seca(pm, est.get("mes_seco"))
    chuva_seca = [m["chuva"] for m in pm if m["mes"] in secos and m["chuva"] is not None]
    menor = min((m["chuva"] for m in pm if m["chuva"] is not None), default=None)
    if secos:
        nomes = ", ".join(NOMES_LONGOS[m] for m in secos[:-1])
        nomes = f"{nomes} e {NOMES_LONGOS[secos[-1]]}" if nomes else NOMES_LONGOS[secos[-1]]
        faixa = (f"entre {_br(min(chuva_seca))} e {_br(max(chuva_seca))} mm/mês"
                 if min(chuva_seca) != max(chuva_seca)
                 else f"em {_br(min(chuva_seca))} mm/mês")
        ressalva = (" Como até o mês mais seco passa de 60 mm, o solo raramente seca: "
                    "a janela vale para entrar com máquina, não para preparo em solo seco."
                    if menor and menor > 60 else "")
        itens.append({
            "titulo": "Amostragem de solo e preparo mecânico",
            "texto": f"Em {nomes} a chuva média fica {faixa} — é a janela de menor "
                     f"encharcamento para retirar terra para laudo, arar e incorporar "
                     f"calcário com antecedência.{ressalva}",
        })
    else:
        itens.append({
            "titulo": "Amostragem de solo",
            "texto": f"Nenhum mês fica abaixo de {LIMITE_SECO} mm nesta estação, então "
                     f"não há janela seca definida. Programe a coleta entre dois eventos "
                     f"de chuva e evite entrar com máquina em solo encharcado.",
        })

    inicio = inicio_das_chuvas(pm, est.get("mes_seco"))
    if inicio:
        itens.append({
            "titulo": "Calagem em cobertura (pasto e perene já formado)",
            "texto": f"A partir de {NOMES_LONGOS[inicio]}, quando a média volta a passar "
                     f"de {LIMITE_UMIDO} mm/mês: aí há água para o corretivo descer no "
                     f"perfil sem enxurrada.",
        })
    else:
        itens.append({
            "titulo": "Calagem em cobertura",
            "texto": f"Sem mês acima de {LIMITE_UMIDO} mm, a chuva não garante a descida "
                     f"do corretivo em superfície. Prefira incorporar no preparo ou "
                     f"irrigar a área.",
        })

    verao = next((s for s in est["sazonal"] if s["nome"] == "Verão" and s["mm"]), None)
    if verao:
        itens.append({
            "titulo": "Plantio e transplante",
            "texto": f"O verão (dezembro a fevereiro) concentra {_br(verao['mm'])} mm, "
                     f"{_br(verao['pct'])}% da chuva do ano — favorece o pegamento de "
                     f"mudas sem irrigação pesada; em áreas declivosas, reforce a "
                     f"conservação de solo nesse período.",
        })

    if est.get("chuva_max") and est["chuva_max"] >= 200:
        itens.append({
            "titulo": "Excesso de chuva e conservação",
            "texto": f"{NOMES_LONGOS.get(est.get('mes_chuvoso'), '---')} passa de 200 mm em "
                     f"média ({_br(est['chuva_max'])} mm): canteiros altos, drenagem "
                     f"limpa e cobertura morta antes da temporada, para não perder "
                     f"solo e adubo no escoamento.",
        })

    if est.get("quente") and est.get("frio"):
        itens.append({
            "titulo": "Calor, frio e fitossanidade",
            "texto": f"{NOMES_LONGOS.get(est['quente'], '---')} tem a maior média "
                     f"({_br(est.get('quente_t'), 1)} °C) e "
                     f"{NOMES_LONGOS.get(est['frio'], '---')} a menor "
                     f"({_br(est.get('frio_t'), 1)} °C, com mínima média de "
                     f"{_br(min((m['tmin'] for m in pm if m['tmin'] is not None), default=None), 1)} °C). "
                     f"Antecipe o monitoramento de doenças fúngicas nos meses quentes e "
                     f"úmidos e proteja culturas sensíveis ao frio nos mais frios.",
        })
    return itens



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
    campos = {
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
    }
    # `uso` e `solsticios` dependem do resumo pronto: o texto cita os mesmos
    # números que os cards, e é gerado aqui para o site e a ficha LaTeX não
    # divergirem.
    dados = {**campos, **resumo(ag)}
    dados["solsticios"] = solsticios(dados["meses"], dados["chuva_ano"])
    dados["uso"] = uso_local(dados)
    return dados


def exportar(conn: sqlite3.Connection) -> dict:
    """Monta o pacote JSON completo que o dashboard consome.

    Args:
        conn: conexão aberta por `coletor.abrir`.

    Returns:
        Dict com `gerado` (data), `fonte`, `regioes`, `municipios` e `regiao`;
        cada município traz `slug`, `nome`, `regiao` e `estacoes`. Cada estação
        traz `slug` e `municipio`, que são a sua rota no painel
        (`#/registro-unesp`). Município sem estação aparece com a lista vazia —
        quem decide como mostrar isso é o front.

    Nota:
        A lista de municípios vem da tabela `municipio`, inclusive os sem
        estação: sumir com eles transformaria "não há dado" em "não existe".

        O `slug` da estação, e não o do município, é a rota: Registro e
        Pariquera-Açu têm duas estações cada, e a URL precisa dizer qual.

        `regioes` é a ordem dos grupos na tela (`Litoral Sul`, `Vale do
        Ribeira`, `Alto Vale e Cabeceiras`), e os municípios já saem ordenados
        por ela. `regiao` (singular) é outra coisa: o texto de uso geral que
        vale para todos — o nome é infeliz, mas renomeá-lo quebraria o front.
    """
    municipios = []
    for mun_id, mun, regiao in conn.execute(
            "SELECT id, nome, regiao FROM municipio ORDER BY nome"):
        estacoes = []
        for p in conn.execute(
                "SELECT id, nome, inicio_auto, primeiro_fato FROM ponto "
                "WHERE municipio_id = ? ORDER BY nome", (mun_id,)):
            estacao = _estacao(conn, p)
            if estacao:
                estacao["slug"] = slug(p["nome"])
                estacao["municipio"] = mun
                estacoes.append(estacao)
        municipios.append({"slug": slug(mun), "nome": mun, "regiao": regiao,
                           "estacoes": estacoes})
    # Ordem do CSV: agrupa na tela sem o front ter de saber a ordem das regiões.
    ordem = {r: i for i, r in enumerate(grupos())}
    municipios.sort(key=lambda m: (ordem.get(m["regiao"], len(ordem)), m["nome"]))
    return {"gerado": date.today().isoformat(), "fonte": "CIIAGRO",
            "regioes": list(grupos()), "regiao": {"uso": USO_GERAL},
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
