# Análise RQ08 (bônus) — Engajamento real: razão forks/estrelas — amostra de 1.000 repositórios (Sprint S02)

**Total de repositórios na amostra:** 1000

**Escopo:** validação estatística de consistência (distribuição, outliers, valores ausentes) de `fork_star_ratio` sobre a totalidade dos 1.000 repositórios coletados — distinta da validação cruzada campo-a-campo de `fork_count` contra a REST API já feita em `docs/validacoes/validacao-rq08.md` (amostra de 8 repositórios). Ver `docs/metodologia.md`, seção "RQ08 (bônus) — Engajamento real: razão forks/estrelas".

## `fork_star_ratio` (fork_count / stargazer_count)

| Métrica | Valor |
|---|---|
| N (valores presentes) | 1000 |
| Valores ausentes | 0 |
| Mínimo | 0.0009 |
| 1º quartil (Q1) | 0.0772 |
| Mediana | 0.1144 |
| Média | 0.1458 |
| 3º quartil (Q3) | 0.1798 |
| Máximo | 1.9449 |
| IQR (Q3-Q1) | 0.1026 |

**Método de outlier:** regra do IQR (1.5×) — valores abaixo de `-0.0768` ou acima de `0.3337` são tratados como atípicos.

- Outliers baixos: 0
- Outliers altos: 53

**Top outliers altos (mais forks que estrelas, proporcionalmente):**

| Repositório | `fork_star_ratio` |
|---|---|
| firstcontributions/first-contributions | 1.9449 |
| eugenp/tutorials | 1.4287 |
| ZhuLinsen/daily_stock_analysis | 0.8409 |
| apache/spark | 0.6690 |
| ChatGPTNextWeb/NextChat | 0.6685 |
| spring-projects/spring-framework | 0.6443 |
| apache/dubbo | 0.6351 |
| opencv/opencv | 0.6298 |
| odoo/odoo | 0.6221 |
| DefinitelyTyped/DefinitelyTyped | 0.5915 |
| tensorflow/models | 0.5782 |
| ultraworkers/claw-code | 0.5594 |
| ant-design/ant-design | 0.5520 |
| shadowsocks/shadowsocks | 0.5369 |
| BVLC/caffe | 0.5332 |

## Valores ausentes — detalhamento por causa

`compute_fork_star_ratio` retorna `None` por dois motivos distintos (`src/metrics.py`):

| Causa | Quantidade |
|---|---|
| `fork_count` ainda não coletado (`NULL`) | 0 |
| `stargazer_count = 0` (razão indefinida) | 0 |
| **Total de ausentes** | **0** |

## Confronto com a hipótese informal (star-farming vs. resto da amostra)

**Hipótese registrada em `docs/metodologia.md`:** repositórios no grupo suspeito de star-farming (idade < 1.5 anos e mais de 100,000 estrelas) devem ter `fork_star_ratio` sistematicamente mais baixo que o resto da amostra.

| Grupo | N | Mediana de `fork_star_ratio` |
|---|---|---|
| Star-farming (idade < 1.5a, > 100,000⭐) | 21 | 0.1190 |
| Resto da amostra | 979 | 0.1144 |

**Resultado:** a hipótese não se confirma nesta amostra — o grupo suspeito de star-farming tem `fork_star_ratio` mediano (0.1190) igual ou maior que o resto da amostra (0.1144). Isso não invalida o achado de star-farming em si (RQ01), mas sugere que `fork_star_ratio` sozinho não é um discriminador forte para esse grupo — merece nota explícita na discussão hipótese vs. resultado do Relatório Final (RQ08).
