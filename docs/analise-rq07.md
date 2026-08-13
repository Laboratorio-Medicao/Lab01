# Análise RQ07 — Linguagem vs. Contribuição, Releases e Atualização

**Metodologia:** mediana por linguagem; linguagens ordenadas por número de repositórios na amostra (proxy de popularidade).

| Linguagem | Nº de repos | Mediana de PRs mergeadas por repo (RQ02) | Mediana de releases por repo (RQ03) | Mediana de dias desde último push (RQ04) |
|---|---|---|---|---|
| Python | 24 | 1881.5 | 54.0 | 1.5 |
| TypeScript | 17 | 6981.0 | 116.0 | 0.1 |
| JavaScript | 10 | 1373.5 | 69.0 | 0.4 |

## Conclusão RQ07

A correlação de Spearman (ρ) mede se duas variáveis caminham juntas, variando de **-1 a 1**: valores próximos de **1** indicam que quanto mais popular a linguagem, maior a métrica; valores próximos de **-1** indicam o oposto; valores próximos de **0** indicam ausência de relação.

Correlação entre popularidade da linguagem (nº de repos na amostra) e cada métrica:

- **PRs mergeadas por repo (RQ02):** ρ = 0.50 → sem correlação clara
- **Releases por repo (RQ03):** ρ = -0.50 → sem correlação clara
- **Frequência de atualização — dias desde último push (RQ04):** ρ = -0.50 → sem correlação clara

**Resposta:** Não há evidência consistente de que linguagens mais populares recebam mais contribuição, releases ou atualizações.
