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
