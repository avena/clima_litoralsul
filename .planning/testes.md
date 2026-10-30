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
| T03.5 | `test_primeiro_fato_recalcula_para_tras` | `primeiro_fato` é o menor `data` do banco, mesmo coletado fora de ordem — regressão de `COALESCE` que congelava a data |

## T05 — Relatório

| ID | Teste | O que garante |
|---|---|---|
| T05.1 | `test_nome_de_arquivo_sem_acento` | `Pariquera-Açu` → `pariquera-acu`; link estático funciona sem reescrita de URL |
| T05.2 | `test_menos_de_30_anos_nunca_diz_normal` | 2 anos de dado não produzem "normal climatológica" |
| T05.3 | `test_serie_pre_2000_nao_vira_normal_mesmo_com_30_anos` | 34 anos com origem desconhecida continuam "médias do período … não validada" |
| T05.4 | `test_valor_impossivel_sai_da_media_e_e_contado` | `tmed = 873,35` não entra na média e o rodapé conta o descarte |
| T05.5 | `test_municipio_sem_estacao_entra_com_lista_vazia` | município sem estação aparece no JSON com `estacoes: []`, em vez de sumir da lista |
| T05.6 | `test_mes_sem_dado_vira_null` | buraco de série é `null` no JSON, não `0` |
| T05.7 | `test_sazonal_soma_a_chuva_anual` | as quatro estações fecham exatamente com a chuva anual do card; o percentual não distribui água inexistente |
| T05.9 | `test_cada_estacao_tem_rota_propria_no_json` | duas estações do mesmo município saem com slugs distintos — `#/registro` e `#/registro-unesp` não podem abrir a mesma tela |
| T05.8 | `test_json_exportado_e_serializavel` | o `dados.json` sai do disco íntegro, com 12 linhas e chuva anual — sem isso o SPA abriria vazio sem erro |

## T06 — Painel (React)

| ID | Teste | O que garante |
|---|---|---|
| T06.1 | `site/check.jsx` (`npm --prefix site run check`) | o SPA renderiza com o `dados.json` real fora do navegador: climatograma com envelope, KPI em pt-BR, aviso de município sem estação e nenhum `NaN`/`undefined` no HTML |
| T06.2 | `site/check.jsx` | a lista de estações mostra `(29 anos)` ao lado do nome — quem escolhe a estação vê de imediato quantos anos fechados existem ali, sem abrir a ficha |
| T06.3 | `site/check.jsx` | o climatograma linka `fichas/<slug>.pdf` da **estação** aberta: `#/registro-unesp` não pode apontar para o PDF de `registro` |

## T07 — Sazonal, solstícios e uso no planejamento

O texto agronômico saiu do JavaScript e do LaTeX e passou a nascer em
`relatorio.py`: site e ficha em PDF mostram a mesma frase porque a frase é uma
só. Foi escrito à mão por cidade uma vez, e duas frases saíram contra os números
(mínima de junho em Barra do Turvo; "mais de 40% da chuva" em Jacupiranga, que
dá 39,8%).

| ID | Teste | O que garante |
|---|---|---|
| T07.1 | `test_sazonal_traz_total_media_maximo_e_minimo` | cada estação do ano traz total, %, média/mês e os meses maior e menor — site e ficha não calculam isso cada um do seu jeito |
| T07.2 | `test_solsticios_nao_somam_duas_vezes_nem_perdem_dezembro` | os acumulados "antes do solstício de inverno" (jan–mai) e "de verão" (jun–nov) mais dezembro fecham com a chuva anual |
| T07.3 | `test_uso_local_cita_numero_e_nao_deixa_valor_ausente` | o texto de planejamento sai com título, texto e sem `None`/`NaN` — é o que vai para a ATER |
| T07.4 | `test_inicio_das_chuvas_e_o_mes_depois_do_seco_nao_janeiro` | a volta das chuvas é o mês seguinte ao mais seco; pegar o primeiro mês úmido do ano civil mandava aplicar calcário em janeiro |
| T07.5 | `test_regiao_leva_orientacao_geral_no_json` | a orientação que vale para todo município (`regiao.uso`) vai no topo do `dados.json` |
| T07.6 | `site/check.jsx` | o card de uso, a média sazonal vinda do JSON e os acumulados de solstício aparecem no HTML renderizado, uma vez só; o bloco regional **não** está dentro de `<details>` — conselho escondido atrás de um clique não é lido |

## O que não está testado, e por quê

- **Rede.** `_get` e `_post` não têm teste automatizado: exigiriam rede ou um
  servidor falso, e o valor seria provar que `urllib` funciona. A coleta real
  foi exercitada à mão contra o site (`catalogo`, `coletar`, `auditar`).
- **`auditar`.** É formatação sobre `SELECT`; os alertas são verificados rodando
  o comando contra o banco real e conferindo os casos conhecidos (Registro antes
  de 2005, Itariri em 1969). Tarefa 04, seção "Verificação".
- **Aparência do painel.** O `check.jsx` garante que o HTML é gerado com os
  números certos; se ficou bonito, só abrindo `./start.sh`. Comparar markup byte
  a byte quebraria a cada ajuste de classe Tailwind sem proteger dado.
