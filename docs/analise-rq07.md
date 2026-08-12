# Análise RQ07 — Linguagem vs. Contribuição, Releases e Atualização

**Metodologia:** mediana por linguagem; linguagens ordenadas por número de repositórios na amostra (proxy de popularidade).

| Linguagem | Nº de repos | Mediana de PRs mergeadas por repo (RQ02) | Mediana de releases por repo (RQ03) | Mediana de dias desde último push (RQ04) |
|---|---|---|---|---|
| Python | 23 | 1875.0 | 39.0 | 4.3 |
| TypeScript | 17 | 6861.0 | 67.0 | 3.2 |
| JavaScript | 10 | 1370.5 | 13.5 | 3.6 |
| Shell | 5 | 222.0 | 7.0 | 4.4 |
| C++ | 5 | 26436.0 | 470.0 | 3.3 |
| Rust | 5 | 4188.0 | 39.0 | 4.2 |
| Go | 5 | 3494.0 | 0.0 | 3.8 |
| C | 3 | 153.0 | 52.0 | 3.4 |
| HTML | 3 | 315.0 | 0.0 | 3.9 |
| Markdown | 2 | 200.5 | 0.0 | 96.4 |
| Jupyter Notebook | 2 | 307.0 | 0.0 | 9.6 |
| Batchfile | 1 | 7.0 | 31.0 | 38.3 |
| Dart | 1 | 49411.0 | 7.0 | 3.3 |
| MDX | 1 | 9473.0 | 94.0 | 3.9 |
| Java | 1 | 994.0 | 10.0 | 18.7 |
| C# | 1 | 589.0 | 332.0 | 3.5 |
| Swift | 1 | 1237.0 | 0.0 | 4.1 |

## Conclusão RQ07

A correlação de Spearman (ρ) mede se duas variáveis caminham juntas, variando de **-1 a 1**: valores próximos de **1** indicam que quanto mais popular a linguagem, maior a métrica; valores próximos de **-1** indicam o oposto; valores próximos de **0** indicam ausência de relação.

Correlação entre popularidade da linguagem (nº de repos na amostra) e cada métrica:

- **PRs mergeadas por repo (RQ02):** ρ = 0.16 → sem correlação clara
- **Releases por repo (RQ03):** ρ = 0.25 → sem correlação clara
- **Frequência de atualização — dias desde último push (RQ04):** ρ = 0.19 → sem correlação clara

**Resposta:** Não há evidência consistente de que linguagens mais populares recebam mais contribuição, releases ou atualizações.
