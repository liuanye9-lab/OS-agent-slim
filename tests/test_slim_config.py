"""tests.test_slim_config — Slim 配置测试。"""

import os
import pytest
from stable_agent.cloud.config import CloudConfig, get_cloud_config, reset_cloud_config


class TestSlimConfig:
    """Slim 配置测试。"""

    def setup_method(self):
        reset_cloud_config()

    def teardown_method(self):
        reset_cloud_config()

    def test_default_profile_is_slim(self):
        """默认 profile 应为 slim。"""
        os.environ.pop("STABLEAGENT_PROFILE", None)
        config = CloudConfig.from_env()
        assert config.profile == "slim"
        assert config.is_slim is True

    def test_full_profile(self):
        """设置 STABLEAGENT_PROFILE=full。"""
        os.environ["STABLEAGENT_PROFILE"] = "full"
        try:
            config = CloudConfig.from_env()
            assert config.profile == "full"
            assert config.is_slim is False
        finally:
            os.environ.pop("STABLEAGENT_PROFILE", None)

    def test_default_port(self):
        """默认端口应为 18789。"""
        os.environ.pop("STABLEAGENT_PORT", None)
        config = CloudConfig.from_env()
        assert config.port == 18789

    def test_default_bind_host(self):
        """默认绑定 127.0.0.1。"""
        os.environ.pop("STABLEAGENT_BIND_HOST", None)
        config = CloudConfig.from_env()
        assert config.bind_host == "127.0.0.1"

    def test_slim_disables_heavy_features(self):
        """Slim 模式禁用重型功能。"""
        os.environ.pop("STABLEAGENT_ENABLE_EFFECTIVENESS", None)
        os.environ.pop("STABLEAGENT_ENABLE_SAAS", None)
        config = CloudConfig.from_env()
        assert config.enable_effectiveness is False
        assert config.enable_saas is False
        assert config.enable_heavy_skillopt is False
        assert config.enable_canvas_animation is False

    def test_max_events_default(self):
        """默认最大事件数 1000。"""
        os.environ.pop("STABLEAGENT_MAX_EVENTS", None)
        config = CloudConfig.from_env()
        assert config.max_events == 1000

    def test_max_task_logs_default(self):
        """默认每任务最大日志 200。"""
        os.environ.pop("STABLEAGENT_MAX_TASK_LOGS", None)
        config = CloudConfig.from_env()
        assert config.max_task_logs == 200

    def test_worker_timeout_default(self):
        """默认 Worker 超时 60 秒。"""
        os.environ.pop("STABLEAGENT_WORKER_TIMEOUT", None)
        config = CloudConfig.from_env()
        assert config.worker_timeout == 60

    def test_cloud_token_default_empty(self):
        """默认 Token 为空。"""
        os.environ.pop("STABLEAGENT_CLOUD_TOKEN", None)
        config = CloudConfig.from_env()
        assert config.cloud_token == ""

    def test_uvicorn_workers_is_1(self):
        """Uvicorn workers 应为 1。"""
        config = CloudConfig.from_env()
        assert config.uvicorn_workers == 1
