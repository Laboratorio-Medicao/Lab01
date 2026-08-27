# Análise exploratória RQ05/RQ06 — amostra de 1.000 repositórios (Sprint S02)

**Total de repositórios na amostra:** 1000

## RQ05 — Linguagem primária

**Total de repositórios:** 1000 | **Sem linguagem definida:** 87 (8.7%)

**Referência de popularidade:** TIOBE Index (agosto de 2026)

| Posição | Linguagem | Nº de repos | % da amostra | TIOBE Top 20 |
|---|---|---|---|---|
| 1 | Python | 229 | 22.9% | #1 |
| 2 | TypeScript | 174 | 17.4% | — |
| 3 | JavaScript | 111 | 11.1% | #6 |
| 4 | Go | 76 | 7.6% | #14 |
| 5 | Rust | 57 | 5.7% | #10 |
| 6 | Java | 41 | 4.1% | #4 |
| 7 | C++ | 40 | 4.0% | #3 |
| 8 | Jupyter Notebook | 24 | 2.4% | — |
| 9 | C | 21 | 2.1% | #2 |
| 10 | Shell | 20 | 2.0% | — |
| 11 | Ruby | 13 | 1.3% | #16 |
| 12 | HTML | 11 | 1.1% | — |
| 13 | Swift | 10 | 1.0% | #17 |
| 14 | Kotlin | 9 | 0.9% | — |
| 15 | C# | 8 | 0.8% | #5 |
| 16 | CSS | 8 | 0.8% | — |
| 17 | Dart | 6 | 0.6% | — |
| 18 | Vue | 6 | 0.6% | — |
| 19 | Markdown | 5 | 0.5% | — |
| 20 | MDX | 4 | 0.4% | — |
| 21 | Clojure | 4 | 0.4% | — |
| 22 | PHP | 4 | 0.4% | #13 |
| 23 | Vim Script | 3 | 0.3% | — |
| 24 | Zig | 3 | 0.3% | — |
| 25 | Dockerfile | 2 | 0.2% | — |
| 26 | Scala | 2 | 0.2% | — |
| 27 | PowerShell | 2 | 0.2% | — |
| 28 | Makefile | 2 | 0.2% | — |
| 29 | Haskell | 2 | 0.2% | — |
| 30 | Astro | 2 | 0.2% | — |
| 31 | TeX | 2 | 0.2% | — |
| 32 | Batchfile | 1 | 0.1% | — |
| 33 | Blade | 1 | 0.1% | — |
| 34 | Roff | 1 | 0.1% | — |
| 35 | Assembly | 1 | 0.1% | #20 |
| 36 | Nunjucks | 1 | 0.1% | — |
| 37 | Julia | 1 | 0.1% | — |
| 38 | Lua | 1 | 0.1% | — |
| 39 | Svelte | 1 | 0.1% | — |
| 40 | LLVM | 1 | 0.1% | — |
| 41 | V | 1 | 0.1% | — |
| 42 | Elixir | 1 | 0.1% | — |
| 43 | Objective-C | 1 | 0.1% | — |

Das 43 linguagens encontradas, **12 aparecem no top 20 do TIOBE** e 31 não aparecem. Os repositórios que usam uma linguagem do TIOBE top 20 representam **611 repos (61.1% da amostra)**. 87 repos (8.7%) não têm linguagem definida.

**Linguagens fora do TIOBE top 20 com mais repos:** TypeScript (174 repos), Jupyter Notebook (24 repos), Shell (20 repos), HTML (11 repos), Kotlin (9 repos).

### Hipótese informal — RQ05

**Fonte de referência:** TIOBE Index (agosto de 2026) — https://www.tiobe.com/tiobe-index/

**Hipótese:** Python e JavaScript devem ocupar as primeiras posições da distribuição nos 1.000 repositórios mais populares do GitHub, refletindo o domínio dessas linguagens em projetos open-source de alta visibilidade (IA/ML, frameworks web, ferramentas de CLI). C e C++ devem aparecer em seguida, puxados por projetos de sistemas e kernels históricos com grande base de estrelas acumulada ao longo de anos. A maioria das linguagens presentes na amostra deve coincidir com o top 20 do TIOBE.

**Justificativa:** o TIOBE Index mede popularidade com base em buscas em motores de busca globais; linguagens com maior adoção tendem a dominar tanto as buscas quanto os repositórios mais populares do GitHub. A exceção esperada é TypeScript, que não aparece no top 20 do TIOBE mas tem forte presença em projetos open-source modernos.

## RQ06 — Razão de issues fechadas

**N (repositórios com ao menos uma issue):** 957 | **Repositórios sem nenhuma issue (ratio = indefinido):** 43

| Métrica | Valor |
|---|---|
| N (valores presentes) | 957 |
| Valores ausentes (zero issues) | 43 |
| Mínimo | 0.0769 |
| 1º quartil (Q1) | 0.7044 |
| Mediana | 0.8763 |
| Média | 0.8025 |
| 3º quartil (Q3) | 0.9677 |
| Máximo | 1.0000 |
| IQR (Q3-Q1) | 0.2633 |

**Método de outlier:** regra do IQR (1.5×) — valores acima de `1.3626` são tratados como atípicos.
- Outliers altos: 0

### Hipótese informal — RQ06

**Hipótese:** a mediana da razão `closed_issues / total_issues` deve ficar acima de 0,5 (mais issues fechadas do que abertas), com uma distribuição assimétrica à esquerda — a maioria dos repositórios populares mantém bom controle do backlog, mas uma cauda de projetos muito ativos tem grande número de issues abertas em relação ao fechado.

**Justificativa:** projetos open-source com alta popularidade costumam ter mantenedores ativos que fecham issues regularmente, mas à medida que o projeto cresce a taxa de abertura de novas issues tende a superar a de fechamento, especialmente em projetos com muita adoção recente.
