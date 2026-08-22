<h1 align="center">Relatório de Laboratório</h1>

| | |
|---|---|
| **Curso** | Engenharia de Software |
| **Disciplina** | Laboratório de Experimentação de Software |
| **Turno / Período** | Noite / 6º |
| **Professor(a)** | Danilo Maia |
| **Laboratório** | Lab01 — Características de Repositórios Populares + Setup do Kanban |
| **Grupo (trio)** | Arthur Luiz Alves Soares  · Guilherme de Almeida Rocha Vieira · Marcos Alberto Ferreira Pinto  |
| **Link do repositório / GitHub Projects** | https://github.com/Laboratorio-Medicao/Lab01 / https://github.com/orgs/Laboratorio-Medicao/projects/1 |
| **Data de entrega** | 28/08/2026 |

---

## 1. Introdução

Este laboratório investiga as principais características dos sistemas open-source mais populares hospedados no GitHub. A popularidade foi operacionalizada pelo número de estrelas (stars) de cada repositório — proxy amplamente utilizado na literatura de engenharia de software para medir relevância e adoção de projetos. A motivação é entender se repositórios com alta visibilidade compartilham padrões comuns de maturidade, contribuição externa, frequência de releases, atualização e escolha de linguagem.

Foram coletados os **1.000 repositórios com maior número de estrelas no GitHub** via API GraphQL, com coleta realizada em agosto de 2026. O estudo responde às seguintes questões de pesquisa:

- **RQ01.** Sistemas populares são maduros/antigos? *(métrica: idade do repositório a partir da data de criação)*
- **RQ02.** Sistemas populares recebem muita contribuição externa? *(métrica: total de pull requests aceitas)*
- **RQ03.** Sistemas populares lançam releases com frequência? *(métrica: total de releases)*
- **RQ04.** Sistemas populares são atualizados com frequência? *(métrica: tempo desde a última atualização)*
- **RQ05.** Sistemas populares são escritos nas linguagens mais populares? *(métrica: linguagem primária de cada repositório, comparada ao TIOBE Index de agosto de 2026)*
- **RQ06.** Sistemas populares possuem um alto percentual de issues fechadas? *(métrica: razão entre issues fechadas e total de issues)*
- **RQ07.** Sistemas escritos em linguagens mais populares recebem mais contribuição externa, lançam mais releases e são atualizados com mais frequência? *(métrica: RQ02, RQ03 e RQ04 agrupados por linguagem primária)*

Como inovação própria (30%), o grupo propôs a **RQ08**, que mede a razão forks/estrelas como proxy de engajamento real versus popularidade passiva, e implementou uma **arquitetura de coleta tolerante a falhas** via fila de jobs com RabbitMQ — detalhes na seção 3.6.

### Hipóteses Informais

#### RQ01 — Maturidade dos repositórios

**Hipótese:** a maior parte dos repositórios populares acumula estrelas ao longo de vários anos — a mediana de idade deve ficar acima de 3 anos. Haverá uma cauda de repositórios jovens (< 1,5 anos) associada principalmente ao fenômeno de star-farming e ao hype de IA/agentes observado em 2025–2026, mas essa cauda não deve representar a maioria da amostra.

**Justificativa:** popularidade orgânica é um processo cumulativo; picos de crescimento rápido em poucos meses são exceção, não regra, mesmo entre os repositórios mais estrelados do GitHub.

#### RQ02 — Contribuição externa

**Hipótese:** a distribuição de pull requests aceitas deve ser fortemente assimétrica à direita — a maioria dos repositórios terá uma contagem relativamente baixa de PRs mergeadas, com uma cauda de outliers formada por projetos de infraestrutura madura (linguagens, frameworks, ferramentas de uso massivo).

**Justificativa:** contribuição via pull request depende de uma comunidade ativa de terceiros, que só se forma depois de o projeto ser amplamente conhecido e adotado.

#### RQ03 — Frequência de releases

**Hipótese:** a maioria dos repositórios populares deve ter um número moderado de releases, com outliers de projetos que adotam versionamento semântico rigoroso. Projetos de documentação, listas curadas e materiais de aprendizado devem puxar a mediana para baixo, por não seguirem o ciclo de release convencional.

