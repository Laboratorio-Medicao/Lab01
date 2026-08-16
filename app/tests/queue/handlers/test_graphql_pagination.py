from unittest.mock import Mock, patch

import pytest

from src.errors import RateLimitReached
from src.queue.handlers.graphql_pagination import GraphQLPaginationHandler
from src.queue.types import Job, JobType

PAYLOAD = {"target_total": 10, "per_page": 5}


def make_handler():
    client = Mock()
    publisher = Mock()
    return GraphQLPaginationHandler(client, publisher), client, publisher


def test_handler_publishes_next_job_after_successful_page(monkeypatch):
    handler, client, publisher = make_handler()
    job = Job(type=JobType.GRAPHQL_PAGINATION, payload=PAYLOAD)

    states = [{"cursor": None, "total_collected": 0}, {"cursor": "c1", "total_collected": 5}]
    state_iter = iter(states)

    with patch("src.queue.handlers.graphql_pagination.get_connection"), \
         patch("src.queue.handlers.graphql_pagination.get_collection_state", side_effect=lambda _: next(state_iter)), \
         patch("src.queue.handlers.graphql_pagination.collect_page"):
        handler.handle(job)

    publisher.publish.assert_called_once()
    next_job = publisher.publish.call_args.args[0]
    assert next_job.type == JobType.GRAPHQL_PAGINATION
    assert next_job.payload == PAYLOAD


def test_handler_does_not_publish_when_target_already_met(monkeypatch):
    handler, client, publisher = make_handler()
    job = Job(type=JobType.GRAPHQL_PAGINATION, payload=PAYLOAD)

    with patch("src.queue.handlers.graphql_pagination.get_connection"), \
         patch("src.queue.handlers.graphql_pagination.get_collection_state",
               return_value={"cursor": "c1", "total_collected": 10}):
        handler.handle(job)

    publisher.publish.assert_not_called()


def test_handler_propagates_rate_limit_reached(monkeypatch):
    handler, client, publisher = make_handler()
    job = Job(type=JobType.GRAPHQL_PAGINATION, payload=PAYLOAD)

    with patch("src.queue.handlers.graphql_pagination.get_connection"), \
         patch("src.queue.handlers.graphql_pagination.get_collection_state",
               return_value={"cursor": None, "total_collected": 0}), \
         patch("src.queue.handlers.graphql_pagination.collect_page",
               side_effect=RateLimitReached(reset_at="2099-01-01T00:00:00Z", remaining=0)):
        with pytest.raises(RateLimitReached):
            handler.handle(job)

    publisher.publish.assert_not_called()


def test_handler_does_not_publish_next_when_page_collection_hits_target(monkeypatch):
    handler, client, publisher = make_handler()
    job = Job(type=JobType.GRAPHQL_PAGINATION, payload=PAYLOAD)

    states = [{"cursor": None, "total_collected": 5}, {"cursor": "c1", "total_collected": 10}]
    state_iter = iter(states)

    with patch("src.queue.handlers.graphql_pagination.get_connection"), \
         patch("src.queue.handlers.graphql_pagination.get_collection_state",
               side_effect=lambda _: next(state_iter)), \
         patch("src.queue.handlers.graphql_pagination.collect_page"):
        handler.handle(job)

    publisher.publish.assert_not_called()
