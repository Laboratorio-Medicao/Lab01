# Metodologia — decisões de coleta e métricas

Este documento registra decisões metodológicas tomadas durante a coleta, para
que os números do Relatório Final sejam reprodutíveis e defensáveis. Cada
seção corresponde a uma decisão da especificação da Issue #4.

## RQ01 — Idade do repositório

**Campo fonte:** `createdAt` (GraphQL, ISO 8601 UTC).

**Fórmula:**

```
idade_em_anos = (collected_at - created_at) / 365.25 dias
```

- **Referência de "hoje":** não é o momento em que a análise roda, e sim
  `collected_at`, o timestamp UTC (`datetime('now')` do SQLite) salvo em cada
  linha da tabela `repositories` no momento em que aquele repositório foi
  coletado. Isso garante que o cálculo de idade seja reproduzível mesmo que a
  coleta de S01 (100 repos) e a de S02 (1.000 repos) ocorram em dias
  diferentes — cada linha carrega sua própria referência temporal, em vez de
  depender da data em que um script de análise é executado depois.
- **365.25, não 365:** considera anos bissextos. Repositórios populares têm
  em geral vários anos de idade, então o erro acumulado de ignorar bissextos
  deixaria de ser desprezível.
- **Arredondamento:** exibição com 1 casa decimal; o valor bruto em dias fica
  disponível via `created_at`/`collected_at` para recomputar com outra
  precisão nas análises de S03, se necessário.

## Risco de dados: repositórios jovens com alto número de estrelas