**Justificativa:** o total de releases depende tanto da maturidade do projeto quanto da política de versionamento adotada — um projeto maduro com entrega contínua pode ter zero releases formais no GitHub, enquanto um projeto jovem com versionamento semântico estrito pode ter dezenas.

#### RQ04 — Frequência de atualização

**Hipótese:** a maioria dos repositórios populares deve ter sido atualizada recentemente (mediana de dias desde o último push abaixo de 30 dias). Porém, uma parcela de repositórios históricos — projetos concluídos, arquivados ou de referência estática — deve apresentar longos períodos sem atividade, formando a cauda da distribuição.

**Justificativa:** sistemas com alta popularidade tendem a atrair usuários que reportam bugs e sugerem melhorias, o que mantém os mantenedores ativos. Exceções naturais são projetos considerados "completos" ou repositórios de conteúdo estático.

#### RQ05 — Linguagens mais populares

**Hipótese:** Python e JavaScript devem ocupar as primeiras posições da distribuição. C e C++ devem aparecer em seguida, puxados por projetos de sistemas com grande base de estrelas acumulada. A maioria das linguagens com representação expressiva na amostra deve coincidir com o top 20 do TIOBE Index. A principal exceção esperada é TypeScript, que tem forte presença no GitHub mas não aparece no top 20 do TIOBE.

**Fonte de referência:** TIOBE Index, agosto de 2026 — https://www.tiobe.com/tiobe-index/

**Justificativa:** o TIOBE mede popularidade com base em buscas globais; linguagens com maior adoção tendem a dominar tanto as buscas quanto os repositórios mais populares do GitHub. TypeScript é uma exceção estrutural por ser um superset de JavaScript voltado especificamente para projetos de médio/grande porte.

#### RQ06 — Percentual de issues fechadas

**Hipótese:** a mediana da razão `closed_issues / total_issues` deve ficar acima de 0,5, com distribuição assimétrica à esquerda — concentrada perto de 1,0 — e uma cauda de projetos muito ativos onde a taxa de abertura de novas issues supera a de fechamento.

**Justificativa:** projetos open-source populares costumam ter mantenedores ativos que fecham issues regularmente. À medida que o projeto cresce, o volume de issues abertas tende a crescer mais rápido do que a capacidade de resolução, especialmente em projetos sem equipe dedicada de suporte.

#### RQ07 — Linguagem vs. contribuição, releases e atualização

**Hipótese:** linguagens mais populares não devem apresentar correlação forte e consistente com todas as métricas de RQ02, RQ03 e RQ04 simultaneamente. É esperada correlação moderada com PRs mergeadas, mas correlação fraca com releases e atualização, pois essas métricas dependem mais da política interna de cada projeto do que da linguagem usada.

**Justificativa:** a popularidade da linguagem influencia o tamanho potencial da comunidade de contribuidores (RQ02), mas não determina a frequência de releases (RQ03) nem a atividade de push (RQ04), que são decisões de governança do projeto.

#### RQ08 — Engajamento real (bônus)

**Hipótese:** repositórios no grupo suspeito de star-farming (idade < 1,5 anos e mais de 100 mil estrelas) devem ter `fork_star_ratio` (fork_count / stargazer_count) sistematicamente mais baixo que o resto da amostra — estrelas compradas/automatizadas não se traduzem em forks, enquanto adoção orgânica gera ambos proporcionalmente.

**Justificativa:** forks exigem uma ação deliberada de quem pretende usar, estudar ou contribuir com o código — um sinal de engajamento ativo bem mais custoso de forjar em massa do que uma estrela, que é um clique único sem intenção necessária de uso.

---

## 2. Contexto

Este é o Lab01 da disciplina, primeiro da sequência de cinco laboratórios do semestre. O board Kanban criado aqui será mantido e utilizado como objeto de estudo nos Labs 04 e 05; os snapshots exportados ao final de cada sprint constituirão a série histórica de dados para esses laboratórios futuros.

