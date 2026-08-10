REPOSITORY_SEARCH_QUERY = """
query RepositorySearch($searchQuery: String!, $perPage: Int!, $after: String) {
  rateLimit {
    remaining
    cost
    resetAt
  }
  search(query: $searchQuery, type: REPOSITORY, first: $perPage, after: $after) {
    repositoryCount
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      ... on Repository {
        id
        name
        owner {
          login
        }
        stargazerCount
        createdAt
        pushedAt
        isFork
        isArchived
        primaryLanguage {
          name
        }
        mergedPullRequests: pullRequests(states: MERGED) {
          totalCount
        }
        releases {
          totalCount
        }
        openIssues: issues(states: OPEN) {
          totalCount
        }
        closedIssues: issues(states: CLOSED) {
          totalCount
        }
      }
    }
  }
}
"""

TOP_STARRED_REPOSITORIES_SEARCH_QUERY = "stars:>1 sort:stars-desc"

MAX_GITHUB_SEARCH_PAGE_SIZE = 100