**Achado (checagem ad-hoc sobre os 100 repositórios coletados em
2026-08-08):** 16 repositórios (16% da amostra) têm menos de 1,5 anos de
idade e mais de 100 mil estrelas — uma combinação que ataca diretamente a
hipótese informal da RQ01 ("popularidade se acumula ao longo de anos, não
aparece do dia para a noite").

| Repositório | Estrelas | Idade (anos) | `createdAt` |
|---|---|---|---|
| openclaw/openclaw | 385568 | 0.70 | 2025-11-24 |
| obra/superpowers | 269278 | 0.83 | 2025-10-09 |
| affaan-m/ECC | 238801 | 0.55 | 2026-01-18 |
| NousResearch/hermes-agent | 227497 | 1.04 | 2025-07-22 |
| mattpocock/skills | 209921 | 0.51 | 2026-02-03 |
| multica-ai/andrej-karpathy-skills | 200686 | 0.53 | 2026-01-27 |
| anomalyco/opencode | 195082 | 1.27 | 2025-04-30 |
| ultraworkers/claw-code | 195015 | 0.36 | 2026-03-31 |
| anthropics/skills | 167046 | 0.88 | 2025-09-22 |
| x1xhlol/system-prompts-and-models-of-ai-tools | 142664 | 1.43 | 2025-03-05 |
| anthropics/claude-code | 140722 | 1.46 | 2025-02-22 |
| msitarzewski/agency-agents | 139595 | 0.82 | 2025-10-13 |
| garrytan/gstack | 126977 | 0.41 | 2026-03-11 |
| github/spec-kit | 125889 | 0.96 | 2025-08-21 |
| farion1231/cc-switch | 125700 | 1.01 | 2025-08-04 |
| nextlevelbuilder/ui-ux-pro-max-skill | 114721 | 0.69 | 2025-11-30 |

**Interpretação:** parte desses casos é plausível — repositórios de
organizações já estabelecidas e com forte tração de mercado (`anthropics/*`,
`github/spec-kit`) podem legitimamente acumular centenas de milhares de
estrelas em poucos meses. Outros, porém, seguem um padrão que a comunidade do
GitHub documentou como característico de **star-farming/fake stars** em
2025-2026 (crescimento de estrelas incompatível com qualquer métrica de
adoção orgânica — commits, issues, forks — combinado a nomes de owner sem
histórico ou ligados ao hype de IA/agentes): `ultraworkers/claw-code`,
`garrytan/gstack`, `multica-ai/andrej-karpathy-skills`, `affaan-m/ECC`, entre
outros.

**Decisão para esta issue:** **não filtrar** esses repositórios agora — não
há um critério objetivo e barato (sem ferramenta de terceiros, que o
enunciado proíbe) para separar tração orgânica de estrelas compradas nesta
etapa da coleta. O campo `stargazer_count` e a idade calculada continuam
sendo salvos como estão, sem alteração.

**Ação obrigatória:** esse achado **precisa ser discutido explicitamente na
seção "Discussão hipótese vs. resultado" do Relatório Final** ao tratar a
RQ01 — se a mediana de idade dos 1.000 repositórios (S02) vier
inesperadamente baixa, ou se a distribuição mostrar uma cauda de
repositórios muito jovens e muito estrelados, este é o motivo mais provável,
não um problema na coleta. Vale considerar, em S03, uma análise de
sensibilidade (mediana com e sem outliers de idade) para não deixar esse
efeito mascarado nos números agregados.

## RQ02 — Pull requests aceitas

**Campo fonte:** `mergedPullRequests: pullRequests(states: MERGED) { totalCount }`.

**Definição adotada:** "aceita" = pull request com estado `MERGED` no GitHub.
Uma PR `CLOSED` sem merge (rejeitada, abandonada, fechada manualmente sem
incorporar o código) **não** conta como aceita — a query já filtra
corretamente por `states: MERGED`, então não há PRs `CLOSED`-sem-merge
misturadas na contagem.

## Forks

**Decisão:** o campo `isFork` foi adicionado à query GraphQL e ao schema
(`repositories.is_fork`, `0`/`1`). Forks **não são excluídos** da amostra por
padrão — a busca (`TOP_STARRED_REPOSITORIES_SEARCH_QUERY`) continua sem
`fork:false`. Na amostra atual de 100 repositórios coletados em 2026-08-08,
`is_fork = 1` em **0** repositórios, então a decisão não teve impacto
observável nesta sprint; o campo fica disponível para reportar/filtrar em S02
(1.000 repos) e no Relatório Final caso forks apareçam em volume relevante.

## Repositórios arquivados

**Decisão:** o campo `isArchived` foi adicionado junto com `isFork` (mesma
alteração de schema/coleta, evitando reabrir a query depois). Não afeta
RQ01/RQ02 diretamente — idade e PRs merged continuam válidos para um
repositório arquivado — mas será usado em RQ04 (frequência de atualização).
Na amostra atual, `is_archived = 1` em **0** repositórios.

## Tratamento de valores nulos

- `createdAt`: campo obrigatório do schema do GitHub para qualquer
  repositório. Na amostra coletada, 0 linhas têm `created_at IS NULL` — um
  nulo aqui indicaria erro de coleta, não "sem dado".
- `mergedPullRequests.totalCount`: `totalCount` de uma conexão GraphQL nunca é
  nulo (retorna `0` quando não há PRs merged). Na amostra, 0 linhas têm
  `merged_pull_requests IS NULL`. Um valor `0` legítimo (ex.:
  `torvalds/linux`, que não usa pull requests do GitHub para merge — os
  commits chegam por outro fluxo) foi confirmado como zero real, não como
  nulo mascarado.

## Validação cruzada (evidência em `docs/validacao-rq01-rq02.md`)

O script `app/src/validate_rq01_rq02.py` cruza os dados coletados via GraphQL
com a API REST do GitHub para uma amostra de 8 repositórios:

- `createdAt` é conferido contra `GET /repos/{owner}/{repo}`.
- `mergedPullRequests.totalCount` é conferido paginando
  `GET /repos/{owner}/{repo}/pulls?state=closed` e contando entradas com
  `merged_at` não nulo — **fonte da verdade**, não uma estimativa.

Duas observações técnicas relevantes encontradas durante a validação:

1. **A REST Search API (`/search/issues?q=...+is:merged`) não é confiável
   para esta conferência.** Um teste inicial com `is:merged` no Search API
   subcontou sistematicamente as PRs merged em todos os repositórios testados
   (ex.: `freeCodeCamp/freeCodeCamp`: 29048 via GraphQL vs. 28663 via Search),
   por causa da defasagem de indexação conhecida desse endpoint para
   repositórios grandes. Por isso o script usa paginação direta de
   `/pulls?state=closed`, que não depende de índice de busca.
2. **Repositórios com `has_issues: false` retornam HTTP 404 em
   `/pulls`**, mesmo tendo PRs merged reais e confirmadas via GraphQL (ex.:
   `awesome-selfhosted/awesome-selfhosted`, `torvalds/linux`,
   `DigitalPlatDev/FreeDomain`). O script detecta esse caso e pula o
   repositório para o próximo candidato, em vez de registrar como
   divergência de dado — é uma limitação da REST API, não um erro na coleta
   GraphQL.

Resultado: nos 8 repositórios validados com sucesso, `createdAt` e
`mergedPullRequests` bateram 100% com a REST API (ver tabela em
`docs/validacao-rq01-rq02.md`).
