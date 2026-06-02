"""web.server_slim — Slim Cloud Edition 入口。

Usage:
    STABLEAGENT_PROFILE=slim uvicorn web.server_slim:app --host 127.0.0.1 --port 18789
    # 或
    PYTHONPATH=. .venv/bin/python -m stable_agent.cli serve --profile slim
"""

import os
os.environ.setdefault("STABLEAGENT_PROFILE", "slim")

from web.app_slim import create_slim_app

app = create_slim_app()
