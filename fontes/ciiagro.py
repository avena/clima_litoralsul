"""Fonte CIIAGRO: catálogo de estações e série diária/mensal.

Endpoints verificados em 2026-10-30 (detalhes e armadilhas em PLANO.md):

    POST /cbhrb/estacoes/diario/cdiaria   data=dd/mm/aaaa   todas as estações
    POST /cbhrb/estacoes/mensal/cmensal   parametro=mm/aaaa
    GET  /cbhrb/estacoes/calendario                         nome + início
    GET  /cbhrb/estacoes/diario/periodo                     nome -> código
    GET  /cbhrb/estacoes/                                   lat/lon nos marcadores

Não existe API: os números vêm embutidos no HTML como
`data.addRows([['Registro',17.1,21.5,25.9], ...])`. Regex, sem parser de HTML.

`horario.php?codigo=N` também responde, mas devolve janela rolante de 7 dias e
ignora qualquer parâmetro de data — não serve para série histórica.
"""
from __future__ import annotations

import re
import time
import urllib.parse
import urllib.request

BASE = "http://www.ciiagro.org.br"
PAUSA = 0.25  # segundos entre requisições
TENTATIVAS = 3
UA = "clima-litoralsul/0.1 (coleta academica)"

_BLOCO = re.compile(r"(\w+)\.addRows\(\[(.*?)\]\s*\);", re.S)
_TUPLA = re.compile(r"\['([^']*)'\s*((?:,[^,\]]*)*)\]")
_MARKER = re.compile(r'L\.marker\(\[(-?[\d.]+),(-?[\d.]+)\],\s*\{title:\s*"([^"]+)"')
_CHECKBOX = re.compile(r'name="estacao_id\[\]"\s*value="(\d+)"[^>]*/>([^<]+)<')


# ---------------------------------------------------------------- rede

def _get(url: str, dados: bytes | None = None) -> str:
    """GET/POST com 3 tentativas. O site responde 200 até para erro, então
    "sem dados" é sinalizado pela ausência dos blocos, não pelo status."""
    pedido = urllib.request.Request(url, data=dados, headers={"User-Agent": UA})
    for tentativa in range(TENTATIVAS):
        try:
            with urllib.request.urlopen(pedido, timeout=60) as r:
                return r.read().decode("utf-8-sig", "replace")
        except OSError:
            if tentativa == TENTATIVAS - 1:
                raise
            time.sleep(2 ** tentativa)
    raise AssertionError("inalcançável")


def _post(caminho: str, dados: dict[str, str]) -> str:
    """POST de formulário no CIIAGRO e devolve o HTML decodificado.

    Args:
        caminho: path relativo, ex.: `/cbhrb/estacoes/diario/cdiaria`.
        dados: campos do formulário, já como `str`.

    Returns:
        Corpo da resposta. Status 200 não garante dado: período inválido
        devolve página vazia, e é `linhas()` que detecta a ausência.
    """
    return _get(BASE + caminho, urllib.parse.urlencode(dados).encode())


# ---------------------------------------------------------------- parsing

def blocos(html: str) -> dict[str, list[tuple[str, list[float]]]]:
    """{variável: [(estação, [valores]), ...]} para cada `addRows` da página."""
    saida: dict[str, list[tuple[str, list[float]]]] = {}
    for m in _BLOCO.finditer(html):
        linhas = []
        for nome, valores in _TUPLA.findall(m.group(2)):
            numeros = [float(v) for v in valores.split(",") if v.strip()]
            linhas.append((nome, numeros))
        saida[m.group(1)] = linhas
    return saida


def _v(valores: list[float], i: int) -> float | None:
    """Valor na posição `i`, ou `None` se a linha veio mais curta que o esperado.

    Args:
        valores: números de uma linha do `addRows`.
        i: índice desejado.

    Returns:
        `valores[i]` ou `None`. Existe porque algumas estações devolvem menos
        colunas que as outras no mesmo bloco.
    """
    return valores[i] if len(valores) > i else None


