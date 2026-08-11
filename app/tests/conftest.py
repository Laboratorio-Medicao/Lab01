import pytest

from src import config, storage

requires_supabase = pytest.mark.skipif(
    not config.supabase_env_configured(),
    reason="Supabase não configurado (.env) — pulando testes que dependem do banco",
)


@pytest.fixture
def db_connection(monkeypatch):
    """Conexão real com o Postgres do Supabase, apontando para tabelas
    isoladas (test_repositories/test_collection_state) em vez das tabelas de
    produção compartilhadas pelo time — ver REPOSITORIES_TABLE/
    COLLECTION_STATE_TABLE em src/storage.py."""
    monkeypatch.setattr(storage, "REPOSITORIES_TABLE", "test_repositories")
    monkeypatch.setattr(storage, "COLLECTION_STATE_TABLE", "test_collection_state")

    connection = storage.get_connection()
    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS test_repositories, test_collection_state")
    connection.commit()

    yield connection

    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS test_repositories, test_collection_state")
    connection.commit()
    connection.close()
