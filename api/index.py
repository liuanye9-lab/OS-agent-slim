"""Vercel Serverless Function — FastAPI 入口。

将 web.server:app 导出为 Vercel Python Runtime 兼容的 ASGI 应用。
"""

from web.server import create_app

app = create_app()