def linhas(html: str) -> list[dict]:
    """Uma linha por estação, com as 8 colunas canônicas.

    Estação que aparece só em um dos blocos entra mesmo assim (chuva sem
    temperatura é dado válido). Valor ausente é None, nunca 0.
    """
    b = blocos(html)
    chuva = {n: _v(v, 0) for n, v in b.get("data2", [])}
    umid = dict(b.get("data3", []))
    temp = dict(b.get("data", []))
    nomes = list(dict.fromkeys([
        *temp,
        *(n for n, _ in b.get("data3", [])),
        *(n for n, _ in b.get("data2", [])),
    ]))
    saida = []
    for nome in nomes:
        t, u = temp.get(nome, []), umid.get(nome, [])
        saida.append({
            "nome": nome,
            "tmin": _v(t, 0), "tmed": _v(t, 1), "tmax": _v(t, 2),
            "urmin": _v(u, 0), "urmed": _v(u, 1), "urmax": _v(u, 2),
            "chuva": chuva.get(nome),
        })
    return saida


def inicios(html: str) -> dict[str, str]:
    """`/calendario` -> {estação: AAAAMMDD}."""
    saida = {}
    for nome, data in re.findall(r"<td>([^<]+)</td>\s*<td>\s*(\d{2}/\d{2}/\d{4})", html):
        d, m, a = data.split("/")
        saida[nome.strip()] = f"{a}-{m}-{d}"
    return saida


def codigos(html: str) -> dict[str, str]:
    """`/diario/periodo` -> {estação: código}."""
    return {nome.strip(): cod for cod, nome in _CHECKBOX.findall(html)}


def coordenadas(html: str) -> dict[str, tuple[float, float]]:
    """`/cbhrb/estacoes/` -> {estação: (lat, lon)} a partir dos marcadores Leaflet."""
    return {nome: (float(lat), float(lon)) for lat, lon, nome in _MARKER.findall(html)}


# ---------------------------------------------------------------- interface da fonte

FONTE = "ciiagro"


def pontos() -> list[dict]:
    """Catálogo completo da fonte (23 estações), com município quando for dos 25."""
    from municipios import resolver

    base = inicios(_get(BASE + "/cbhrb/estacoes/calendario"))
    ids = codigos(_get(BASE + "/cbhrb/estacoes/diario/periodo"))
    geo = coordenadas(_get(BASE + "/cbhrb/estacoes/"))
    return [
        {
            "id": f"ciiagro:{codigo}",
            "nome": nome,
            "municipio": resolver(nome),
            "lat": geo.get(nome, (None, None))[0],
            "lon": geo.get(nome, (None, None))[1],
            "inicio_auto": base.get(nome),
            "tipo": "estacao",
        }
        for nome, codigo in ids.items()
    ]


def fatos(desde: str, ate: str, diario: bool = False):
    """Gera um dict por estação e por período (mensal, ou diário com diario=True).

    `desde`/`ate` são 'AAAA-MM' (mensal) ou 'AAAA-MM-DD' (diário), inclusivos.
    O nome devolvido é o da fonte; o banco resolve para `ponto.id`.
    """
    for chave in _chaves(desde, ate, diario):
        if diario:
            d, m, a = chave.split("-")[::-1]
            html = _post("/cbhrb/estacoes/diario/cdiaria", {"data": f"{d}/{m}/{a}"})
        else:
            a, m = chave.split("-")
            html = _post("/cbhrb/estacoes/mensal/cmensal", {"parametro": f"{m}/{a}"})
        for linha in linhas(html):
            yield {**linha, "data": chave}
        time.sleep(PAUSA)


def _chaves(desde: str, ate: str, diario: bool) -> list[str]:
    """Lista de 'AAAA-MM' ou 'AAAA-MM-DD' entre os dois extremos."""
    from datetime import date, timedelta

    if diario:
        a, b = (date.fromisoformat(x) for x in (desde, ate))
        return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]
    a = [int(x) for x in desde.split("-")]
    b = [int(x) for x in ate.split("-")]
    meses = (b[0] - a[0]) * 12 + b[1] - a[1]
    return [f"{a[0] + (a[1] - 1 + i) // 12:04d}-{(a[1] - 1 + i) % 12 + 1:02d}"
            for i in range(meses + 1)]
