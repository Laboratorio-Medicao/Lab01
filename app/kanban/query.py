KANBAN_SNAPSHOT_QUERY = """
query KanbanSnapshot($org: String!, $projectNumber: Int!, $after: String) {
  rateLimit {
    remaining
    cost
    resetAt
  }
  organization(login: $org) {
    projectV2(number: $projectNumber) {
      items(first: 100, after: $after) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          fieldValues(first: 10) {
            nodes {
              ... on ProjectV2ItemFieldTextValue {
                text
                field { ... on ProjectV2Field { name } }
              }
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field { ... on ProjectV2SingleSelectField { name } }
              }
            }
          }
          content {
            ... on Issue {
              number
              title
              assignees(first: 5) { nodes { login } }
              labels(first: 10) { nodes { name } }
            }
          }
        }
      }
    }
  }
}
"""

MAX_ITEMS_PER_PAGE = 100


def build_variables(org, project_number, after=None):
    return {"org": org, "projectNumber": project_number, "after": after}
