import os
import secrets
from pathlib import Path


GENERATED_SECRET_LENGTH = 32
LEGACY_DEFAULT_SECRETS = {
    "mouse-secret-key-2026",
    "replace-with-a-random-secret-at-least-32-characters",
}


def load_or_create_secret_key(configured_secret, data_dir):
    """Return a custom secret or persist a generated one in the data directory."""
    configured_secret = (configured_secret or "").strip()
    if configured_secret and configured_secret not in LEGACY_DEFAULT_SECRETS:
        return configured_secret

    secret_path = Path(data_dir) / ".secret_key"
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        stored_secret = secret_path.read_text(encoding="ascii").strip()
    except FileNotFoundError:
        stored_secret = ""
    if stored_secret:
        return stored_secret

    generated_secret = secrets.token_hex(GENERATED_SECRET_LENGTH // 2)
    try:
        descriptor = os.open(secret_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        stored_secret = secret_path.read_text(encoding="ascii").strip()
        if not stored_secret:
            raise RuntimeError(f"持久化 SECRET_KEY 文件为空：{secret_path}")
        return stored_secret

    with os.fdopen(descriptor, "w", encoding="ascii") as secret_file:
        secret_file.write(generated_secret)
        secret_file.write("\n")
    return generated_secret
