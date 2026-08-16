import pika
from unittest.mock import Mock

from src.queue.publisher import JobPublisher
from src.queue.types import Job, JobType


def test_publish_without_delay_uses_empty_headers():
    channel = Mock()
    publisher = JobPublisher(channel)
    job = Job(type=JobType.GRAPHQL_PAGINATION, payload={"target_total": 100})

    publisher.publish(job)

    channel.basic_publish.assert_called_once()
    props = channel.basic_publish.call_args.kwargs["properties"]
    assert props.headers == {}


def test_publish_with_delay_sets_x_delay_header():
    channel = Mock()
    publisher = JobPublisher(channel)
    job = Job(type=JobType.GRAPHQL_PAGINATION, payload={})

    publisher.publish(job, delay_ms=5000)

    props = channel.basic_publish.call_args.kwargs["properties"]
    assert props.headers["x-delay"] == 5000


def test_publish_sends_serialized_job_body():
    channel = Mock()
    publisher = JobPublisher(channel)
    job = Job(type=JobType.GRAPHQL_PAGINATION, payload={"target_total": 1000})

    publisher.publish(job)

    body = channel.basic_publish.call_args.kwargs["body"]
    restored = Job.from_bytes(body)
    assert restored.type == JobType.GRAPHQL_PAGINATION
    assert restored.payload == {"target_total": 1000}


def test_publish_uses_persistent_delivery_mode():
    channel = Mock()
    publisher = JobPublisher(channel)
    job = Job(type=JobType.REST_PAGINATION, payload={})

    publisher.publish(job)

    props = channel.basic_publish.call_args.kwargs["properties"]
    assert props.delivery_mode == 2
