# clima_litoralsul

Série climática dos **17 municípios da mesorregião Litoral Sul Paulista**
(microrregiões de Itanhaém e Registro), a partir das estações do
[CIIAGRO](http://www.ciiagro.org.br).

Python 3.12, **sem dependências**: `urllib`, `sqlite3`, `re`, `csv`, `unittest`.

## Começar

```bash
python3 coletor.py catalogo
python3 coletor.py coletar --desde 2000-01 --ate 2026-10
python3 coletor.py auditar
```

`auditar` imprime, por estação: município, início declarado pelo site, primeiro
dado efetivamente recebido, número de linhas e alertas (`dado antes do início`,
`umidade toda 0`, `chuva toda 0`, `início suspeito`).

## O que a fonte entrega

| Endpoint | Conteúdo |
|---|---|
| `diario/cdiaria` (POST `data=dd/mm/aaaa`) | **todas** as estações num dia: T e UR mín/média/máx, chuva |
| `mensal/cmensal` (POST `parametro=mm/aaaa`) | agregados mensais, todas as estações |
| `horario.php?codigo=N` | janela rolante de 7 dias — **sem histórico** |

Não há API. Os números vêm em `data.addRows([['Registro',17.1,21.5,25.9],…])`
dentro do HTML; o extrator é regex, testado contra HTML real em `tests/fixtures/`.

## Cobertura medida (do banco, não do calendário do site)

4.914 linhas mensais, `1990-01` a `2026-10`, 23 estações.

- **≥30 anos de dado**: Pariquera-Açu (34,1), Registro (31,6) — as duas só
  alcançam isso porque o CIIAGRO serve série anterior ao início que ele mesmo
  declara (`/calendario` diz 2004 e 2005).
- **20-29 anos**: Miracatu (26,9), Cananéia (26,8), Sete Barras (26,7),
  Jacupiranga (25,8).
- **13-19 anos**: Iguape, Ribeira, Tapiraí, Juquitiba, Itariri, Eldorado,
  Registro Unesp, Apiaí, Cajati, Iporanga, Itaóca, Juquiá.
- **6-8 anos**: Pedro de Toledo, Pariquera-Açu 2, Barra do Chapéu, Barra do
  Turvo, Itapirapuã Paulista.
- **Sem estação CIIAGRO**: Itanhaém, Mongaguá, Ilha Comprida. Peruíbe só na rede
  principal (`/ema/index.php?id=56`), fora desta versão.

**13 dos 17 municípios** têm estação — 15 é o número de estações, porque Registro
e Pariquera-Açu têm duas cada. As 8 estações de municípios vizinhos ficam no
banco com `municipio_id` nulo, como referência.

## Duas armadilhas que mudam a interpretação

1. **O site serve dados antes de a estação existir.** Registro tem 380 mm em
   `01/1995`, mas começou em 2005. Pode ser registro histórico convencional ou
   reconstrução — só o cruzamento com o INMET decide. Até lá, série
   pré-automação é `suspeita` e o `auditar` mostra o caso em cada estação.
2. **`0` significa "sem medição", não "zero".** Em `01/2001` todas as estações
   reportam `0.00 %` de umidade. Some com "vazio" que a página devolve sem motivo
   aparente e você tem uma seca que nunca aconteceu.

## Banco

`dados/clima.sqlite`, três tabelas: `municipio`, `ponto`, `fato`.

- `ponto.id` é o código da estação no CIIAGRO (ex.: `63` = Registro).
- `fato.data` em `AAAA-MM-DD` (dia) ou `AAAA-MM` (mês) — `length(data)` é a granularidade.
- Um mês guarda **ou** o total mensal **ou** os dias, nunca os dois.
- `INSERT … ON CONFLICT DO UPDATE` com `COALESCE`: recoletar não duplica nem apaga.

## Limitações

- Sem INMET ou NASA POWER: 3 municípios sem estação e séries curtas continuam curtas.
- Sem insolação (estação automática não mede) e sem ET0 — Hargreaves–Samani vem
  no ticket de relatório.
- Sem tabela climática publicável: para a Wikipédia seria pesquisa inédita, porque
  as normais 1981-2010 são do INMET.
- Coleta respeita o servidor: 0,25 s entre requisições, 3 tentativas, User-Agent próprio.

Dados pertencem ao CIIAGRO / Governo do Estado de São Paulo — verifique os termos
de uso antes de redistribuir.
