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

**Rate limit:** a API GraphQL do GitHub limita a 5.000 pontos/hora. Cada resposta retorna `rateLimit.remaining` e `rateLimit.resetAt`. O client monitora esse campo e dorme até o reset quando o saldo está abaixo de um threshold definido — sem perda de dados e sem requisições desnecessárias.

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
# Dependências
pip install -r requirements.txt

# Coleta (salva em data/repos.db, retomável se interrompida)
python src/collector.py

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
