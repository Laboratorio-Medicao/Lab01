# Análise Exploratória — RQ03 e RQ04 (1000 repositórios)

Esta análise usa os dados completos da coleta (S02), sem nova validação REST amostral.
Data de referência para RQ04: 2026-08-19T23:01:10.338779+00:00

## Sumário Estatístico

| Métrica | N válido | Média | Mediana | Mín | Q1 | Q3 | Máx | IQR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `releases_count` (RQ03) | 1000 | 127.35 | 39.50 | 0.00 | 0.00 | 148.25 | 1000.00 | 148.25 |
| `dias_desde_ultimo_push` (RQ04) | 1000 | 116.36 | 5.87 | 2.46 | 2.71 | 52.50 | 2451.77 | 49.79 |

## Valores Ausentes e Qualidade dos Campos

- Total de linhas analisadas: 1000
- `releases_count` ausente: 0 (0.00%)
- `pushed_at` ausente/vazio: 0 (0.00%)
- `pushed_at` inválido: 0 (0.00%)
- `pushed_at` no futuro: 0 (0.00%)

## Outliers (Regra IQR)

| Campo | Limite inferior | Limite superior | Qtde de outliers | % do total válido |
|---|---:|---:|---:|---:|
| `releases_count` | -222.38 | 370.62 | 94 | 9.40% |
| `dias_desde_ultimo_push` | -71.98 | 127.19 | 190 | 19.00% |

## Sanidade da Distribuição

- Repositórios com `releases_count = 0`: 280 (28.00% dos válidos de RQ03)
- Repositórios com último push muito antigo (>= 10 anos): 0 (0.00% dos válidos de RQ04)
- Interpretação esperada: RQ03 tende a ser assimétrica (cauda longa), e RQ04 tende a concentrar em baixa defasagem com poucos casos muito antigos.

## Hipótese Informal (RQ03 e RQ04)

**RQ03 (total de releases):** espera-se uma distribuição assimétrica à direita, com muitos repositórios populares tendo poucos releases formais (incluindo 0) e um grupo menor concentrando grande volume de releases. Isso acontece porque parte dos projetos adota entrega contínua sem versionamento frequente por release.

**RQ04 (tempo desde última atualização):** espera-se concentração em valores baixos (dias ou poucas semanas), pois repositórios muito populares tendem a manter atividade contínua. Ainda assim, deve existir uma cauda de projetos estáveis/legados com último push antigo, inclusive alguns outliers.
