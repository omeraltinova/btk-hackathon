"""Compatibility wrapper for the backend demo seed worker.

Preferred command from `backend/`:
    uv run python -m app.workers.demo_seed
"""

from __future__ import annotations

from app.workers.demo_seed import main


if __name__ == "__main__":
    main()
