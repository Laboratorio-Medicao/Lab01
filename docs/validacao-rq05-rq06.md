| Repositório | `primaryLanguage` (query) | `language` (REST) | `openIssues` (query) | `open_issues_count` (REST) | `closedIssues` (query) | issues fechadas (REST) | Zero issues? | Linguagem bate? | Issues batem? |
|---|---|---|---|---|---|---|---|---|---|
| vinta/awesome-python | Python | Python | 0 | 23 | 0 | 0 | ⚠️ sim | ✅ | ✅ |
| yangshun/tech-interview-handbook | TypeScript | TypeScript | 34 | 34 | 92 | 92 | não | ✅ | ✅ |
| msitarzewski/agency-agents | Shell | Shell | 51 | 111 | 87 | 87 | não | ✅ | ✅ |
| Shubhamsaboo/awesome-llm-apps | Python | Python | 3 | 10 | 167 | 166 | não | ✅ | ❌ |
| f/prompts.chat | HTML | HTML | 20 | 64 | 152 | 152 | não | ✅ | ✅ |
| nextlevelbuilder/ui-ux-pro-max-skill | Python | Python | 54 | 118 | 118 | 118 | não | ✅ | ✅ |
| x1xhlol/system-prompts-and-models-of-ai-tools | null | null | 91 | 158 | 120 | 120 | não | ✅ | ✅ |
| practical-tutorials/project-based-learning | Python | Python | 151 | 267 | 88 | 88 | não | ✅ | ✅ |

## RQ07 (bônus) — por que não há tabela própria de validação

RQ07 pergunta se repositórios em linguagens mais populares recebem mais
contribuição externa, lançam mais releases e são atualizados com mais
frequência — ou seja, cruza os resultados de RQ02 (`merged_pull_requests`),
RQ03 (`releases_count`) e RQ04 (`pushed_at`), agrupados pela linguagem
primária de cada repositório (RQ05, `primary_language`).

**Não há campo adicional a coletar ou validar para RQ07.** A métrica é uma
agregação (`GROUP BY primary_language`) sobre colunas que já têm validação
cruzada própria:

- `primary_language` → validado nesta mesma tabela (colunas "Linguagem
  bate?").
- `merged_pull_requests` → validado em
  [`docs/validacao-rq01-rq02.md`](./validacao-rq01-rq02.md) (RQ02).
- `releases_count` e `pushed_at` (RQ03/RQ04) → ainda sem tabela de validação
  cruzada própria nesta sprint; ver observação abaixo.

Se `primary_language` e `merged_pull_requests` já batem individualmente
contra a REST API, o agrupamento por linguagem (RQ07) herda essa garantia —
não há transformação adicional que possa introduzir divergência.

**Pendência:** `releases_count` (RQ03) e `pushed_at` (RQ04) ainda não têm uma
validação cruzada própria documentada (nem aqui, nem em
`docs/validacao-rq01-rq02.md`). Como RQ07 depende desses dois campos, o ideal
é fechar essa lacuna — mesmo que com uma amostra pequena, no mesmo padrão
usado para RQ01/RQ02/RQ05/RQ06 — antes de tratar RQ07 como validado.
