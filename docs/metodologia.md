# Metodologia — decisões de coleta e métricas

Este documento registra decisões metodológicas tomadas durante a coleta, para
que os números do Relatório Final sejam reprodutíveis e defensáveis. Cada
seção corresponde a uma decisão da especificação da Issue #4.

## Armazenamento — Postgres (Supabase) em vez de SQLite local

**Decisão:** os dados coletados são persistidos em um banco Postgres
compartilhado (projeto Supabase do grupo), não em CSV solto nem em SQLite
local por integrante.

**Por que um banco, e não só CSV:**

1. **Coleta incremental/retomável.** A busca dos 1.000 repositórios (S02) é
   feita em múltiplos lotes (25 por página — ver README, seção "Rate limit e
   tamanho de página"), não em uma única requisição. Se o script for
   interrompido no meio, o cursor da última página e o total já coletado
   ficam salvos em `collection_state`; a próxima execução retoma dali, sem
   reprocessar repositórios já salvos.
2. **Agregação com SQL.** RQ07 depende de agrupar RQ02/RQ03/RQ04 por
   linguagem (RQ05) — um `GROUP BY primary_language` é mais direto e menos
   sujeito a erro do que reimplementar a agregação em listas/dicionários
   Python.

**Por que Postgres/Supabase, e não SQLite:** o projeto começou com SQLite
local (ver commits iniciais do client GraphQL), mas cada integrante tinha seu
próprio arquivo `repos.db` isolado — ninguém além de quem rodou a coleta
localmente conseguia consultar os dados dos outros. A migração para um
projeto Postgres compartilhado no Supabase elimina essa fragmentação: todo o
time lê/escreve o mesmo banco, sem sincronizar arquivo `.db` manualmente. As
duas razões acima (coleta incremental + análise com SQL) já valiam para o
SQLite; só a camada física mudou.

**Conexão via pooler, não conexão direta:** o host de conexão direta do
Supabase (`db.<ref>.supabase.co`) só resolve endereço IPv6, o que falha em
redes sem suporte a IPv6 (comum em redes domésticas/4G de alguns
integrantes). Por isso o `.env.example` aponta para o host do **Connection
Pooling** (`aws-0-<region>.pooler.supabase.com`, modo *Transaction*, porta
6543), não para o host de conexão direta.

**Por que `psycopg2` não viola a regra de "sem bibliotecas de terceiros":**
o enunciado proíbe bibliotecas de terceiros que **consultem a API do
GitHub** — a coleta em si usa só `urllib` (stdlib). O `psycopg2` fala com o
banco Postgres, não com a API do GitHub, então está fora dessa restrição.

## RQ01 — Idade do repositório

**Campo fonte:** `createdAt` (GraphQL, ISO 8601 UTC).

**Fórmula:**

```
idade_em_anos = (collected_at - created_at) / 365.25 dias
```

- **Referência de "hoje":** não é o momento em que a análise roda, e sim
  `collected_at`, o timestamp UTC (`now() AT TIME ZONE 'utc'` do Postgres)
  salvo em cada linha da tabela `repositories` no momento em que aquele
  repositório foi coletado. Isso garante que o cálculo de idade seja
  reproduzível mesmo que a
  coleta de S01 (100 repos) e a de S02 (1.000 repos) ocorram em dias
  diferentes — cada linha carrega sua própria referência temporal, em vez de
  depender da data em que um script de análise é executado depois.
- **365.25, não 365:** considera anos bissextos. Repositórios populares têm
  em geral vários anos de idade, então o erro acumulado de ignorar bissextos
  deixaria de ser desprezível.
- **Arredondamento:** exibição com 1 casa decimal; o valor bruto em dias fica
  disponível via `created_at`/`collected_at` para recomputar com outra
  precisão nas análises de S03, se necessário.
- **`collected_at` é atualizado a cada UPSERT, não só na primeira coleta
  (desde o commit `df34ff1`, issue #55):** antes, o campo ficava congelado no
  valor da primeira vez em que a linha era inserida; agora, toda vez que um
  repositório já existente é reprocessado (`ON CONFLICT DO UPDATE` em
  `storage.py`), `collected_at` é regravado com o timestamp atual. Isso
  corrige um bug (o campo nunca refletia recoletas), mas também significa que
  a "referência de hoje" de um repositório pode avançar entre S01 e S02 caso
  ele seja upsertado de novo — por exemplo se a página em que ele aparece for
  reprocessada, ou se a ordenação por estrelas do `search` do GitHub mudar
  no meio da paginação e o mesmo repositório aparecer em outro lote (risco já
  registrado na auditoria técnica de S01). Nesse caso a idade calculada para
  aquele repositório reflete o momento da recoleta, não da coleta original —
  `created_at` não muda, só a referência de "hoje" usada no cálculo. Não
  filtramos nem sinalizamos esses casos automaticamente; se a distribuição de
  idade parecer inconsistente entre S01 e S02 para um mesmo repositório, essa
  é a explicação mais provável a checar antes de suspeitar de erro de coleta.

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

## RQ03/RQ04 — Releases e última atualização

**Campo fonte de RQ03:** `releases_count` (GraphQL, `totalCount` da conexão
de releases).

**Campo fonte de RQ04:** `pushed_at` (GraphQL/REST, timestamp ISO 8601 UTC
do último push no repositório).

**Validação cruzada prevista/implementada:** o script
`app/src/validate_rq03_rq04.py` cruza os dados coletados com a REST API do
GitHub em uma amostra pequena (5–10 repositórios, via `--sample-size`).

- RQ03 confere `releases_count` contra `GET /repos/{owner}/{repo}/releases`,
  contando todos os itens paginados até o fim da listagem.
- RQ04 confere `pushed_at` salvo no banco contra o `pushed_at` retornado por
  `GET /repos/{owner}/{repo}`.

**Critério de comparação:** igualdade exata de string para `pushed_at` e
igualdade de contagem inteira para `releases_count`. Repositórios com `404`
na REST API são pulados e a amostra continua com os próximos candidatos, no
mesmo padrão dos validadores de RQ01/RQ02 e RQ05/RQ06.

**Amostragem cobre releases_count = 0 e > 0 (correção da auditoria de S01):**
`fetch_candidate_pool` busca separadamente um pool de repositórios com
`releases_count = 0` e outro com `releases_count > 0`, e intercala os dois
antes de aplicar `--sample-size`. Antes dessa correção, a consulta ordenava
tudo por `releases_count ASC`, então a amostra de 8 acabava sendo **100%
repositórios com 0 releases** — o que nunca provava que a contagem bate para
um valor diferente de zero. Ver `docs/validacao-rq03-rq04.md` para a tabela
atual, que já mistura os dois casos.

**Nota sobre divergências esperadas em `pushed_at`:** como a validação roda
em um momento posterior à coleta, é normal que `pushed_at` divirja da REST
API para repositórios ativos — o repositório pode ter recebido push entre a
coleta e a validação. Isso não é um erro de coleta; é o mesmo fenômeno de
defasagem temporal já documentado para `openIssues`/`closedIssues` na seção
de RQ05/RQ06 abaixo.

**Motivo metodológico:** essa validação fecha a base empírica da RQ07, que
agrega RQ02/RQ03/RQ04 por linguagem. Sem validar RQ03 e RQ04 isoladamente,
qualquer conclusão sobre diferenças por linguagem ficaria apoiada em campos
sem conferência cruzada própria.

## RQ05/RQ06 — Linguagem primária e issues fechadas

**Campo fonte de RQ05:** `primaryLanguage.name` (GraphQL). Comparado contra
`language` da REST API (`GET /repos/{owner}/{repo}`) — mesmo campo, sem
transformação, então a comparação é direta (igualdade de string ou `null`
dos dois lados).

**Fonte de referência para "linguagens mais populares" (exigida pelo
enunciado da RQ05):** **GitHub Octoverse** (octoverse.github.com), a mesma
citada no `README.md`. É a fonte usada, e mantida, em todo o laboratório
para responder "os sistemas populares estão nas linguagens mais populares?"
— ou seja, a linguagem primária de cada repositório coletado (`RQ05`) é
comparada contra o ranking de linguagens do Octoverse, não contra um ranking
derivado da própria amostra. Essa distinção importa em especial para a RQ07
(ver seção abaixo), que usa uma métrica de popularidade diferente por
motivos práticos.

**Campo fonte de RQ06:** `issues(states: OPEN) { totalCount }` e
`issues(states: CLOSED) { totalCount }` (GraphQL).

**Validação cruzada (`app/src/validate_rq05_rq06.py`):** ambos os lados de
RQ06 — issues abertas **e** fechadas — são conferidos contra a REST API,
paginando `GET /repos/{owner}/{repo}/issues?state=open` e
`?state=closed` até o fim da listagem e descartando itens que trazem a
chave `pull_request` (a REST API do GitHub mistura pull requests na
listagem de "issues" de um repositório).

**Por que não usar o campo `open_issues_count` do `GET /repos/{owner}/{repo}`
para conferir `openIssues`:** esse campo da REST API soma issues **e**
pull requests abertas em um único número — não é comparável a
`issues(states: OPEN).totalCount` do GraphQL, que conta só issues. Usar
esse campo direto produziria falsos negativos de validação em qualquer
repositório com PRs abertas (a maioria dos populares). Por isso o script
pagina `/issues?state=open` e aplica o mesmo filtro de exclusão de PRs já
usado do lado de `closedIssues` — mantendo os dois lados da RQ06 (aberto e
fechado) na mesma base de comparação "só issues".

**Nota sobre divergências esperadas na tabela de validação:** como a
validação roda em um momento posterior à coleta, é normal que `openIssues`/
`closedIssues` divirjam da REST API para repositórios ativos — issues
continuam sendo abertas/fechadas entre a coleta e a validação. Uma
divergência só é motivo de investigação se a **soma** (`open + closed`)
também mudar de forma inconsistente com "algumas issues fechadas entre a
coleta e a validação" (nesse caso o total se mantém constante, só migra de
aberta para fechada).

## RQ07 (bônus) — Linguagem vs. contribuição, releases e atualização

**Implementação:** `app/analysis/analyze_rq07.py`, gera
`docs/analise-rq07.md`. Agrupa os repositórios por `primary_language`,
calcula a mediana de PRs mergeadas (RQ02), releases (RQ03) e dias desde o
último push (RQ04) por linguagem, e mede a correlação de Spearman entre um
ranking de popularidade de linguagem e cada uma dessas três medianas.

**Métrica de popularidade usada aqui é diferente da fonte da RQ05, por
necessidade prática:** a RQ07 ranqueia as linguagens pelo **número de
repositórios da própria amostra coletada** que as usam como `primary_language`
(`repo_count`), e não pela posição da linguagem no ranking do GitHub
Octoverse (a fonte externa adotada para a RQ05 — ver seção acima). Motivo:
o Octoverse publica um ranking ordinal de linguagens, não um valor numérico
por linguagem que sirva de variável contínua para correlacionar com as
medianas de PRs/releases/atualização — usar só a posição no ranking (1º,
2º, 3º...) como proxy funcionaria de forma parecida, mas a contagem de
repositórios na amostra tem a vantagem adicional de já vir calculada dos
mesmos dados coletados, sem depender de mapear manualmente cada linguagem da
amostra para uma posição no Octoverse.

**Limitação que isso introduz:** "número de repositórios na amostra" mede
popularidade **dentro do universo já filtrado de repositórios populares**,
não popularidade da linguagem no ecossistema em geral — são conceitos
relacionados, mas não idênticos, e podem divergir do ranking do Octoverse
(ex.: uma linguagem pode ser muito usada em repositórios de alto destaque no
GitHub sem estar entre as mais populares do Octoverse, ou vice-versa). Por
isso o texto gerado em `docs/analise-rq07.md` chama a métrica explicitamente
de "proxy de popularidade", e o Relatório Final deve deixar claro, ao
apresentar a RQ07, que a definição de "popular" usada ali não é a mesma
fonte externa citada na RQ05 — para não parecer inconsistência não
intencional entre as duas seções do relatório.
