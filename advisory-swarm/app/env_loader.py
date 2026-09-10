"""Tiny .env loader — no python-dotenv dependency for a two-line job.

Only sets a variable if it isn't already in the environment, so a real `export` always wins.
"""

from pathlib import Path


def load_env_file(path: Path) -> None:
    import os

    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
