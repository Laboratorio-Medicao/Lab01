import os
from pathlib import Path

ENV_FILE_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_env_file(env_file_path=ENV_FILE_PATH):
    if not env_file_path.exists():
        return
    for line in env_file_path.read_text(encoding="utf-8").splitlines():
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith("#") or "=" not in stripped_line:
            continue
        key, value = stripped_line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_github_token():
    load_env_file()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN não encontrado. Defina no ambiente ou em um arquivo .env "
            "(veja .env.example)."
        )
    return token


SUPABASE_ENV_VARS = (
    "SUPABASE_HOST",
    "SUPABASE_PORT",
    "SUPABASE_DB_NAME",
    "SUPABASE_USER",
    "SUPABASE_PASSWORD",
)


def get_supabase_connection_params():
    load_env_file()
    values = {name: os.environ.get(name, "").strip() for name in SUPABASE_ENV_VARS}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError(
            f"variáveis do Supabase ausentes: {', '.join(missing)}. Defina no ambiente ou "
            "em um arquivo .env (veja .env.example) — use o host do connection pooling "
            "(porta 6543), não o de conexão direta, para evitar o problema de IPv6-only."
        )
    return {
        "host": values["SUPABASE_HOST"],
        "port": values["SUPABASE_PORT"],
        "dbname": values["SUPABASE_DB_NAME"],
        "user": values["SUPABASE_USER"],
        "password": values["SUPABASE_PASSWORD"],
    }


def supabase_env_configured():
    load_env_file()
    return all(os.environ.get(name, "").strip() for name in SUPABASE_ENV_VARS)


RABBITMQ_ENV_VARS = ("RABBITMQ_HOST", "RABBITMQ_PORT", "RABBITMQ_USER", "RABBITMQ_PASS")


def get_rabbitmq_connection_params():
    load_env_file()
    values = {name: os.environ.get(name, "").strip() for name in RABBITMQ_ENV_VARS}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError(
            f"variáveis do RabbitMQ ausentes: {', '.join(missing)}. "
            "Defina no ambiente ou em .env (veja .env.example)."
        )
    return {
        "host": values["RABBITMQ_HOST"],
        "port": int(values["RABBITMQ_PORT"]),
        "user": values["RABBITMQ_USER"],
        "password": values["RABBITMQ_PASS"],
    }
