from datetime import datetime, timezone

DAYS_PER_YEAR = 365.25


def _parse_iso8601(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_collected_at(collected_at):
    return datetime.strptime(collected_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def _years_since(reference_iso8601, collected_at):
    reference = _parse_iso8601(reference_iso8601)
    collected = _parse_collected_at(collected_at)
    days = (collected - reference).total_seconds() / 86400
    return round(days / DAYS_PER_YEAR, 1)


def compute_age_years(created_at, collected_at):
    """RQ01 — idade do repositório, em anos, a partir de createdAt até collected_at."""
    return _years_since(created_at, collected_at)


def compute_update_recency_years(pushed_at, collected_at):
    """RQ04 — tempo desde a última atualização (pushedAt), em anos, até collected_at.

    Mesma unidade de RQ01 (anos), conforme recomendação de consistência da
    fonte da verdade (seção 4, RQ04).
    """
    return _years_since(pushed_at, collected_at)


def compute_closed_issues_ratio(open_issues, closed_issues):
    """RQ06 — razão entre issues fechadas e total de issues (open + closed).

    Retorna `None` quando `total = 0` (repositório sem nenhuma issue), em vez
    de levantar `ZeroDivisionError` — não existe percentual de "fechadas"
    definido quando não há issues, então o valor ausente é registrado
    explicitamente como `None` (fonte da verdade, seção 4, RQ06).
    """
    total = open_issues + closed_issues
    if total == 0:
        return None
    return round(closed_issues / total, 4)
