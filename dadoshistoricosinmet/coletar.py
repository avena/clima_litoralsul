"""Coletor dos arquivos anuais de Dados Históricos do INMET.

Baixa os pacotes `{ano}.zip` de portal.inmet.gov.br/dadoshistoricos para
`zips/`, com retomada por arquivo e validação de integridade. Os arquivos são
grandes (~100 MB/ano) e o servidor derruba conexões longas de vez em quando,
por isso o download é retomável via Range e verificado antes de virar definitivo.

Uso:
    python3 dadoshistoricosinmet/coletar.py                # 2000..2026
    python3 dadoshistoricosinmet/coletar.py --anos 2010,2011
    python3 dadoshistoricosinmet/coletar.py --paralelo 2
"""
from __future__ import annotations

import argparse
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

URL_BASE = "https://portal.inmet.gov.br/uploads/dadoshistoricos/{ano}.zip"
DIR_BASE = Path(__file__).resolve().parent
DIR_ZIPS = DIR_BASE / "zips"

# Sem UA de navegador o portal responde 403 para alguns clientes.
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

PRIMEIRO_ANO = 2000
ULTIMO_ANO = 2026

# Tamanho mínimo plausível: o menor arquivo da série (2000) tem ~527 KB.
TAMANHO_MINIMO = 100_000


def anos_padrao() -> list[int]:
    """Retorna a série completa de anos com dados publicados pelo INMET."""
    return list(range(PRIMEIRO_ANO, ULTIMO_ANO + 1))


def zip_valido(caminho: Path) -> bool:
    """Confere se o arquivo é um ZIP íntegro e grande o bastante para valer.

    Args:
        caminho: Arquivo a verificar.

    Returns:
        True se o arquivo abre como ZIP e tem tamanho plausível.
    """
    if not caminho.exists() or caminho.stat().st_size < TAMANHO_MINIMO:
        return False
    return zipfile.is_zipfile(caminho)


def baixar_ano(ano: int, destino_dir: Path = DIR_ZIPS, tentativas: int = 4) -> tuple[Path, bool]:
    """Baixa o pacote anual, retomando download parcial quando existir.

    Args:
        ano: Ano com 4 dígitos.
        destino_dir: Pasta de cache dos `.zip`.
        tentativas: Quantas vezes tentar antes de desistir.

    Returns:
        Tupla (caminho_do_zip, baixou_agora). `baixou_agora` é False quando o
        arquivo já estava em cache íntegro.
    """
    destino_dir.mkdir(parents=True, exist_ok=True)
    final = destino_dir / f"{ano}.zip"

    if zip_valido(final):
        return final, False

    # Arquivo corrompido de execução anterior: descarta para não mascarar erro.
    if final.exists():
        final.unlink()

    parcial = destino_dir / f"{ano}.zip.part"
    url = URL_BASE.format(ano=ano)
    ultimo_erro: Exception | None = None

    for tentativa in range(1, tentativas + 1):
        inicio = parcial.stat().st_size if parcial.exists() else 0
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        if inicio:
            req.add_header("Range", f"bytes={inicio}-")

        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                # 206 = retomou do ponto certo. 200 = servidor ignorou o Range.
                if inicio and resp.status != 206:
                    inicio = 0
                modo = "ab" if inicio else "wb"
                with open(parcial, modo) as f:
                    while True:
                        bloco = resp.read(1024 * 256)
                        if not bloco:
                            break
                        f.write(bloco)
        except (urllib.error.URLError, TimeoutError, OSError) as erro:
            ultimo_erro = erro
            espera = min(2 * tentativa, 10)
            print(f"  [{ano}] tentativa {tentativa} falhou ({erro}); retomando em {espera}s")
            time.sleep(espera)
            continue

        if zip_valido(parcial):
            parcial.replace(final)
            return final, True

        # ZIP truncado: o Range seguinte recomeça do zero.
        parcial.unlink(missing_ok=True)
        print(f"  [{ano}] arquivo inválido após download; reiniciando")

    raise RuntimeError(f"Falha ao baixar {ano}.zip após {tentativas} tentativas") from ultimo_erro


def coletar(anos: list[int], destino_dir: Path = DIR_ZIPS, paralelo: int = 3) -> dict[int, Path]:
    """Baixa uma lista de anos, em paralelo controlado.

    Args:
        anos: Anos a garantir em cache.
        destino_dir: Pasta de destino.
        paralelo: Downloads simultâneos.

    Returns:
        Mapa ano -> caminho do `.zip`.
    """
    destino_dir.mkdir(parents=True, exist_ok=True)
    baixados: dict[int, Path] = {}
    falhas: list[int] = []

    with ThreadPoolExecutor(max_workers=max(1, paralelo)) as pool:
        futuros = {pool.submit(baixar_ano, a, destino_dir): a for a in anos}
        for futuro in as_completed(futuros):
            ano = futuros[futuro]
            try:
                caminho, novo = futuro.result()
            except RuntimeError as erro:
                print(f"  [{ano}] ERRO: {erro}")
                falhas.append(ano)
                continue
            baixados[ano] = caminho
            estado = "baixado" if novo else "em cache"
            mb = caminho.stat().st_size / (1024 * 1024)
            print(f"  [{ano}] {estado} ({mb:.1f} MB)")

    if falhas:
        print(f"\nFalharam {len(falhas)} anos: {sorted(falhas)}")
    return baixados


def main() -> None:
    parser = argparse.ArgumentParser(description="Baixa os ZIPs anuais de dados históricos do INMET.")
    parser.add_argument("--anos", type=str, help="Anos separados por vírgula (ex.: 2010,2011). Padrão: 2000..2026")
    parser.add_argument("--desde", type=int, default=PRIMEIRO_ANO, help="Primeiro ano do intervalo")
    parser.add_argument("--ate", type=int, default=ULTIMO_ANO, help="Último ano do intervalo")
    parser.add_argument("--paralelo", type=int, default=3, help="Downloads simultâneos")
    args = parser.parse_args()

    if args.anos:
        anos = sorted(int(a.strip()) for a in args.anos.split(",") if a.strip())
    else:
        anos = list(range(args.desde, args.ate + 1))

    print(f"Baixando {len(anos)} arquivos anuais para {DIR_ZIPS}")
    inicio = time.time()
    baixados = coletar(anos, paralelo=args.paralelo)

    total_mb = sum(p.stat().st_size for p in baixados.values()) / (1024 * 1024)
    print(
        f"\n{len(baixados)}/{len(anos)} arquivos em {time.time() - inicio:.0f}s "
        f"({total_mb:.0f} MB em cache)."
    )


if __name__ == "__main__":
    main()
