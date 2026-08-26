# Matriz de correlação global

Esta análise considera as métricas numéricas coletadas e as métricas derivadas de datas e razões. A matriz principal usa correlação de Spearman; Pearson é apresentada para comparação.

## Métricas

Métrica | Descrição
|---|---|
| `stargazer_count` | Estrelas |
| `fork_count` | Forks |
| `merged_pull_requests` | PRs mergeadas |
| `releases_count` | Releases |
| `open_issues` | Issues abertas |
| `closed_issues` | Issues fechadas |
| `is_fork` | É fork |
| `is_archived` | Arquivado |
| `idade_anos` | Idade (anos) |
| `dias_desde_ultimo_push` | Dias desde último push |
| `issues_total` | Issues totais |
| `closed_issues_ratio` | Razão de issues fechadas |
| `fork_star_ratio` | Razão forks/estrelas |

## Pares com maior correlação absoluta (Spearman)

| Métrica A | Métrica B | ρ | N |
|---|---:|---:|---:|
| `closed_issues` | `issues_total` | 0.989 | 1000 |
| `fork_count` | `fork_star_ratio` | 0.821 | 1000 |
| `merged_pull_requests` | `closed_issues` | 0.733 | 1000 |
| `merged_pull_requests` | `issues_total` | 0.713 | 1000 |
| `releases_count` | `closed_issues` | 0.710 | 1000 |
| `releases_count` | `issues_total` | 0.697 | 1000 |
| `open_issues` | `issues_total` | 0.688 | 1000 |
| `stargazer_count` | `fork_count` | 0.611 | 1000 |
| `merged_pull_requests` | `releases_count` | 0.609 | 1000 |
| `open_issues` | `closed_issues` | 0.605 | 1000 |

## Interpretação

- Correlação positiva indica que as métricas tendem a crescer juntas; correlação negativa indica movimentos opostos.
- Spearman é o resultado principal porque é menos sensível à assimetria e aos outliers presentes nas contagens do GitHub.
- A correlação não implica causalidade. Métricas derivadas de outras, como `issues_total` e `fork_star_ratio`, podem produzir relações matematicamente esperadas.
- O valor de N pode variar por par porque os cálculos usam observações válidas para as duas métricas comparadas.