O objeto de estudo é o conjunto dos **1.000 repositórios com maior número de estrelas no GitHub** em agosto de 2026 — um recorte que captura sistemas de diferentes domínios, idades e linguagens, unificados pelo critério de alta visibilidade na plataforma.

Como referência para "linguagens de programação mais populares" (RQ05), o grupo adotou o **TIOBE Index** (tiobe.com/tiobe-index), edição de agosto de 2026, mantendo esta fonte como única referência ao longo de todo o laboratório.

---

## 3. Metodologia

### 3.1 Principais Desafios

**Rate limit da API GraphQL do GitHub:** a coleta de 1.000 repositórios em lotes de 25 por requisição está sujeita ao limite de taxa da API. Quando o limite é atingido, a coleta precisa ser pausada até a janela de reset — sem persistência de estado, qualquer interrupção obrigaria recomeçar do zero.

**Limite hard de 1.000 resultados por query de busca:** a API de Search do GitHub (GraphQL e REST) não retorna mais de 1.000 resultados por query, independente de paginação. Isso define o tamanho máximo da amostra com a estratégia atual de coleta — para amostras maiores, seria necessário quebrar a busca em múltiplas queries com filtros diferentes.

**Star-farming e repositórios jovens com muitas estrelas:** 21 repositórios da amostra (2,1%) têm menos de 1,5 anos de idade e mais de 100 mil estrelas — padrão documentado na comunidade do GitHub como característico de star-farming/fake stars em 2025–2026. Esses repositórios afetam diretamente a RQ01 e precisam ser discutidos explicitamente na análise de resultados.

**Divergências temporais na validação cruzada:** como a validação contra a REST API ocorre em momento posterior à coleta, campos como `pushed_at` e contagens de issues podem divergir para repositórios ativos — não por erro de coleta, mas por atividade ocorrida entre os dois momentos.

### 3.2 Tomadas de Decisão

**PostgreSQL (Supabase) em vez de SQLite/CSV:** garantiu coleta incremental retomável (cursor e total coletado salvos em tabela `collection_state`) e agregação por linguagem via SQL para a RQ07. Cada integrante acessa o mesmo banco, eliminando a fragmentação de dados entre máquinas locais.

**Fila de jobs com RabbitMQ:** cada página coletada é processada por um job consumido do RabbitMQ, que ao final enfileira o próximo job. Isso desacopla produção de consumo e torna a coleta tolerante a interrupções e rate limits — quando o limite é atingido, o consumer aguarda e retoma sem perda de estado.

**TIOBE Index como referência para RQ05:** escolhido por medir popularidade com base em buscas globais (metodologia pública e auditável), com edição mensal que permite replicar o estudo com a mesma referência temporal. A edição de agosto de 2026 foi fixada como referência única ao longo de todo o laboratório.

**Não filtrar forks nem repositórios arquivados:** os campos `isFork` e `isArchived` foram coletados para rastreabilidade, mas nenhum filtro foi aplicado na seleção — na amostra, 0% dos repositórios são forks e 0% são arquivados, então a decisão não teve impacto prático nesta sprint.

**Não filtrar repositórios suspeitos de star-farming:** não há critério objetivo e barato (sem ferramentas de terceiros proibidas pelo enunciado) para separar tração orgânica de estrelas compradas. O achado é documentado e discutido na análise de resultados, sem remover dados da amostra.

### 3.3 Etapas

**S01 — Infraestrutura e Coleta Inicial**

| Issue | Título | Responsável |
|---|---|---|
| #10 | Setup do projeto e client GraphQL | Marcos Alberto |
| #11 | Query e validação RQ01 e RQ02 | Marcos Alberto |
| #12 | Validação RQ03 e RQ04 | Arthur Soares |
| #13 | Validação RQ05, RQ06 | Guilherme Vieira |
| #27 | Script de export do Kanban (Projects v2) | Guilherme Vieira |
| #49 | Análise RQ07 (bônus): métricas por linguagem | Guilherme Vieira |
| #55 | Correção da validação RQ06, refresh de dados e fix de collected_at | Marcos Alberto |

**S02 — Paginação, CSV e Hipóteses**

