"""StableAgent Cloud — FastAPI 服务器入口。

向后兼容: `uvicorn web.server:app` 仍然可用。
实际逻辑在 web/app.py (create_app) 和 web/routes/ 模块。

Usage:
    uvicorn web.server:app --host 0.0.0.0 --port 8000
    python web/server.py
"""

from __future__ import annotations

from web.app import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
