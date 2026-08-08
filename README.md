# Lab01 — Características de Repositórios Populares no GitHub

Laboratório 01 da disciplina **Laboratório de Experimentação de Software** — Engenharia de Software, 6º período.

O objetivo é coletar e analisar dados dos **1.000 repositórios com maior número de estrelas no GitHub**, respondendo seis questões de pesquisa sobre maturidade, contribuição, frequência de releases, atualização, linguagem e qualidade de issues.

---

## Questões de Pesquisa

| # | Pergunta | Métrica |
|---|----------|---------|
| RQ01 | Sistemas populares são maduros/antigos? | Idade do repositório (data de criação até hoje) |
| RQ02 | Sistemas populares recebem muita contribuição externa? | Total de pull requests aceitas (merged) |
| RQ03 | Sistemas populares lançam releases com frequência? | Total de releases |
| RQ04 | Sistemas populares são atualizados com frequência? | Tempo desde a última atualização |
| RQ05 | Sistemas populares são escritos nas linguagens mais populares? | Linguagem primária de cada repositório |
| RQ06 | Sistemas populares possuem alto percentual de issues fechadas? | Razão entre issues fechadas e total de issues |
| RQ07 ⭐ | Sistemas em linguagens populares recebem mais contribuição, releases e atualizações? | RQ02, RQ03 e RQ04 segmentados por linguagem |

A referência adotada para "linguagens mais populares" é o **GitHub Octoverse** (fonte: octoverse.github.com), mantida ao longo de todo o laboratório.

---

## Arquitetura

A solução é uma pipeline de dados 100% Python dividida em quatro camadas:

```
GitHub GraphQL API
        │
        ▼
   [Coleta]  ←── client HTTP próprio com fila de rate limit
        │         armazena incrementalmente em SQLite
        ▼         (permite retomar coleta interrompida)
   [Banco]   ←── SQLite local (repos.db)
        │
        ├──▶ [Análise]    ←── Python + pandas + seaborn/matplotlib
        │         │              uma pessoa por grupo de RQs
        │         ▼
        │    charts/ (PNG para o relatório)
        │
        └──▶ [Dashboard]  ←── plotly → dashboard.html interativo
```

**Por que SQLite?** Dois motivos documentados na metodologia:
1. **Coleta incremental:** se o script falhar no meio dos 1.000 repos, retoma do último cursor salvo sem reprocessar.
2. **Análise com SQL:** aggregations por linguagem (RQ07) são mais expressivas com `GROUP BY` do que com manipulação manual de listas.

**Por que `urllib` e não `requests`?** O enunciado proíbe bibliotecas de terceiros que consultem a API do GitHub. O `urllib.request` é built-in e cobre exatamente o que precisamos, evitando qualquer ambiguidade na interpretação da regra.

**Rate limit:** a API GraphQL do GitHub limita a 5.000 pontos/hora. Cada resposta retorna `rateLimit.remaining` e `rateLimit.resetAt`. O client monitora esse campo e dorme até o reset quando o saldo está abaixo de um threshold definido — sem perda de dados e sem requisições desnecessárias. Também é comum receber um HTTP 403 de rate limit secundário (abuso por rajada de requisições) com header `Retry-After`; o client trata isso como erro retentável e espera o tempo indicado antes de tentar de novo.

**Rate limit e tamanho de página (por que o batch é 25, não 100):** testamos a `REPOSITORY_SEARCH_QUERY` diretamente contra a API em 2026-08-08 variando `perPage`. A partir de `perPage=40` o GitHub passou a responder **HTTP 502 (Bad Gateway)** de forma consistente; até `perPage=35` a resposta veio OK. A hipótese mais provável é o custo de computar `totalCount` de `pullRequests`, `releases` e `issues` (open/closed) para muitos repositórios na mesma resposta, o que aparentemente estoura algum timeout do lado do GitHub — não é um limite documentado oficialmente pela API, é um comportamento observado empiricamente, que pode variar com carga do servidor. Por segurança, o coletor usa **25 como tamanho de lote padrão** (`DEFAULT_BATCH_SIZE` em `collector.py`), com folga do limiar de 35-40 observado. Essa é uma decisão de metodologia que vale citar no relatório final: a coleta dos 100 (S01) e dos 1.000 (S02) repositórios não é feita em uma única requisição GraphQL, e sim em múltiplos lotes menores, com o estado (cursor + total já coletado) persistido em SQLite entre lotes — o que também é o mecanismo que permite retomar uma coleta interrompida sem reprocessar repositórios já salvos.

---

## Estrutura de Sprints

| Sprint | Entrega | Pontos |
|--------|---------|--------|
| **S01** | Query GraphQL + coleta de 100 repos + GitHub Projects configurado | 4 |
| **S02** | Paginação para 1.000 repos + CSV + hipóteses informais + snapshot Kanban | 4 |
| **S03** | Análise estatística + visualizações + dashboard interativo | 4 |
| **Relatório** | Documento final com resultados, discussão e configuração do processo | 3 |

---

## Como Executar

> Instruções completas serão adicionadas ao longo das sprints.

```bash
cd app

# Configuração do token (uma vez)
cp .env.example .env
# edite .env e defina GITHUB_TOKEN=<token com escopo public_repo>

# Dependências de desenvolvimento (runtime não tem dependências externas)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# Testes automatizados
pytest

# Coleta (salva em data/repos.db, retomável se interrompida)
# --per-page controla o tamanho de cada requisição à API (padrão 25 — ver
# "Rate limit e tamanho de página" acima sobre por que não usar 100 direto).
# --total, se informado, encadeia lotes de --per-page até atingir a meta.
python -m src.collector                        # 1 lote de 25 repos
python -m src.collector --per-page 25 --total 100   # S01: 100 repos (4 lotes de 25)
python -m src.collector --per-page 25 --total 1000  # S02: 1.000 repos (paginação completa)

# Export para CSV
python src/export.py

# Análise por RQ
python analysis/rq01_02.py
python analysis/rq03_04.py
python analysis/rq05_06_07.py

# Dashboard interativo
python dashboard/generate.py
# → abre output/dashboard.html

# Export snapshot do Kanban (rodar ao final de cada sprint)
python kanban/export_kanban.py
```

---

## Equipe

| Integrante | RQs | Responsabilidade principal |
|------------|-----|---------------------------|
| Pessoa A | RQ01, RQ02 | Client GraphQL + análise de idade e PRs |
| Pessoa B | RQ03, RQ04 | Paginação + análise de releases e atualização |
| Pessoa C | RQ05, RQ06, RQ07 | Linguagens + issues + bônus + export Kanban |

---

## Links

- **Repositório:** https://github.com/Laboratorio-Medicao/Lab01
- **GitHub Projects (Kanban):** `<preencher após criação>`
- **Relatório Final:** `<preencher após entrega>`
