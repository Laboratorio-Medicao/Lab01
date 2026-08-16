from unittest.mock import Mock

import pytest

from src.errors import RateLimitReached
from src.queue.consumer import JobConsumer
from src.queue.types import Job, JobType


def make_consumer(dispatcher=None, publisher=None):
    channel = Mock()
    dispatcher = dispatcher or Mock()
    publisher = publisher or Mock()
    return JobConsumer(channel, dispatcher, publisher), channel


def make_method(delivery_tag=1):
    method = Mock()
    method.delivery_tag = delivery_tag
    return method


def test_consumer_acks_on_successful_dispatch():
    consumer, channel = make_consumer()
    job = Job(type=JobType.GRAPHQL_PAGINATION, payload={})

    consumer._on_message(channel, make_method(), None, job.to_bytes())

    channel.basic_ack.assert_called_once_with(delivery_tag=1)
    channel.basic_nack.assert_not_called()


def test_consumer_requeues_with_delay_on_rate_limit():
    publisher = Mock()
    dispatcher = Mock()
    dispatcher.dispatch.side_effect = RateLimitReached(
        reset_at="2000-01-01T00:00:00Z", remaining=0
    )
    consumer, channel = make_consumer(dispatcher=dispatcher, publisher=publisher)
    job = Job(type=JobType.GRAPHQL_PAGINATION, payload={"target_total": 1000})

    consumer._on_message(channel, make_method(), None, job.to_bytes())

    publisher.publish.assert_called_once()
    published_job = publisher.publish.call_args.args[0]
    kwargs = publisher.publish.call_args.kwargs
    assert published_job.attempt == 1
    assert published_job.type == JobType.GRAPHQL_PAGINATION
    assert "delay_ms" in kwargs
    channel.basic_ack.assert_called_once_with(delivery_tag=1)
    channel.basic_nack.assert_not_called()


def test_consumer_nacks_without_requeue_on_unexpected_error():
    dispatcher = Mock()
    dispatcher.dispatch.side_effect = RuntimeError("boom inesperado")
    consumer, channel = make_consumer(dispatcher=dispatcher)
    job = Job(type=JobType.GRAPHQL_PAGINATION, payload={})

    consumer._on_message(channel, make_method(), None, job.to_bytes())

    channel.basic_nack.assert_called_once_with(delivery_tag=1, requeue=False)
    channel.basic_ack.assert_not_called()


def test_consumer_increments_attempt_on_rate_limit_retry():
    publisher = Mock()
    dispatcher = Mock()
    dispatcher.dispatch.side_effect = RateLimitReached(
        reset_at="2000-01-01T00:00:00Z", remaining=0
    )
    consumer, channel = make_consumer(dispatcher=dispatcher, publisher=publisher)
    job = Job(type=JobType.GRAPHQL_PAGINATION, payload={}, attempt=3)

    consumer._on_message(channel, make_method(), None, job.to_bytes())

    published_job = publisher.publish.call_args.args[0]
    assert published_job.attempt == 4