| Issue | Título | Responsável |
|---|---|---|
| #22 | Export Postgres para CSV | Marcos Alberto |
| #23 | Análise exploratória e hipóteses RQ01 e RQ02 | Marcos Alberto |
| #24 | Script de validação e hipóteses RQ03 e RQ04 | Arthur Soares |
| #25 | Script de validação e hipóteses RQ05, RQ06 e RQ07 | Guilherme Vieira |
| #26 | Paginação para 1000 repositórios | Arthur Soares |
| #28 | Gerar snapshot S02 do Kanban | Guilherme Vieira |
| #38 | Relatório: introdução, hipóteses e metodologia de coleta | Guilherme Vieira |
| #44 | Fila de requisições para controle de rate limit | Guilherme Vieira |
| #58 | RQ08 (bônus): coleta de fork_count, métrica fork_star_ratio e validação cruzada | Marcos Alberto |

**S03 — Análise, Visualização e Dashboard** *(em andamento)*

| Issue | Título | Responsável |
|---|---|---|
| #31 | Análise e visualização RQ01 e RQ02 | Marcos Alberto |
| #32 | Análise e visualização RQ03 e RQ04 | Arthur Soares |
| #33 | Análise e visualização RQ05, RQ06 e RQ07 (bônus) | Guilherme Vieira |
| #34 | Matriz de correlação entre métricas | — |
| #35 | Dashboard interativo HTML | — |
| #39 | Relatório — Resultados e discussão RQ01 e RQ02 | Marcos Alberto |
| #40 | Relatório — Resultados e discussão RQ03 e RQ04 | Arthur Soares |
| #41 | Relatório — Resultados e discussão RQ05, RQ06 e RQ07 | — |
| #42 | Relatório — Seção de configuração do processo | — |
| #43 | Relatório — Revisão final e exportação PDF | — |

**Configuração do processo — GitHub Projects:**

- **Colunas (Status):** Backlog → To Do → Doing → Review → Done
- **Limite de WIP (Doing):** [preencher — valor e justificativa]
- **Print do board:** [inserir captura de tela ao final do laboratório]

### 3.4 Ferramentas

| Ferramenta | Uso |
|---|---|
| **Python 3.9** (stdlib: `urllib`, `json`) | Script de coleta GraphQL e REST — sem bibliotecas de terceiros para acesso à API |
| **psycopg2** | Conexão com PostgreSQL (não acessa API do GitHub — fora da restrição do enunciado) |
| **pika** | Client RabbitMQ para o sistema de fila de jobs |
| **PostgreSQL / Supabase** | Armazenamento compartilhado dos dados coletados |
| **RabbitMQ** | Fila de jobs para coleta incremental tolerante a falhas |
| **pytest** | Testes unitários e de integração |
| **GitHub GraphQL API** | Coleta dos campos de cada repositório |
| **GitHub REST API** | Validação cruzada dos dados coletados |
| **GitHub Projects (v2)** | Gestão do processo — link: [preencher] |

### 3.5 Tabela de Métricas

| RQ | Métrica | Definição Operacional | Unidade | Ferramenta / Fonte |
|---|---|---|---|---|
| RQ01 | Idade do repositório | `(collected_at − createdAt) / 365,25` | Anos | GraphQL `Repository.createdAt` |
| RQ02 | Pull requests aceitas | `pullRequests(states: MERGED).totalCount` | Contagem | GraphQL `Repository.pullRequests` |
| RQ03 | Total de releases | `releases.totalCount` | Contagem | GraphQL `Repository.releases` |
| RQ04 | Tempo desde última atualização | `data de análise − pushedAt` | Dias | GraphQL `Repository.pushedAt` |
| RQ05 | Linguagem primária | `primaryLanguage.name`; comparada ao top 20 do TIOBE Index (ago/2026) | Categoria | GraphQL `Repository.primaryLanguage` |
| RQ06 | Razão de issues fechadas | `closedIssues / (openIssues + closedIssues)`; indefinida quando total = 0 | Razão [0,1] | GraphQL `issues(states: OPEN/CLOSED).totalCount` |
| RQ07 | Métricas de RQ02/03/04 por linguagem | Mediana de cada métrica agrupada por `primary_language`; correlação de Spearman entre rank de popularidade e cada mediana | Mediana + ρ | Banco de dados (SQL `GROUP BY`) |
| RQ08 (bônus) | Razão forks/estrelas | `forkCount / stargazerCount`; indefinida quando `stargazerCount = 0` | Razão [0, +∞) | GraphQL `Repository.forkCount` |

