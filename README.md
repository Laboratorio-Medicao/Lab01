# Lab01 — Características de Repositórios Populares no GitHub

Laboratório 01 da disciplina **Laboratório de Experimentação de Software** — Engenharia de Software, 6º período.

O objetivo é coletar e analisar dados dos **1.000 repositórios com maior número de estrelas no GitHub**, respondendo seis questões de pesquisa sobre maturidade, contribuição, frequência de releases, atualização, linguagem e qualidade de issues — mais uma questão bônus (RQ07, do enunciado).

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
        │         persiste incrementalmente no Postgres (Supabase)
        ▼         (permite retomar coleta interrompida, time todo lê o mesmo banco)
   [Banco]   ←── Postgres compartilhado (Supabase — ver "Configuração do Supabase")
        │
        ├──▶ [Análise]    ←── Python + pandas + seaborn/matplotlib
        │         │              uma pessoa por grupo de RQs
        │         ▼
        │    charts/ (PNG para o relatório)
        │
        └──▶ [Dashboard]  ←── plotly → dashboard.html interativo
```

**Por que um banco (e não só o CSV)?** Dois motivos documentados na metodologia:
1. **Coleta incremental:** se o script falhar no meio dos 1.000 repos, retoma do último cursor salvo sem reprocessar.
2. **Análise com SQL:** aggregations por linguagem (RQ07) são mais expressivas com `GROUP BY` do que com manipulação manual de listas.

**Por que Postgres/Supabase (e não SQLite local)?** O projeto começou com SQLite local, mas cada integrante tinha seu próprio `repos.db` isolado — ninguém além de quem rodou a coleta conseguia consultar os dados. Migramos para um projeto Postgres compartilhado no Supabase: todo o time lê/escreve o mesmo banco, sem precisar sincronizar arquivo `.db` manualmente. As duas razões do SQLite (coleta incremental + análise com SQL) continuam valendo — só a camada física mudou.

**Conexão via pooler, não conexão direta:** o host de conexão direta do Supabase (`db.<ref>.supabase.co`) só resolve endereço IPv6, o que falha em redes sem suporte a IPv6 (comum em algumas redes domésticas/4G). Use o host do **Connection Pooling** (`aws-0-<region>.pooler.supabase.com`, modo *Transaction*, porta 6543) — ver `.env.example`.

**Por que `urllib` e não `requests`?** O enunciado proíbe bibliotecas de terceiros que consultem a API do GitHub. O `urllib.request` é built-in e cobre exatamente o que precisamos, evitando qualquer ambiguidade na interpretação da regra. (O driver `psycopg2` é third-party, mas fala com o banco — não com a API do GitHub — então está fora dessa restrição.)

**Rate limit:** a API GraphQL do GitHub limita a 5.000 pontos/hora. Cada resposta retorna `rateLimit.remaining` e `rateLimit.resetAt`. O client monitora esse campo e dorme até o reset quando o saldo está abaixo de um threshold definido — sem perda de dados e sem requisições desnecessárias. Também é comum receber um HTTP 403 de rate limit secundário (abuso por rajada de requisições) com header `Retry-After`; o client trata isso como erro retentável e espera o tempo indicado antes de tentar de novo.

**Rate limit e tamanho de página (por que o batch é 25, não 100):** testamos a `REPOSITORY_SEARCH_QUERY` diretamente contra a API em 2026-08-08 variando `perPage`. A partir de `perPage=40` o GitHub passou a responder **HTTP 502 (Bad Gateway)** de forma consistente; até `perPage=35` a resposta veio OK naquele teste. A hipótese mais provável é o custo de computar `totalCount` de `pullRequests`, `releases` e `issues` (open/closed) para muitos repositórios na mesma resposta, o que aparentemente estoura algum timeout do lado do GitHub — não é um limite documentado oficialmente pela API. Por segurança, o coletor usa **25 como tamanho de lote padrão** (`DEFAULT_BATCH_SIZE` em `collector.py`), com folga do limiar de 35-40 observado. Essa é uma decisão de metodologia que vale citar no relatório final: a coleta dos 100 (S01) e dos 1.000 (S02) repositórios não é feita em uma única requisição GraphQL, e sim em múltiplos lotes menores, com o estado (cursor + total já coletado) persistido no Postgres entre lotes — o que também é o mecanismo que permite retomar uma coleta interrompida sem reprocessar repositórios já salvos.

**Atualização (2026-08-11):** o limiar de `perPage=35-40` não é um teto confiável — em execução real contra a API, um lote de `perPage=25` retornou 502 de forma consistente (3 tentativas, mesmo após o retry/backoff do client) para uma página específica, provavelmente por causa de repositórios com contagens muito altas de PRs/issues caindo naquele lote. O custo parece depender de *quais* repositórios estão na página, não só do tamanho dela. Por isso `collect_total` (em `collector.py`) agora reduz `perPage` automaticamente pela metade (até um piso de `MIN_BATCH_SIZE=5`) sempre que uma página falha de forma retentável mesmo após o client esgotar as tentativas, e repete essa mesma página com o lote menor — sem perder o progresso já salvo (o cursor só avança em páginas bem-sucedidas). Na prática isso já resolveu o caso observado: a coleta completou os 100 repositórios sem intervenção manual.

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

# Configuração (uma vez por pessoa)
cp .env.example .env
# edite .env e preencha:
#   GITHUB_TOKEN=<token com escopo public_repo>
#   SUPABASE_HOST/PORT/DB_NAME/USER/PASSWORD  (peça as credenciais do projeto
#   Supabase do grupo a quem criou o projeto — todo mundo aponta pro mesmo
#   banco. Use o host do Connection Pooling, não o de conexão direta — ver
#   "Conexão via pooler" acima)

# Dependências (psycopg2 para o Postgres; coleta em si só usa stdlib)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# Testes automatizados (os que tocam o banco usam tabelas isoladas —
# test_repositories/test_collection_state — e são pulados se o .env não
# tiver as variáveis do Supabase configuradas)
pytest

# Coleta (grava no Postgres compartilhado, retomável se interrompida —
# o cursor fica salvo em collection_state, então qualquer pessoa do time
# pode continuar de onde a última coleta parou)
# --per-page controla o tamanho de cada requisição à API (padrão 25 — ver
# "Rate limit e tamanho de página" acima sobre por que não usar 100 direto).
# --total, se informado, encadeia lotes de --per-page até atingir a meta.
python -m src.collector                        # 1 lote de 25 repos
python -m src.collector --per-page 25 --total 100   # S01: 100 repos (4 lotes de 25)
python -m src.collector --per-page 25 --total 1000  # S02: 1.000 repos (paginação completa)
# Ao usar --total, o coletor valida no fim: total_rows == meta e distinct_ids == meta.
# Exemplo da S02: exige exatamente 1.000 registros sem duplicatas de id.

# Validação cruzada RQ01/RQ02 contra a API REST do GitHub (Issue #4)
# gera docs/validacao-rq01-rq02.md — decisões metodológicas em docs/metodologia.md
python -m src.validate_rq01_rq02 --sample-size 8

# Validação cruzada RQ03/RQ04 contra a API REST do GitHub
# gera docs/validacao-rq03-rq04.md
python -m src.validate_rq03_rq04 --sample-size 8

# Validação cruzada RQ05/RQ06 contra a API REST do GitHub (Issue #6)
# gera docs/validacao-rq05-rq06.md
python -m src.validate_rq05_rq06 --sample-size 8

# Validação cruzada RQ08 (bônus) — fork_count contra a API REST do GitHub
# gera docs/validacao-rq08.md — decisão metodológica em docs/metodologia.md
python -m src.validate_rq08 --sample-size 8

# Export para CSV (lê do Postgres, grava data/repos.csv)
python -m src.export

# Análise por RQ01/RQ02 — AINDA NÃO IMPLEMENTADO
# (analysis/rq01_02.py não existe neste repositório ainda; planejado para S03,
# junto com o restante da análise estatística/visualizações)
# python analysis/rq01_02.py

# Análise exploratória RQ03/RQ04 (1.000 repositórios completos da S02)
# gera docs/analise-rq03-rq04.md com estatística descritiva, ausentes,
# outliers, sanidade da distribuição e hipótese informal
python -m analysis.analyze_rq03_rq04

# Relatório HTML interativo com gráficos de RQ03/RQ04
python -m analysis.report_rq03_rq04

# Matriz de correlação global — Spearman, Pearson, Markdown, HTML e CSV
python -m analysis.report_correlation

# Análise RQ07 (bônus) — implementado; roda como módulo, não como script solto
# (rodar "python analysis/analyze_rq07.py" direto falha com
# ModuleNotFoundError: No module named 'src', pois o diretório do script não
# tem app/ no sys.path — use -m a partir de app/)
# gera docs/analise-rq07.md
python -m analysis.analyze_rq07

# Análise RQ08 (bônus) — distribuição, outliers e valores ausentes de
# fork_star_ratio sobre os 1.000 repositórios, confrontando a hipótese
# informal de star-farming registrada em docs/metodologia.md
# gera docs/analise-rq08.md
python -m analysis.analyze_rq08

# Dashboard interativo — AINDA NÃO IMPLEMENTADO
# (dashboard/generate.py não existe neste repositório ainda; planejado para S03)
# python dashboard/generate.py
# → abriria output/dashboard.html

# Snapshot do Kanban (grava kanban/snapshots/kanban-snapshot-YYYY-MM-DD.csv)
# Requer GITHUB_TOKEN com acesso à organização Laboratorio-Medicao.
# Nota: tokens fine-grained com prazo > 366 dias são bloqueados pela org —
# gere um token com prazo menor ou use um token clássico (classic PAT).
python -m kanban.snapshot
# opções:
python -m kanban.snapshot --org Laboratorio-Medicao --project 1
```

