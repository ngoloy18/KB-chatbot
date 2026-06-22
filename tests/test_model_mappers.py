import sys
from pathlib import Path

from sqlalchemy.orm import configure_mappers

# Add the project root to Python's import path when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import app.models


def check_model_mappers() -> None:
    """Verify split SQLAlchemy model files can resolve all relationships."""

    configure_mappers()
    print("SQLAlchemy model mappers OK.")


if __name__ == "__main__":
    try:
        check_model_mappers()
    except Exception as exc:
        print("SQLAlchemy model mapper test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
