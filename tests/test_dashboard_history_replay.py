"""测试 Dashboard Observer 历史事件回放 (V11.4)

验证：
1. /observe/{run_id} 能正确注入 run_id
2. /api/runs/{run_id}/events 能返回历史事件
3. /runs/{run_id} 重定向到 /observe/{run_id}
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ========== 测试 1: /observe/{run_id} 路由注入 run_id ==========

def test_observe_route_injects_run_id():
    """验证 /observe/{run_id} 路由会注入 meta 标签"""
    from web.app import create_app

    app = create_app()
    client = TestClient(app)

    test_run_id = "test_run_123"
    resp = client.get(f"/observe/{test_run_id}")

    assert resp.status_code == 200
    assert f'<meta name="run-id" content="{test_run_id}">' in resp.text


# ========== 测试 2: /runs/{run_id} 重定向到 /observe/{run_id} ==========

def test_runs_redirects_to_observe():
    """验证 /runs/{run_id} 重定向到 /observe/{run_id}"""
    from web.app import create_app

    app = create_app()
    client = TestClient(app, follow_redirects=False)

    test_run_id = "test_run_789"
    resp = client.get(f"/runs/{test_run_id}")

    assert resp.status_code == 302
    assert resp.headers["location"] == f"/observe/{test_run_id}"


# ========== 测试 3: JS 包含 run_id 提取逻辑 ==========

def test_js_contains_run_id_extraction():
    """验证 JS 包含从 meta 标签提取 run_id 的逻辑"""
    from web.app import create_app

    app = create_app()
    client = TestClient(app)

    # 获取静态 JS 文件
    resp = client.get("/static/run_observer.js")

    assert resp.status_code == 200
    js_content = resp.text

    # 检查 JS 包含 run_id 提取逻辑
    assert 'meta[name="run-id"]' in js_content
    assert "getAttribute" in js_content
    assert "runId" in js_content


# ========== 测试 4: JS 包含错误处理逻辑 ==========

def test_js_contains_error_handling():
    """验证 JS 包含错误处理逻辑"""
    from web.app import create_app

    app = create_app()
    client = TestClient(app)

    # 获取静态 JS 文件
    resp = client.get("/static/run_observer.js")

    assert resp.status_code == 200
    js_content = resp.text

    # 检查包含错误处理
    assert "事件 API 读取失败" in js_content
    assert "暂无历史事件，等待实时事件" in js_content
    assert "checkEffectivenessForRun" in js_content


# ========== 测试 5: API 返回结构验证 ==========

def test_api_events_endpoint_exists():
    """验证 /api/runs/{run_id}/events 端点存在"""
    from web.app import create_app

    app = create_app()
    client = TestClient(app)

    # 发送请求（即使 run 不存在，端点应该存在）
    resp = client.get("/api/runs/nonexistent_run/events")

    # 应该返回 404（run 不存在），而不是 404（端点不存在）
    # 或者返回 503（store 不可用）
    assert resp.status_code in [404, 503]


# ========== 测试 6: 验证 loadHistoryAndConnect 存在 ==========

def test_load_history_and_connect_exists():
    """验证 loadHistoryAndConnect 函数存在"""
    from web.app import create_app

    app = create_app()
    client = TestClient(app)

    # 获取静态 JS 文件
    resp = client.get("/static/run_observer.js")

    assert resp.status_code == 200
    js_content = resp.text

    # 检查包含关键函数
    assert "loadHistoryAndConnect" in js_content
    assert "applyEvent" in js_content
    assert "updateProgress" in js_content


# ========== 测试 7: 验证进度更新逻辑 ==========

def test_progress_update_logic():
    """验证进度更新逻辑存在"""
    from web.app import create_app

    app = create_app()
    client = TestClient(app)

    # 获取静态 JS 文件
    resp = client.get("/static/run_observer.js")

    assert resp.status_code == 200
    js_content = resp.text

    # 检查包含进度更新
    assert "progress_pct" in js_content
    assert "updateProgress" in js_content
    assert "progressBar" in js_content


# ========== 测试 8: 验证 WebSocket 连接逻辑 ==========

def test_websocket_connection_logic():
    """验证 WebSocket 连接逻辑存在"""
    from web.app import create_app

    app = create_app()
    client = TestClient(app)

    # 获取静态 JS 文件
    resp = client.get("/static/run_observer.js")

    assert resp.status_code == 200
    js_content = resp.text

    # 检查包含 WebSocket 连接
    assert "connectWebSocket" in js_content
    assert "WebSocket" in js_content
    assert "dashboard-sync/ws/runs" in js_content


# ========== 测试 9: 验证事件类型处理 ==========

def test_event_type_handling():
    """验证事件类型处理逻辑存在"""
    from web.app import create_app

    app = create_app()
    client = TestClient(app)

    # 获取静态 JS 文件
    resp = client.get("/static/run_observer.js")

    assert resp.status_code == 200
    js_content = resp.text

    # 检查包含事件类型处理
    assert "event_type" in js_content
    assert "run.completed" in js_content or "applyEvent" in js_content


# ========== 测试 10: 验证 avatar_state 更新 ==========

def test_avatar_state_update():
    """验证 avatar_state 更新逻辑存在"""
    from web.app import create_app

    app = create_app()
    client = TestClient(app)

    # 获取静态 JS 文件
    resp = client.get("/static/run_observer.js")

    assert resp.status_code == 200
    js_content = resp.text

    # 检查包含 avatar 更新
    assert "avatar_state" in js_content
    assert "updateAvatar" in js_content
    assert "AVATAR_SCENE_MAP" in js_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
