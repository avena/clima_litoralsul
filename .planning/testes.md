# Catálogo de testes

Todo teste tem docstring dizendo **o que ele garante**, não o que ele faz. Um
teste sem essa frase é um teste que ninguém sabe se pode apagar.

Rodar: `python3 -m unittest discover -s tests -v` (16 testes, ~0,5 s, sem rede).

Os fixtures em `tests/fixtures/` foram baixados do CIIAGRO em 2026-10-30. Eles
são a única verdade sobre o formato da página: se o site mudar o HTML, os testes
quebram, e é isso que se quer.

## T01 — Catálogo

| ID | Teste | O que garante |
|---|---|---|
| T01.1 | `test_dezessete_municipios` | o CSV tem exatamente os 17 da mesorregião; a promessa de cobertura não infla |
| T01.2 | `test_nome_exato` | nome de município com acento resolve (Cananéia, Itanhaém) |
| T01.3 | `test_sufixo_de_estacao` | `Registro Unesp` e `Pariquera-Açu 2` não viram município novo |
| T01.4 | `test_estacao_fora_dos_17` | estação vizinha (Apiaí, Juquitiba, Ribeira, Tapiraí, Itaóca) devolve `None` em vez de casar com o município errado |
| T01.5 | `test_calendario_traz_inicio_de_cada_estacao` | 23 estações, e `dd/mm/aaaa` → `AAAA-MM-DD` sem inverter dia e mês |
| T01.6 | `test_periodo_traz_o_codigo_numerico` | o código da estação sai da única página que o expõe |
| T01.7 | `test_marcadores_do_mapa_dao_coordenadas` | lat/lon saem do HTML do Leaflet, na ordem correta |
| T01.8 | `test_upsert_nao_duplica` | rodar `catalogo`/`coletar` duas vezes não duplica linha |

## T02 — Extrator

| ID | Teste | O que garante |
|---|---|---|
| T02.1 | `test_diario_tem_todas_as_estacoes_do_dia` | 18 estações no dia 29/10/2026 — a união dos três blocos (`data`, `data2`, `data3`) não perde estação que reporta só um deles |
| T02.2 | `test_diario_valores_conferem_com_a_pagina` | posição e escala de cada coluna: se `tmin` trocar com `tmax`, ou a umidade for lida como temperatura, quebra |
| T02.3 | `test_mensal_uma_linha_por_estacao` | o mesmo extrator serve diário e mensal (7 estações em 01/2001) |
| T02.4 | `test_umidade_zero_em_2001_nao_vira_medicao` | documenta que `0.0` de umidade é "sensor ausente" e que o extrator **não** inventa `NULL` |

## T03 — Coletor

| ID | Teste | O que garante |
|---|---|---|
| T03.1 | `test_meses_inclusivos` | `2000-11` a `2001-02` dá 4 meses; off-by-one aqui perde dezembro ou duplica janeiro |
| T03.2 | `test_dias_inclusivos` | a contagem de dias atravessa a virada de mês |
| T03.3 | `test_mes_e_dia_nao_convivem_no_mesmo_mes` | coletar diário depois de mensal apaga o total do mês; a soma dos dias continua igual ao total |
| T03.4 | `test_mensal_apaga_os_dias_do_mes` | a invariante vale nos dois sentidos |

## T05 — Relatório (previstos, ainda não escritos)

| ID | Teste | O que vai garantir |
|---|---|---|
| T05.1 | `test_n_anos_vem_do_banco` | o rótulo do rodapé é calculado, não cravado |
| T05.2 | `test_menos_de_30_anos_nunca_diz_normal` | `n_anos=2` não produz a palavra "normal climatológica" |
| T05.3 | `test_meses_descartados_aparecem_no_rodape` | descartar mês com < 20 dias não enviesa o total anual em silêncio |
| T05.4 | `test_lacuna_sai_como_travessao` | mês sem dado é `—`, não `0` |
| T05.5 | `test_municipio_sem_estacao_avisa` | Itanhaém, Mongaguá e Ilha Comprida não geram tabela vazia |
| T05.6 | `test_nome_de_arquivo_sem_acento` | `Pariquera-Açu` → `pariquera-acu.md` |

## O que não está testado, e por quê

- **Rede.** `_get` e `_post` não têm teste automatizado: exigiriam rede ou um
  servidor falso, e o valor seria provar que `urllib` funciona. A coleta real
  foi exercitada à mão contra o site (`catalogo`, `coletar`, `auditar`).
- **`auditar`.** É formatação sobre `SELECT`; os alertas são verificados rodando
  o comando contra o banco real e conferindo os casos conhecidos (Registro antes
  de 2005, Itariri em 1969). Tarefa 04, seção "Verificação".
- **UPSERT com `NULL` sobre valor existente.** Está no `COALESCE` e é testado
  indiretamente por T03.3; um teste dedicado seria barato e vale na tarefa 05.
