"""Os 25 municípios do Litoral Sul + Vale do Ribeira e o casamento de nomes.

Três recortes, na ordem em que o painel os mostra: **Litoral Sul** (faixa
costeira e estuário), **Vale do Ribeira** (baixo/médio curso) e **Alto Vale e
Cabeceiras**. A ordem do CSV é a ordem dos grupos na tela.

O CIIAGRO nomeia a estação pelo município, mas às vezes acrescenta sufixo
("Registro Unesp", "Pariquera-Açu 2"). `resolver` normaliza e tenta o nome
exato, depois tira o sufixo numérico/institucional.
"""
from __future__ import annotations

import csv
import unicodedata
from functools import lru_cache
from pathlib import Path

CSV = Path(__file__).with_name("municipios.csv")


def normalizar(nome: str) -> str:
    """"Pariquera-Açu" -> "pariquera acu" (sem acento, sem hífen, minúsculo)."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", nome) if unicodedata.category(c) != "Mn"
    )
    return " ".join(sem_acento.replace("-", " ").lower().split())


@lru_cache(maxsize=1)
def todos() -> tuple[dict[str, str], ...]:
    """[(nome, região), ...] na ordem do CSV."""
    with CSV.open(encoding="utf-8") as f:
        return tuple(
            {"nome": r["municipio"], "regiao": r["regiao"]}
            for r in csv.DictReader(f)
        )


def regioes() -> tuple[str, ...]:
    """Nomes das regiões sem repetir, na ordem do CSV — a ordem dos grupos."""
    return tuple(dict.fromkeys(m["regiao"] for m in todos()))


def resolver(nome_estacao: str) -> str | None:
    """Nome da estação -> município canônico, ou None se estiver fora dos 17."""
    alvo = normalizar(nome_estacao)
    candidatos = {normalizar(m["nome"]): m["nome"] for m in todos()}
    if alvo in candidatos:
        return candidatos[alvo]
    # "Registro Unesp" -> "registro"; "Pariquera-Açu 2" -> "pariquera acu"
    palavras = alvo.split()
    for n in range(len(palavras) - 1, 0, -1):
        if (achado := candidatos.get(" ".join(palavras[:n]))):
            return achado
    return None
