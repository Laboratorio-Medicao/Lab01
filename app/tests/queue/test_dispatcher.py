import pytest
from unittest.mock import Mock

from src.queue.dispatcher import JobDispatcher
from src.queue.types import Job, JobType


def test_dispatch_calls_correct_handler():
    handler = Mock()
    dispatcher = JobDispatcher({JobType.GRAPHQL_PAGINATION: handler})
    job = Job(type=JobType.GRAPHQL_PAGINATION, payload={})

    dispatcher.dispatch(job)

    handler.handle.assert_called_once_with(job)


def test_dispatch_raises_for_unregistered_type():
    dispatcher = JobDispatcher({})
    job = Job(type=JobType.GRAPHQL_PAGINATION, payload={})

    with pytest.raises(ValueError, match="graphql_pagination"):
        dispatcher.dispatch(job)


def test_dispatch_routes_to_correct_handler_among_multiple():
    graphql_handler = Mock()
    rest_handler = Mock()
    dispatcher = JobDispatcher(
        {
            JobType.GRAPHQL_PAGINATION: graphql_handler,
            JobType.REST_PAGINATION: rest_handler,
        }
    )
    job = Job(type=JobType.REST_PAGINATION, payload={})

    dispatcher.dispatch(job)

    rest_handler.handle.assert_called_once_with(job)
    graphql_handler.handle.assert_not_called()
