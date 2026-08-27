# Análise Exploratória — RQ03 e RQ04 (1000 repositórios)

Esta análise usa os dados completos da coleta (S02), sem nova validação REST amostral.
Referência para RQ04: `collected_at` de cada repositório (não a data de execução deste script) — garante reprodutibilidade, mesmo critério já usado em RQ01.

## Sumário Estatístico

| Métrica | N válido | Média | Mediana | Mín | Q1 | Q3 | Máx | IQR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `releases_count` (RQ03) | 1000 | 127.35 | 39.50 | 0.00 | 0.00 | 148.25 | 1000.00 | 148.25 |
| `dias_desde_ultimo_push` (RQ04) | 999 | 113.86 | 3.11 | 0.00 | 0.19 | 50.98 | 2449.31 | 50.79 |

## Valores Ausentes e Qualidade dos Campos

- Total de linhas analisadas: 1000
- `releases_count` ausente: 0 (0.00%)
- `pushed_at` ausente/vazio: 0 (0.00%)
- `pushed_at` inválido: 0 (0.00%)
- `pushed_at` no futuro: 1 (0.10%)

## Outliers (Regra IQR)

| Campo | Limite inferior | Limite superior | Qtde de outliers | % do total válido |
|---|---:|---:|---:|---:|
| `releases_count` | -222.38 | 370.62 | 94 | 9.40% |
| `dias_desde_ultimo_push` | -75.99 | 127.17 | 188 | 18.82% |

## Sanidade da Distribuição

- Repositórios com `releases_count = 0`: 280 (28.00% dos válidos de RQ03)
- Repositórios com último push muito antigo (>= 10 anos): 0 (0.00% dos válidos de RQ04)
- Interpretação esperada: RQ03 tende a ser assimétrica (cauda longa), e RQ04 tende a concentrar em baixa defasagem com poucos casos muito antigos.

## Hipótese Informal (RQ03 e RQ04)

**RQ03 (total de releases):** espera-se uma distribuição assimétrica à direita, com muitos repositórios populares tendo poucos releases formais (incluindo 0) e um grupo menor concentrando grande volume de releases. Isso acontece porque parte dos projetos adota entrega contínua sem versionamento frequente por release.

**RQ04 (tempo desde última atualização):** espera-se concentração em valores baixos (dias ou poucas semanas), pois repositórios muito populares tendem a manter atividade contínua. Ainda assim, deve existir uma cauda de projetos estáveis/legados com último push antigo, inclusive alguns outliers.
