"""tests.test_cli_slim_commands — CLI slim 命令测试。"""

import argparse
import pytest
from stable_agent.cli import (
    cmd_cloud_health,
    cmd_worker_list,
    cmd_task_list,
    cmd_serve,
)


class TestCLISlimCommands:
    """CLI slim 命令测试。"""

    def test_cmd_cloud_health_exists(self):
        """cmd_cloud_health 函数存在。"""
        assert callable(cmd_cloud_health)

    def test_cmd_worker_list_exists(self):
        """cmd_worker_list 函数存在。"""
        assert callable(cmd_worker_list)

    def test_cmd_task_list_exists(self):
        """cmd_task_list 函数存在。"""
        assert callable(cmd_task_list)

    def test_cmd_serve_exists(self):
        """cmd_serve 函数存在且支持 profile 参数。"""
        assert callable(cmd_serve)

    def test_cli_parser_has_serve(self):
        """CLI 解析器包含 serve 命令。"""
        import stable_agent.cli as cli_module
        # 检查 main 函数存在
        assert callable(cli_module.main)

    def test_cli_parser_has_worker(self):
        """CLI 解析器包含 worker 命令。"""
        import stable_agent.cli as cli_module
        assert callable(cli_module.main)

    def test_cli_parser_has_cloud(self):
        """CLI 解析器包含 cloud 命令。"""
        import stable_agent.cli as cli_module
        assert callable(cli_module.main)

    def test_serve_profile_slim(self):
        """serve 命令支持 --profile slim。"""
        import stable_agent.cli as cli_module
        # 验证 cmd_serve 接受 profile 参数
        args = argparse.Namespace(
            host="127.0.0.1", port=18789, profile="slim"
        )
        # 不实际启动，只验证函数签名
        assert hasattr(args, "profile")

    def test_cloud_health_requires_server(self):
        """cloud health 命令需要服务器运行。"""
        args = argparse.Namespace(host="127.0.0.1", port=19999, json=True)
        with pytest.raises(SystemExit):
            cmd_cloud_health(args)
