"""Fonte NASA POWER: reanálise diária e mensal para municípios sem estação de superfície.

API: https://power.larc.nasa.gov/api/temporal/daily/point
Grade: 0.5° × 0.5° (~55 km). Não substitui medição física em superfície.
"""
from __future__ import annotations

import calendar
import json
import time
import urllib.request
from typing import Iterator

FONTE = "nasa_power"
PAUSA = 0.25
UA = "clima-litoralsul/0.1 (coleta academica)"

# Coordenadas travadas na zona terrestre/agrícola dos municípios sem estação física
PONTOS = (
    {
        "id": "nasa:itanhaem",
        "nome": "Itanhaém (NASA POWER)",
        "municipio": "Itanhaém",
        "lat": -24.18,
        "lon": -46.79,
        "inicio_auto": "1981-01-01",
        "tipo": "reanalise",
    },
    {
        "id": "nasa:mongagua",
        "nome": "Mongaguá (NASA POWER)",
        "municipio": "Mongaguá",
        "lat": -24.09,
        "lon": -46.62,
        "inicio_auto": "1981-01-01",
        "tipo": "reanalise",
    },
    {
        "id": "nasa:peruibe",
        "nome": "Peruíbe (NASA POWER)",
        "municipio": "Peruíbe",
        "lat": -24.32,
        "lon": -47.00,
        "inicio_auto": "1981-01-01",
        "tipo": "reanalise",
    },
    {
        "id": "nasa:ilha-comprida",
        "nome": "Ilha Comprida (NASA POWER)",
        "municipio": "Ilha Comprida",
        "lat": -24.74,
        "lon": -47.54,
        "inicio_auto": "1981-01-01",
        "tipo": "reanalise",
    },
)


def pontos() -> list[dict]:
    """Catálogo de pontos virtuais de reanálise nos municípios sem estação CIIAGRO.

    Returns:
        Lista de pontos com id prefixado ('nasa:<slug>'), coordenadas e tipo.
    """
    return [dict(p) for p in PONTOS]


def _limpar(v: float | None) -> float | None:
    """Converte sentinela de dado ausente da NASA (-999.0) em None.

    Args:
        v: valor numérico retornado pela API.

    Returns:
        float válido ou None quando ausente.
    """
    return None if v is None or v <= -900 else v


def _parse_resposta(dados: dict, nome: str, diario: bool) -> Iterator[dict]:
    """Extrai fatos a partir do payload JSON da NASA POWER.

    Args:
        dados: dicionário decodificado da resposta JSON.
        nome: nome do ponto para vinculação com o catálogo.
        diario: True para diário, False para agregação mensal.

    Yields:
        Dicionários canônicos de fatos climáticos.
    """
    param = dados.get("properties", {}).get("parameter", {})
    tmin_d = param.get("T2M_MIN", {})
    tmed_d = param.get("T2M", {})
    tmax_d = param.get("T2M_MAX", {})
    ur_d = param.get("RH2M", {})
    pr_d = param.get("PRECTOTCORR", {})

    datas = sorted(tmed_d.keys())
    if diario:
        for d in datas:
            data_fmt = f"{d[:4]}-{d[4:6]}-{d[6:]}"
            yield {
                "nome": nome,
                "data": data_fmt,
                "tmin": _limpar(tmin_d.get(d)),
                "tmed": _limpar(tmed_d.get(d)),
                "tmax": _limpar(tmax_d.get(d)),
                "urmin": None,
                "urmed": _limpar(ur_d.get(d)),
                "urmax": None,
                "chuva": _limpar(pr_d.get(d)),
            }
        return

    # Agregação mensal
    por_mes: dict[str, list[tuple[float | None, float | None, float | None, float | None, float | None]]] = {}
    for d in datas:
        mes = f"{d[:4]}-{d[4:6]}"
        por_mes.setdefault(mes, []).append((
            _limpar(tmin_d.get(d)),
            _limpar(tmed_d.get(d)),
            _limpar(tmax_d.get(d)),
            _limpar(ur_d.get(d)),
            _limpar(pr_d.get(d)),
        ))

    for mes, valores in sorted(por_mes.items()):
        tmins = [v[0] for v in valores if v[0] is not None]
        tmeds = [v[1] for v in valores if v[1] is not None]
        tmaxs = [v[2] for v in valores if v[2] is not None]
        urs = [v[3] for v in valores if v[3] is not None]
        prs = [v[4] for v in valores if v[4] is not None]

        yield {
            "nome": nome,
            "data": mes,
            "tmin": round(sum(tmins) / len(tmins), 2) if tmins else None,
            "tmed": round(sum(tmeds) / len(tmeds), 2) if tmeds else None,
            "tmax": round(sum(tmaxs) / len(tmaxs), 2) if tmaxs else None,
            "urmin": None,
            "urmed": round(sum(urs) / len(urs), 1) if urs else None,
            "urmax": None,
            "chuva": round(sum(prs), 1) if prs else None,
        }


def _periodo_para_datas(desde: str, ate: str) -> tuple[str, str]:
    """Converte 'AAAA-MM' ou 'AAAA-MM-DD' para 'YYYYMMDD' aceito pela NASA.

    Args:
        desde: data inicial.
        ate: data final.

    Returns:
        Tupla (start_yyyymmdd, end_yyyymmdd).
    """
    if len(desde) == 7:
        start = desde.replace("-", "") + "01"
    else:
        start = desde.replace("-", "")

    if len(ate) == 7:
        ano, mes = int(ate[:4]), int(ate[5:7])
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        end = f"{ano}{mes:02d}{ultimo_dia:02d}"
    else:
        end = ate.replace("-", "")

    return start, end


def fatos(desde: str, ate: str, diario: bool = False) -> Iterator[dict]:
    """Obtém observações da NASA POWER para os pontos cadastrados.

    Args:
        desde: 'AAAA-MM' ou 'AAAA-MM-DD' inclusivo.
        ate: 'AAAA-MM' ou 'AAAA-MM-DD' inclusivo.
        diario: True para diário, False para agregado mensal.

    Yields:
        Dicionários canônicos de fatos climáticos.
    """
    start, end = _periodo_para_datas(desde, ate)
    base_url = "https://power.larc.nasa.gov/api/temporal/daily/point"

    for ponto in PONTOS:
        url = (
            f"{base_url}?parameters=T2M,T2M_MIN,T2M_MAX,RH2M,PRECTOTCORR"
            f"&community=AG&longitude={ponto['lon']}&latitude={ponto['lat']}"
            f"&start={start}&end={end}&format=JSON"
        )
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        # ponytail: divisão em fatias anuais dispensada; a API suporta 20+ anos numa só requisição.
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                dados = json.loads(r.read().decode("utf-8"))
            yield from _parse_resposta(dados, ponto["nome"], diario=diario)
        except OSError:
            pass
        time.sleep(PAUSA)
