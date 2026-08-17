# Análise exploratória RQ01/RQ02 — amostra de 1.000 repositórios (Sprint S02)

**Total de repositórios na amostra:** 1000

**Escopo:** validação estatística de consistência (distribuição, outliers, valores ausentes) sobre a totalidade dos 1.000 repositórios coletados — distinta da validação cruzada campo-a-campo contra a REST API já feita em S01 (`docs/validacao-rq01-rq02.md`, amostra de 8 repositórios). Ver `docs/fonte-da-verdade-s02.md`, seção 8.1.

## RQ01 — Idade do repositório (anos) (created_at)

| Métrica | Valor |
|---|---|
| N (valores presentes) | 1000 |
| Valores ausentes | 0 |
| Mínimo | 0.00 |
| 1º quartil (Q1) | 3.50 |
| Mediana | 7.70 |
| Média | 7.65 |
| 3º quartil (Q3) | 11.33 |
| Máximo | 18.40 |
| IQR (Q3-Q1) | 7.83 |

**Método de outlier:** regra do IQR (1.5×) — valores abaixo de `-8.24` ou acima de `23.06` são tratados como atípicos.

- Outliers baixos: 0
- Outliers altos: 0

## RQ02 — Pull requests aceitas (merged) (merged_pull_requests)

| Métrica | Valor |
|---|---|
| N (valores presentes) | 1000 |
| Valores ausentes | 0 |
| Mínimo | 0.00 |
| 1º quartil (Q1) | 175.00 |
| Mediana | 768.00 |
| Média | 4212.96 |
| 3º quartil (Q3) | 3391.25 |
| Máximo | 103167.00 |
| IQR (Q3-Q1) | 3216.25 |

**Método de outlier:** regra do IQR (1.5×) — valores abaixo de `-4649.38` ou acima de `8215.62` são tratados como atípicos.

- Outliers baixos: 0
- Outliers altos: 123

**Top outliers altos:**

| Repositório | Valor |
|---|---|
| firstcontributions/first-contributions | 103167.00 |
| llvm/llvm-project | 96690.00 |
| elastic/elasticsearch | 95345.00 |
| getsentry/sentry | 91101.00 |
| home-assistant/core | 90011.00 |
| rust-lang/rust | 73490.00 |
| grafana/grafana | 69289.00 |
| ClickHouse/ClickHouse | 68948.00 |
| kubernetes/kubernetes | 65646.00 |
| python/cpython | 62610.00 |
| swiftlang/swift | 60647.00 |
| PostHog/posthog | 54015.00 |
| DefinitelyTyped/DefinitelyTyped | 53478.00 |
| microsoft/vscode | 51978.00 |
| flutter/flutter | 49578.00 |

## Achado de star-farming (RQ01) — comparação S01 → S02

Repositórios com idade < 1.5 anos e mais de 100,000 estrelas: **21 de 1000** (2.1%).

Em S01 (amostra de 100), esse padrão apareceu em 16% da amostra (`docs/metodologia.md`, seção "Risco de dados"). A proporção mudou de forma perceptível ao expandir para 1.000 repositórios — merece nota explícita na discussão hipótese vs. resultado do Relatório Final (RQ01).

**Top 10 por estrelas:**

| Repositório | Estrelas | Idade (anos) |
|---|---|---|
| openclaw/openclaw | 386403 | 0.70 |
| obra/superpowers | 272495 | 0.80 |
| affaan-m/ECC | 240297 | 0.60 |
| NousResearch/hermes-agent | 231075 | 1.10 |
| mattpocock/skills | 218365 | 0.50 |
| multica-ai/andrej-karpathy-skills | 202766 | 0.50 |
| anomalyco/opencode | 197797 | 1.30 |
| ultraworkers/claw-code | 195053 | 0.40 |
| anthropics/skills | 169559 | 0.90 |
| msitarzewski/agency-agents | 145624 | 0.80 |

## Hipóteses informais

### RQ01 — Idade do repositório

**Hipótese:** a maior parte dos repositórios populares acumula estrelas ao longo de vários anos — a mediana de idade da amostra de 1.000 deve ficar acima de 3 anos, com uma cauda de repositórios jovens (< 1,5 anos) puxada principalmente pelo fenômeno de star-farming/hype de IA já documentado em S01, não pela maioria da amostra.

**Justificativa:** popularidade orgânica (uso, indicação, cobertura de comunidade) é um processo cumulativo; picos de crescimento rápido em poucos meses são exceção, não regra, mesmo entre os repositórios mais estrelados do GitHub — achado já registrado em `docs/metodologia.md` para a amostra de 100.

**Métrica relacionada:** `age_years` (`src/metrics.compute_age_years`), confrontada com a mediana observada nesta análise e, em S03/Relatório Final, com o percentual de repositórios no grupo de star-farming.

### RQ02 — Pull requests aceitas

**Hipótese:** a distribuição de `merged_pull_requests` deve ser fortemente assimétrica à direita (poucos repositórios com dezenas de milhares de PRs mergeadas, a maioria concentrada em uma faixa muito menor), com uma cauda de outliers formada por projetos maduros e com grande base de contribuidores externos (ex.: linguagens/frameworks de uso massivo).

**Justificativa:** contribuição via pull request depende de comunidade ativa de terceiros, que só se forma depois de o projeto já ser conhecido — repositórios muito jovens (mesmo que populares em estrelas) tendem a ainda não ter acumulado um volume alto de PRs aceitas, diferente de estrelas, que podem crescer de forma mais rápida (inclusive artificialmente).

**Métrica relacionada:** `merged_pull_requests`, confrontada com a mediana e os outliers altos identificados nesta análise.