### 3.6 Inovações Propostas pelo Grupo (30%)

**RQ08 — Razão forks/estrelas como proxy de engajamento real**

O grupo propôs uma métrica adicional não solicitada pelo enunciado: `fork_count / stargazer_count`, que diferencia popularidade passiva (estrelas — sinal de interesse) de engajamento ativo (forks — sinal de uso e intenção de contribuição). A hipótese é que repositórios suspeitos de star-farming apresentem razão forks/estrelas sistematicamente mais baixa do que o restante da amostra, pois estrelas compradas/automatizadas não geram forks orgânicos. O campo `forkCount` já estava disponível no mesmo nó GraphQL das demais RQs, sem custo adicional de coleta. A análise desta métrica sobre os 1.000 repositórios está prevista para S03.

**Arquitetura de coleta tolerante a falhas com RabbitMQ**

Em vez de um script de coleta sequencial com `time.sleep` em caso de rate limit, o grupo implementou um sistema de fila de jobs com RabbitMQ (`app/src/queue/`): um producer publica o job inicial; cada consumer processa uma página, persiste os dados e enfileira o próximo job. Isso torna a coleta retomável após falhas ou rate limits sem reprocessar dados já salvos, e desacopla a lógica de paginação da lógica de persistência.

---

## 4. Resultados

Os valores abaixo cobrem a amostra completa de 1.000 repositórios (coleta de S02, sem valores ausentes em nenhuma das métricas desta seção). As visualizações interativas (histogramas, box plots e gráficos de dispersão) referenciadas em cada RQ foram geradas em S03 e estão disponíveis nos arquivos HTML indicados.

### 4.1 RQ01 — Idade do repositório

| Métrica | Valor |
|---|---|
| N | 1000 |
| Mínimo | 0,00 anos |
| 1º quartil | 3,50 anos |
| **Mediana** | **7,70 anos** |
| Média | 7,65 anos |
| 3º quartil | 11,33 anos |
| Máximo | 18,40 anos |
| Outliers (regra IQR 1,5×) | 0 |

**Achado de star-farming:** 21 dos 1.000 repositórios (2,1%) têm idade < 1,5 anos e mais de 100 mil estrelas — liderados por `openclaw/openclaw` (386.403⭐, 0,70 anos) e outros projetos ligados ao hype recente de agentes de IA.

**Visualização:** `docs/report-rq01-rq02.html` — histograma de idade, box plot, e dispersão idade × estrelas com destaque para o grupo de star-farming.

**Discussão hipótese vs. resultado:** a hipótese **se confirma**. A mediana observada (7,70 anos) fica bem acima do limiar de 3 anos previsto, confirmando que a popularidade da maioria dos repositórios é fruto de acúmulo orgânico ao longo de vários anos, não de picos recentes. A cauda de repositórios jovens existe como esperado, mas é pequena (2,1%) e concentrada no fenômeno de star-farming/hype de IA já antecipado na hipótese. Um ponto que **diverge** da expectativa inicial é a magnitude dessa cauda: em S01 (amostra de 100), o mesmo padrão aparecia em 16% dos casos — quase 8× a proporção observada na amostra completa. A leitura mais provável é viés de amostra pequena: o corte "top 100" tende a capturar desproporcionalmente os repositórios em ascensão mais recente e virótica, enquanto o "top 1.000" dilui esse efeito com projetos de cauda mais longa e histórico mais consolidado.

### 4.2 RQ02 — Pull requests aceitas

| Métrica | Valor |
|---|---|
| N | 1000 |
| Mínimo | 0 |
| 1º quartil | 175 |
| **Mediana** | **768** |
| Média | 4.212,96 |
| 3º quartil | 3.391,25 |
| Máximo | 103.167 |
| Outliers altos (regra IQR 1,5×) | 123 |

