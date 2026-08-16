import logging

from src.errors import RateLimitReached
from src.queue.dispatcher import JobDispatcher
from src.queue.publisher import JobPublisher
from src.queue.types import Job

logger = logging.getLogger(__name__)


class JobConsumer:
    def __init__(self, channel, dispatcher: JobDispatcher, publisher: JobPublisher):
        self._channel = channel
        self._dispatcher = dispatcher
        self._publisher = publisher

    def start(self, queue_name: str) -> None:
        self._channel.basic_qos(prefetch_count=1)
        self._channel.basic_consume(
            queue=queue_name,
            on_message_callback=self._on_message,
        )
        logger.info("consumer iniciado, aguardando jobs na fila %r...", queue_name)
        self._channel.start_consuming()

    def _on_message(self, channel, method, properties, body) -> None:
        job = Job.from_bytes(body)
        logger.info("processando job type=%s attempt=%s", job.type.value, job.attempt)
        try:
            self._dispatcher.dispatch(job)
            channel.basic_ack(delivery_tag=method.delivery_tag)
            logger.info("job concluído: type=%s", job.type.value)
        except RateLimitReached as error:
            delay_ms = int(error.seconds_until_reset() * 1000)
            retry_job = Job(type=job.type, payload=job.payload, attempt=job.attempt + 1)
            logger.warning(
                "rate limit atingido; re-enfileirando type=%s com delay=%.0fs (attempt=%s→%s)",
                job.type.value,
                delay_ms / 1000,
                job.attempt,
                retry_job.attempt,
            )
            self._publisher.publish(retry_job, delay_ms=delay_ms)
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception:
            logger.exception("erro ao processar job type=%s attempt=%s", job.type.value, job.attempt)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
