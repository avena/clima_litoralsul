"""Fonte INMET: estações meteorológicas automáticas do Instituto Nacional de Meteorologia.

Natureza: API REST OFICIAL (JSON) + DADOS ABERTOS EM LOTE (ZIP/CSV).
Rede: Estações automáticas de superfície (EMA).

Onde se cadastrar para obter o token da API (Passo a Passo):
1. Acesse o portal oficial do INMET:
   https://portal.inmet.gov.br
2. Manual de uso e regras da API:
   https://portal.inmet.gov.br/manual/manual-de-uso-da-api-estacoes
3. Cadastro gratuito de usuário / desenvolvedor:
   No portal do INMET, acesse o menu superior ou o link de cadastro em:
   https://portal.inmet.gov.br (clique em 'Acesso a Dados' -> 'API de Dados Meteorológicos')
   ou diretamente no formulário de cadastro de desenvolvedor.
4. Após o cadastro e validação do e-mail, seu token pessoal será exibido no painel.
5. Para usar o token no coletor do projeto, defina no seu terminal:
   export INMET_TOKEN="seu_token_aqui"
   python3 coletor.py coletar --fonte inmet --desde 2023-01 --ate 2023-12

URLs de conferência no navegador e API:
- Catálogo de todas as estações automáticas (aberto, público sem necessidade de token):
  GET https://apitempo.inmet.gov.br/estacoes/T
  (Retorna JSON com as 669 estações do Brasil, incluindo A712-Iguape, A746-Barra do Turvo e A766-Registro)
- Dados históricos em lote por ano (portal público, sem token):
  https://portal.inmet.gov.br/dadoshistoricos (arquivos ZIP anuais com CSVs de todas as estações)
- API de medições horárias por estação e período:
  Sem token: GET https://apitempo.inmet.gov.br/estacao/{data_inicio}/{data_fim}/{codigo} (retorna 204 para períodos históricos)
  Com token pessoal: GET https://apitempo.inmet.gov.br/token/estacao/{data_inicio}/{data_fim}/{codigo}/{token}

Estações no território:
- A712: Iguape (lat -24.6716, lon -47.5458, início 2006-07-20)
- A746: Barra do Turvo (lat -24.9627, lon -48.4163, início 2008-07-03)
- A766: Registro (lat -24.5330, lon -47.8641, início 2017-02-08)
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Iterator

from municipios import resolver

FONTE = "inmet"
PAUSA = 0.25
UA = "clima-litoralsul/0.1 (coleta academica)"

# Estações de referência no território do observatório
ESTACOES_LOCAIS = (
    {
        "id": "inmet:A712",
        "codigo": "A712",
        "nome": "Iguape (INMET A712)",
        "municipio": "Iguape",
        "lat": -24.67166666,
        "lon": -47.54583333,
        "inicio_auto": "2006-07-20",
        "tipo": "estacao",
    },
    {
        "id": "inmet:A746",
        "codigo": "A746",
        "nome": "Barra do Turvo (INMET A746)",
        "municipio": "Barra do Turvo",
        "lat": -24.96277777,
        "lon": -48.41638888,
        "inicio_auto": "2008-07-03",
        "tipo": "estacao",
    },
    {
        "id": "inmet:A766",
        "codigo": "A766",
        "nome": "Registro (INMET A766)",
        "municipio": "Registro",
        "lat": -24.53305554,
        "lon": -47.86416666,
        "inicio_auto": "2008-07-03",
        "tipo": "estacao",
    },
)


def _converte_num(v: str | float | None) -> float | None:
    """Converte valor da API do INMET para float, tratando nulos e vírgulas.

    Args:
        v: valor em string ou número.

    Returns:
        float válido ou None.
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", ".")
    if not s or s == "-9999" or s == "-999":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def pontos() -> list[dict]:
    """Catálogo de estações automáticas do INMET no território.

    Tenta consultar a API pública /estacoes/T; se falhar, utiliza as estações
    canônicas mapeadas para a bacia do Ribeira e Litoral Sul.

    Returns:
        Lista de dicionários no formato canônico do catálogo.
    """
    # ponytail: catálogo estático local cobre as estações ativas; chamada remota atualiza coordenadas se houver rede.
    url = "https://apitempo.inmet.gov.br/estacoes/T"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            catalogo_remoto = json.loads(r.read().decode("utf-8"))
        codigos = {e["codigo"]: e for e in ESTACOES_LOCAIS}
        resultado = []
        for item in catalogo_remoto:
            cod = item.get("CD_ESTACAO")
            if cod in codigos:
                ref = codigos[cod]
                lat = _converte_num(item.get("VL_LATITUDE")) or ref["lat"]
                lon = _converte_num(item.get("VL_LONGITUDE")) or ref["lon"]
                inicio = item.get("DT_INICIO_OPERACAO")
                inicio_str = inicio[:10] if inicio else ref["inicio_auto"]
                resultado.append({
                    "id": f"inmet:{cod}",
                    "codigo": cod,
                    "nome": ref["nome"],
                    "municipio": ref["municipio"],
                    "lat": lat,
                    "lon": lon,
                    "inicio_auto": inicio_str,
                    "tipo": "estacao",
                })
        if resultado:
            return resultado
    except OSError:
        pass

    return [dict(e) for e in ESTACOES_LOCAIS]


