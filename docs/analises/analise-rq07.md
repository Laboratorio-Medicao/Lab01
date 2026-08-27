# Análise RQ07 — Linguagem vs. Contribuição, Releases e Atualização

**Metodologia:** mediana por linguagem; linguagens ordenadas por número de repositórios na amostra (proxy de popularidade).

| Linguagem | Nº de repos | Mediana de PRs mergeadas por repo (RQ02) | Mediana de releases por repo (RQ03) | Mediana de dias desde último push (RQ04) |
|---|---|---|---|---|
| Python | 229 | 560.0 | 20.0 | 3.5 |
| TypeScript | 174 | 1996.5 | 134.0 | 0.5 |
| JavaScript | 111 | 617.0 | 39.0 | 7.7 |
| Go | 76 | 1690.0 | 139.5 | 0.8 |
| Rust | 57 | 2491.0 | 90.0 | 0.8 |
| Java | 41 | 939.0 | 54.0 | 2.8 |
| C++ | 40 | 1121.0 | 50.5 | 1.3 |
| Jupyter Notebook | 24 | 78.0 | 0.0 | 23.9 |
| C | 21 | 294.0 | 43.0 | 1.4 |
| Shell | 20 | 389.5 | 9.5 | 12.4 |

## Conclusão RQ07

A correlação de Spearman (ρ) mede se duas variáveis caminham juntas, variando de **-1 a 1**: valores próximos de **1** indicam que quanto mais popular a linguagem, maior a métrica; valores próximos de **-1** indicam o oposto; valores próximos de **0** indicam ausência de relação.

Correlação entre popularidade da linguagem (nº de repos na amostra) e cada métrica:

- **PRs mergeadas por repo (RQ02):** ρ = 0.52 → correlação positiva
- **Releases por repo (RQ03):** ρ = 0.39 → sem correlação clara
- **Frequência de atualização — dias desde último push (RQ04):** ρ = 0.39 → sem correlação clara

**Resposta:** Não há evidência consistente de que linguagens mais populares recebam mais contribuição, releases ou atualizações.