**Top outliers:** `firstcontributions/first-contributions` (103.167), `llvm/llvm-project` (96.690), `elastic/elasticsearch` (95.345), `getsentry/sentry` (91.101), `home-assistant/core` (90.011), `rust-lang/rust` (73.490), `kubernetes/kubernetes` (65.646), `python/cpython` (62.610), entre outros.

**Visualização:** `docs/report-rq01-rq02.html` — histograma em escala log10 (dada a forte assimetria) e box plot em escala linear.

**Discussão hipótese vs. resultado:** a hipótese **se confirma**. A distância entre mediana (768) e média (4.212,96) já denuncia a forte assimetria à direita prevista, e os 123 outliers altos são majoritariamente projetos de infraestrutura madura com grande base de contribuidores externos (compiladores, bancos de dados, kernels de sistemas, frameworks de uso massivo) — exatamente o perfil antecipado na hipótese. Uma exceção interessante que a hipótese não previu é o outlier máximo, `firstcontributions/first-contributions`: não é um projeto de infraestrutura, mas um repositório criado especificamente como exercício de primeira contribuição em código aberto — sua função é gerar PRs em alto volume, o que infla a métrica por um motivo estrutural diferente do "engajamento de comunidade madura" hipotetizado para os demais outliers.

### 4.3 RQ08 — Engajamento real: razão forks/estrelas (bônus)

| Métrica | Valor |
|---|---|
| N | 1000 |
| Mínimo | 0,0009 |
| 1º quartil | 0,0772 |
| **Mediana** | **0,1144** |
| Média | 0,1458 |
| 3º quartil | 0,1798 |
| Máximo | 1,9449 |
| Outliers altos (regra IQR 1,5×) | 53 |

**Comparação star-farming vs. resto da amostra:**

| Grupo | N | Mediana de `fork_star_ratio` |
|---|---|---|
| Star-farming (idade < 1,5a, > 100 mil⭐) | 21 | 0,1190 |
| Resto da amostra | 979 | 0,1144 |

**Visualização:** `docs/report-rq08.html` — histograma, box plot, e box plot comparativo entre o grupo de star-farming e o resto da amostra.

**Discussão hipótese vs. resultado:** a hipótese **não se confirma**. Esperava-se que o grupo suspeito de star-farming apresentasse `fork_star_ratio` sistematicamente mais baixo — sinal de que estrelas artificiais não geram forks proporcionais —, mas a mediana observada nesse grupo (0,1190) é, na verdade, igual ou ligeiramente **maior** que a do resto da amostra (0,1144). Isso não invalida o achado de star-farming em si (RQ01), que se apoia em critério independente (idade × estrelas), mas indica que `fork_star_ratio` sozinho não é um discriminador forte para esse grupo específico. Uma leitura possível é que parte dos repositórios nesse grupo (ligados ao hype de agentes de IA) atrai também curiosidade genuína — testes, estudo de código, tentativas de uso — que se traduz em forks reais, mesmo quando uma fração das estrelas não é orgânica; ou que o N pequeno (21 repositórios) torna a mediana desse grupo sensível a poucos casos extremos.

### 4.4 RQ03 — Frequência de releases

*[a preencher em #40 — Arthur Soares]*

### 4.5 RQ04 — Frequência de atualização

*[a preencher em #40 — Arthur Soares]*

### 4.6 RQ05 — Linguagens mais populares

*[a preencher em #41]*

### 4.7 RQ06 — Percentual de issues fechadas

*[a preencher em #41]*

### 4.8 RQ07 — Linguagem vs. contribuição, releases e atualização (bônus)

*[a preencher em #41]*

---

## 5. Conclusão

*[a preencher no Relatório Final]*

---

## 6. Referências

ZUSE, Horst. *A framework of software measurement*. Walter de Gruyter, 2013.

TIOBE Software. **TIOBE Index for August 2026**. Disponível em: https://www.tiobe.com/tiobe-index/. Acesso em: ago. 2026.
