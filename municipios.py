"""Os 17 municípios da mesorregião Litoral Sul Paulista e o casamento de nomes.

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
    """[(nome, microrregião), ...] na ordem do CSV."""
    with CSV.open(encoding="utf-8") as f:
        return tuple(
            {"nome": r["municipio"], "microrregiao": r["microrregiao"]}
            for r in csv.DictReader(f)
        )


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