---

## Configuração do Processo (GitHub Projects)

O grupo utiliza um **GitHub Projects v2** com o seguinte board Kanban:

| Coluna | Descrição |
|--------|-----------|
| **Backlog** | Tarefas identificadas mas ainda não priorizadas |
| **To Do** | Tarefas priorizadas para a sprint atual |
| **Doing** | Tarefas em andamento — sujeitas ao limite de WIP |
| **Review** | Tarefas concluídas aguardando revisão do grupo |
| **Done** | Tarefas concluídas e validadas |

**Limite de WIP (Work in Progress):** `6 itens na coluna Doing`

**Justificativa:** O grupo é formado por 3 integrantes. Definimos WIP = 6 (2 por integrante) para acomodar situações em que uma tarefa está bloqueada aguardando revisão de outro membro, permitindo que o integrante inicie uma segunda tarefa sem paralisar o fluxo. Esse limite evita sobrecarga excessiva e mantém visibilidade sobre o trabalho em andamento.

---

## Equipe

| Integrante | RQs | Responsabilidade principal |
|------------|-----|---------------------------|
| Pessoa A | RQ01, RQ02 | Client GraphQL + análise de idade e PRs |
| Pessoa B | RQ03, RQ04 | Paginação + análise de releases e atualização |
| Pessoa C | RQ05, RQ06, RQ07 | Linguagens + issues + bônus + export Kanban |

---

## Links

- **Repositório:** https://github.com/Laboratorio-Medicao/Lab01-v2
- **GitHub Projects (Kanban):** `<preencher após criação>`
- **Relatório Final:** `<preencher após entrega>`
