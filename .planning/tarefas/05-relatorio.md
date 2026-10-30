# Tarefa 05 — Relatório por município

**Status:** pendente
**Depende de:** 04
**Arquivos previstos:** `relatorio.py` (novo)
**Testes previstos:** T05.1 a T05.6 em `.planning/testes.md`

## Objetivo

Gerar, por comando, `relatorios/<municipio>.md` e `.html` com chuva, temperatura
e a série real de cada município — declarando fonte, período e quantidade de
anos em cada linha.

## Formato de saída

Comando, não servidor. DreamHost Shared roda só CGI, então a "web" é HTML
estático gerado aqui e copiado depois.

```
python3 relatorio.py                 # todos os 15 municípios com estação
python3 relatorio.py --municipio Registro
```

## Subtarefas

### 05.1 — Série por município

`SELECT` em `fato JOIN ponto WHERE ponto.municipio_id = ?`, ordenado por `data`.

Mês e dia convivem no banco (tarefa 03 garante que nunca no mesmo mês), então a
consulta precisa normalizar: `GROUP BY substr(data,1,7)` para série mensal e
`WHERE length(data)=10` para série diária.

### 05.2 — Cobertura declarada antes de qualquer número

Antes da primeira tabela, imprimir:

```
Registro — estação 63, 2005-10 a 2026-10 (21 anos, 252 meses)
1 mês descartado por cobertura < 20 dias
```

Sem isso o leitor não sabe se está vendo 21 anos ou 3 meses com lacunas.

### 05.3 — Métricas mensais

Por mês do ano (12 colunas): chuva média, dias com chuva ≥ 1 mm, T máx/média/mín
média, UR média.

Mês com menos de 20 dias de dado é **descartado do total anual e contado no
rodapé**. Descartar em silêncio enviesa o total anual para baixo — foi
exatamente o defeito do material anterior.

### 05.4 — Rótulos derivados de `n_anos`, nunca cravados

| `n_anos` | Rótulo |
|---|---|
| ≥ 30 | "normal climatológica" |
| < 30 | "médias do período AAAA–AAAA (n anos)" |
| extremos, ≥ 30 | "recorde" |
| extremos, < 30 | "extremo observado no período" |

E "Temperatura média simples", nunca "compensada": o CIIAGRO não entrega as
leituras fixas de 9 h e 21 h que a média compensada do INMET exige.

### 05.5 — Lacunas explícitas

Mês sem dado aparece como `—`, não como `0`. Série com buraco é diferente de
série seca.

### 05.6 — Renderização Markdown e HTML

Um dicionário de resultado, dois renderizadores. Sem Jinja, sem template engine:
duas funções de `str.join`. O HTML é tabela simples com CSS embutido.

### 05.7 — Nota de proveniência

Rodapé obrigatório: fonte, estação, código, período, `n_anos`, e o aviso de
série pré-automação quando `primeiro_fato < inicio_auto`.

## Critério de aceite

- [ ] Um arquivo por município, com nome sem acento (`pariquera-acu.md`)
- [ ] Nenhum `0` onde a resposta correta é "sem dado"
- [ ] Os 3 municípios sem estação aparecem com aviso, não com tabela vazia
- [ ] Rodapé sempre presente, com `n_anos` calculado do banco
- [ ] `n_anos < 30` nunca produz a palavra "normal climatológica"

## Fora de escopo

- **Tabela para a Wikipédia:** seria pesquisa inédita. As normais 1981-2010 são
  do INMET, não do CIIAGRO; publicar "média 2024-2026" como clima não se
  sustenta em fonte verificável.
- **ET0 / balanço hídrico:** Hargreaves–Samani precisa de latitude e produz
  estimativa, não medição. Se entrar, entra numa tarefa 06 com o rótulo
  "estimativa" no nome da coluna.
- **INMET e NASA POWER:** tarefa 07, só depois de a série do CIIAGRO estar
  auditada.
