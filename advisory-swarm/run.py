"""Entrypoint. python run.py -> http://localhost:8000"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "app"))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
