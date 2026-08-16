import os
import pytest
from unittest.mock import patch


def test_get_rabbitmq_connection_params_returns_all_fields(monkeypatch):
    monkeypatch.setenv("RABBITMQ_HOST", "localhost")
    monkeypatch.setenv("RABBITMQ_PORT", "5672")
    monkeypatch.setenv("RABBITMQ_USER", "guest")
    monkeypatch.setenv("RABBITMQ_PASS", "secret")

    from src.config import get_rabbitmq_connection_params
    params = get_rabbitmq_connection_params()

    assert params["host"] == "localhost"
    assert params["port"] == 5672
    assert params["user"] == "guest"
    assert params["password"] == "secret"


def test_get_rabbitmq_connection_params_raises_when_missing(monkeypatch):
    for var in ("RABBITMQ_HOST", "RABBITMQ_PORT", "RABBITMQ_USER", "RABBITMQ_PASS"):
        monkeypatch.delenv(var, raising=False)

    from src.config import get_rabbitmq_connection_params
    with pytest.raises(RuntimeError, match="RABBITMQ"):
        get_rabbitmq_connection_params()
