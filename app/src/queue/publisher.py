import pika

from src.queue.connection import EXCHANGE_NAME, ROUTING_KEY
from src.queue.types import Job


class JobPublisher:
    def __init__(self, channel):
        self._channel = channel

    def publish(self, job: Job, delay_ms: int = 0) -> None:
        self._channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=ROUTING_KEY,
            body=job.to_bytes(),
            properties=pika.BasicProperties(
                delivery_mode=2,
                headers={"x-delay": delay_ms} if delay_ms > 0 else {},
            ),
        )
