import pika

from src.config import get_rabbitmq_connection_params

EXCHANGE_NAME = "github_collector"
QUEUE_NAME = "jobs"
ROUTING_KEY = "jobs"


def get_channel():
    params = get_rabbitmq_connection_params()
    credentials = pika.PlainCredentials(params["user"], params["password"])
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=params["host"],
            port=params["port"],
            credentials=credentials,
        )
    )
    channel = connection.channel()
    _declare_topology(channel)
    return connection, channel


def _declare_topology(channel) -> None:
    channel.exchange_declare(
        exchange=EXCHANGE_NAME,
        exchange_type="x-delayed-message",
        durable=True,
        arguments={"x-delayed-type": "direct"},
    )
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    channel.queue_bind(
        queue=QUEUE_NAME,
        exchange=EXCHANGE_NAME,
        routing_key=ROUTING_KEY,
    )
