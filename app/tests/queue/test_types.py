import pytest
from src.queue.types import Job, JobType


def test_job_type_values():
    assert JobType.GRAPHQL_PAGINATION.value == "graphql_pagination"
    assert JobType.REST_PAGINATION.value == "rest_pagination"


def test_job_roundtrip_serialization():
    job = Job(
        type=JobType.GRAPHQL_PAGINATION,
        payload={"target_total": 1000, "per_page": 25},
        attempt=2,
    )
    restored = Job.from_bytes(job.to_bytes())

    assert restored.type == JobType.GRAPHQL_PAGINATION
    assert restored.payload == {"target_total": 1000, "per_page": 25}
    assert restored.attempt == 2


def test_job_default_attempt_is_zero():
    job = Job(type=JobType.REST_PAGINATION, payload={})
    assert job.attempt == 0


def test_job_from_bytes_raises_on_unknown_type():
    import json
    raw = json.dumps({"type": "unknown_type", "payload": {}, "attempt": 0}).encode()
    with pytest.raises(ValueError):
        Job.from_bytes(raw)
