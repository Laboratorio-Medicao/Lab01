FROM rabbitmq:3.13-management
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
RUN curl -fL \
    "https://github.com/rabbitmq/rabbitmq-delayed-message-exchange/releases/download/v3.13.0/rabbitmq_delayed_message_exchange-3.13.0.ez" \
    -o /opt/rabbitmq/plugins/rabbitmq_delayed_message_exchange-3.13.0.ez
RUN rabbitmq-plugins enable --offline rabbitmq_delayed_message_exchange rabbitmq_management