def _parse_horario(linhas: list[dict], nome: str, diario: bool) -> Iterator[dict]:
    """Agrega registros horários do INMET em observações diárias ou mensais.

    Args:
        linhas: lista de registros horários da API.
        nome: nome da estação.
        diario: True para diário, False para mensal.

    Yields:
        Dicionários canônicos de fatos climáticos.
    """
    # Agrupa por dia
    por_dia: dict[str, list[dict]] = {}
    for r in linhas:
        dt = r.get("DT_MEDICAO")
        if not dt:
            continue
        por_dia.setdefault(dt, []).append(r)

    fatos_diarios = []
    for dt, registros in sorted(por_dia.items()):
        tmins = [_converte_num(r.get("TEM_MIN") or r.get("TEM_INS")) for r in registros]
        tmaxs = [_converte_num(r.get("TEM_MAX") or r.get("TEM_INS")) for r in registros]
        tmeds = [_converte_num(r.get("TEM_INS")) for r in registros]
        urs = [_converte_num(r.get("UMD_INS")) for r in registros]
        chuvas = [_converte_num(r.get("CHUVA")) for r in registros]

        tmins = [v for v in tmins if v is not None]
        tmaxs = [v for v in tmaxs if v is not None]
        tmeds = [v for v in tmeds if v is not None]
        urs = [v for v in urs if v is not None]
        chuvas = [v for v in chuvas if v is not None]

        fato_dia = {
            "nome": nome,
            "data": dt,
            "tmin": min(tmins) if tmins else None,
            "tmed": round(sum(tmeds) / len(tmeds), 2) if tmeds else None,
            "tmax": max(tmaxs) if tmaxs else None,
            "urmin": None,
            "urmed": round(sum(urs) / len(urs), 1) if urs else None,
            "urmax": None,
            "chuva": round(sum(chuvas), 1) if chuvas else (0.0 if registros else None),
        }
        fatos_diarios.append(fato_dia)

    if diario:
        yield from fatos_diarios
        return

    # Agrupa dias por mês
    por_mes: dict[str, list[dict]] = {}
    for fd in fatos_diarios:
        mes = fd["data"][:7]
        por_mes.setdefault(mes, []).append(fd)

    for mes, dias in sorted(por_mes.items()):
        tmins = [d["tmin"] for d in dias if d["tmin"] is not None]
        tmeds = [d["tmed"] for d in dias if d["tmed"] is not None]
        tmaxs = [d["tmax"] for d in dias if d["tmax"] is not None]
        urs = [d["urmed"] for d in dias if d["urmed"] is not None]
        chuvas = [d["chuva"] for d in dias if d["chuva"] is not None]

        yield {
            "nome": nome,
            "data": mes,
            "tmin": round(sum(tmins) / len(tmins), 2) if tmins else None,
            "tmed": round(sum(tmeds) / len(tmeds), 2) if tmeds else None,
            "tmax": round(sum(tmaxs) / len(tmaxs), 2) if tmaxs else None,
            "urmin": None,
            "urmed": round(sum(urs) / len(urs), 1) if urs else None,
            "urmax": None,
            "chuva": round(sum(chuvas), 1) if chuvas else None,
        }


def fatos(desde: str, ate: str, diario: bool = False) -> Iterator[dict]:
    """Obtém medições do INMET para as estações mapeadas.

    Args:
        desde: 'AAAA-MM' ou 'AAAA-MM-DD'.
        ate: 'AAAA-MM' ou 'AAAA-MM-DD'.
        diario: True para diário, False para mensal.

    Yields:
        Dicionários canônicos de fatos climáticos.
    """
    token = os.environ.get("INMET_TOKEN")
    dt_inicio = desde if len(desde) == 10 else f"{desde}-01"
    dt_fim = ate if len(ate) == 10 else f"{ate}-28"

    for est in pontos():
        cod = est.get("codigo") or est["id"].split(":")[-1]
        # ponytail: sem INMET_TOKEN a API pública devolve vazio (204); com token em os.environ['INMET_TOKEN'], consulta /token/estacao/...
        if token:
            url = f"https://apitempo.inmet.gov.br/token/estacao/{dt_inicio}/{dt_fim}/{cod}/{token}"
        else:
            url = f"https://apitempo.inmet.gov.br/estacao/{dt_inicio}/{dt_fim}/{cod}"

        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                conteudo = r.read().decode("utf-8")
                if not conteudo or "CHAVE INVÁLIDA" in conteudo:
                    continue
                linhas = json.loads(conteudo)
                if isinstance(linhas, list):
                    yield from _parse_horario(linhas, est["nome"], diario=diario)
        except (OSError, json.JSONDecodeError):
            pass
        time.sleep(PAUSA)
