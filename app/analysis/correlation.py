from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone

from src.metrics import compute_closed_issues_ratio, compute_fork_star_ratio

METRIC_NAMES = (
    "stargazer_count",
    "fork_count",
    "merged_pull_requests",
    "releases_count",
    "open_issues",
    "closed_issues",
    "is_fork",
    "is_archived",
    "idade_anos",
    "dias_desde_ultimo_push",
    "issues_total",
    "closed_issues_ratio",
    "fork_star_ratio",
)

METRIC_LABELS = {
    "stargazer_count": "Estrelas",
    "fork_count": "Forks",
    "merged_pull_requests": "PRs mergeadas",
    "releases_count": "Releases",
    "open_issues": "Issues abertas",
    "closed_issues": "Issues fechadas",
    "is_fork": "É fork",
    "is_archived": "Arquivado",
    "idade_anos": "Idade (anos)",
    "dias_desde_ultimo_push": "Dias desde último push",
    "issues_total": "Issues totais",
    "closed_issues_ratio": "Razão de issues fechadas",
    "fork_star_ratio": "Razão forks/estrelas",
}


@dataclass(frozen=True)
class CorrelationResult:
    metrics: tuple[str, ...]
    values: dict[str, list[float | None]]
    pearson: list[list[float | None]]
    spearman: list[list[float | None]]
    counts: list[list[int]]


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _date_metric(value: str | None, reference_date: datetime, divisor: float) -> float | None:
    if not value:
        return None
    try:
        delta = (reference_date - _parse_datetime(str(value))).total_seconds() / 86400
    except ValueError:
        return None
    if delta < 0:
        return None
    return delta / divisor


def build_metric_values(rows: list[dict], reference_date: datetime) -> dict[str, list[float | None]]:
    values = {metric: [] for metric in METRIC_NAMES}
    for row in rows:
        for metric in (
            "stargazer_count", "fork_count", "merged_pull_requests", "releases_count",
            "open_issues", "closed_issues", "is_fork", "is_archived",
        ):
            raw_value = row.get(metric)
            values[metric].append(float(raw_value) if raw_value is not None else None)

        age = _date_metric(row.get("created_at"), reference_date, 365.25)
        days = _date_metric(row.get("pushed_at"), reference_date, 1)
        values["idade_anos"].append(age)
        values["dias_desde_ultimo_push"].append(days)

        open_issues = row.get("open_issues")
        closed_issues = row.get("closed_issues")
        values["issues_total"].append(
            float(open_issues + closed_issues)
            if open_issues is not None and closed_issues is not None
            else None
        )
        values["closed_issues_ratio"].append(
            compute_closed_issues_ratio(open_issues, closed_issues)
            if open_issues is not None and closed_issues is not None
            else None
        )
        values["fork_star_ratio"].append(
            compute_fork_star_ratio(row.get("fork_count"), row.get("stargazer_count"))
        )
    return values


def _average_ranks(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(indexed):
        end = index + 1
        while end < len(indexed) and indexed[end][1] == indexed[index][1]:
            end += 1
        rank = (index + 1 + end) / 2
        for position in range(index, end):
            ranks[indexed[position][0]] = rank
        index = end
    return ranks


def _pearson(x_values: list[float], y_values: list[float]) -> float | None:
    if len(x_values) < 2:
        return None
    x_mean = statistics.fmean(x_values)
    y_mean = statistics.fmean(y_values)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
    x_sum = sum((x - x_mean) ** 2 for x in x_values)
    y_sum = sum((y - y_mean) ** 2 for y in y_values)
    denominator = math.sqrt(x_sum * y_sum)
    return numerator / denominator if denominator else None


def _pair_values(first: list[float | None], second: list[float | None]) -> tuple[list[float], list[float]]:
    pairs = [(x, y) for x, y in zip(first, second) if x is not None and y is not None]
    return [pair[0] for pair in pairs], [pair[1] for pair in pairs]


def compute_correlations(values: dict[str, list[float | None]]) -> CorrelationResult:
    metrics = tuple(values)
    pearson_matrix = []
    spearman_matrix = []
    counts = []
    for first_metric in metrics:
        pearson_row = []
        spearman_row = []
        count_row = []
        for second_metric in metrics:
            first, second = _pair_values(values[first_metric], values[second_metric])
            count_row.append(len(first))
            pearson_row.append(_pearson(first, second))
            if len(first) < 2:
                spearman_row.append(None)
            else:
                spearman_row.append(_pearson(_average_ranks(first), _average_ranks(second)))
        pearson_matrix.append(pearson_row)
        spearman_matrix.append(spearman_row)
        counts.append(count_row)
    return CorrelationResult(metrics, values, pearson_matrix, spearman_matrix, counts)


def correlation_pairs(result: CorrelationResult, method: str = "spearman") -> list[tuple[str, str, float, int]]:
    matrix = result.spearman if method == "spearman" else result.pearson
    pairs = []
    for first_index, first_metric in enumerate(result.metrics):
        for second_index in range(first_index + 1, len(result.metrics)):
            coefficient = matrix[first_index][second_index]
            if coefficient is not None:
                pairs.append((first_metric, result.metrics[second_index], coefficient, result.counts[first_index][second_index]))
    return sorted(pairs, key=lambda pair: abs(pair[2]), reverse=True)
